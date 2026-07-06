import os
import pickle
import numpy as np
from sqlalchemy.orm import Session
from ..config import settings
from ..schemas.schemas import RiskScoreResponse, DecisionResponse, TransactionScoreRequest
from ..models.models import RiskScore, DecisionLog, Alert, Transaction, FraudCase
from datetime import datetime
import uuid

class RiskFusionEngine:
    _model = None

    @classmethod
    def _load_model(cls):
        if cls._model is None:
            # Centralized model file path
            from ..engines.training import FUSION_MODEL_FILE
            if os.path.exists(FUSION_MODEL_FILE):
                try:
                    with open(FUSION_MODEL_FILE, "rb") as f:
                        cls._model = pickle.load(f)
                except Exception as e:
                    print(f"[PayShield] Error loading fusion model: {e}")

    @classmethod
    def fuse_and_decide(
        cls,
        db: Session,
        transaction_id: str,
        user_id: str,
        req: TransactionScoreRequest,
        scores: RiskScoreResponse,
        anomaly_signals: dict | None = None,
        scam_analysis: dict | None = None,
        graph_signals: dict | None = None
    ) -> DecisionResponse:
        """
        Combines behavioral, device, geolocation, anomaly, and graph risk scores into a single weighted score.
        Integrates Gemini AI scam remarks detection into the final score.
        Computes the final authorization decision and explainable reason codes.
        Saves scores, decision logs, and generates alerts if risk is elevated.
        """
        # Determine scam features for model
        scam_likely = 0.0
        scam_suspicious = 0.0
        if scam_analysis:
            if scam_analysis.get("classification") == "Scam Likely":
                scam_likely = 1.0
            elif scam_analysis.get("classification") == "Suspicious":
                scam_suspicious = 1.0

        cls._load_model()
        total_score = None
        if cls._model is not None:
            try:
                # Model features: [behavioral_score, device_score, geolocation_score, anomaly_score, graph_score, scam_likely, scam_suspicious]
                x = np.array([[
                    scores.behavioral_score,
                    scores.device_score,
                    scores.geolocation_score,
                    scores.anomaly_score,
                    scores.graph_score,
                    scam_likely,
                    scam_suspicious
                ]])
                total_score = float(cls._model.predict_proba(x)[0][1] * 100.0)
            except Exception as e:
                print(f"[PayShield] Fusion model inference failed, using weighted fallback: {e}")
                total_score = None
        if total_score is None:
            # 1. Compute weighted total risk score fallback
            total_score = (
                settings.WEIGHT_BEHAVIORAL * scores.behavioral_score +
                settings.WEIGHT_DEVICE * scores.device_score +
                settings.WEIGHT_GEOLOCATION * scores.geolocation_score +
                settings.WEIGHT_ANOMALY * scores.anomaly_score +
                settings.WEIGHT_GRAPH * scores.graph_score
            )
            
            # Apply scam detection penalty to total score fallback
            if scam_likely == 1.0:
                total_score += 25.0
            elif scam_suspicious == 1.0:
                total_score += 10.0

            # Apply critical signal penalties to total score fallback
            if scores.behavioral_score >= 85.0:  # Bot pattern
                total_score += 35.0
            if scores.geolocation_score >= 60.0:  # Impossible travel
                total_score += 20.0
            if scores.graph_score >= 80.0:  # Fraud ring link
                total_score += 30.0

        total_score = min(round(total_score, 2), 99.0)
        scores.total_score = total_score

        # 2. Determine Action Decision
        if total_score >= settings.THRESH_REVIEW:
            decision = "BLOCK"
        elif total_score >= settings.THRESH_STEP_UP:
            decision = "REVIEW"
        elif total_score >= settings.THRESH_ALLOW:
            decision = "STEP_UP"
        else:
            decision = "ALLOW"
            
        # 3. Generate Explainable Reason Codes
        reason_codes = []
        
        # Behavioral reasons
        if scores.behavioral_score >= 85.0:
            reason_codes.append("BOT_PATTERN_DETECTED")
        elif scores.behavioral_score >= 50.0:
            reason_codes.append("BEHAVIORAL_DEVIATION")
            
        # Device reasons
        if scores.device_score >= 100.0:
            reason_codes.append("COMPROMISED_DEVICE_IP")
        elif scores.device_score >= 50.0:
            reason_codes.append("NEW_DEVICE")
        elif scores.device_score >= 30.0:
            reason_codes.append("SUSPICIOUS_IP_LOC")

        # Geolocation reasons
        if scores.geolocation_score >= 60.0:
            reason_codes.append("IMPOSSIBLE_TRAVEL")
        elif scores.geolocation_score >= 35.0:
            reason_codes.append("SUSPICIOUS_COUNTRY_CHANGE")
        elif scores.geolocation_score >= 15.0:
            reason_codes.append("NEW_GEOGRAPHIC_LOCATION")
        elif scores.geolocation_score >= 10.0:
            reason_codes.append("SUSPICIOUS_CITY_CHANGE")
            
        # Scam reasons
        if scam_analysis:
            if scam_analysis.get("classification") == "Scam Likely":
                reason_codes.append("SCAM_TEXT_DETECTED")
            elif scam_analysis.get("classification") == "Suspicious":
                reason_codes.append("SUSPICIOUS_REMARKS")

        anomaly_signals = anomaly_signals or {}
        # Anomaly reasons
        if scores.anomaly_score >= 80.0:
            reason_codes.append("EXTREME_ANOMALY_VELOCITY")
        elif scores.anomaly_score >= 50.0:
            if anomaly_signals.get("new_beneficiary"):
                reason_codes.append(f"NEW_BENEFICIARY_{int(anomaly_signals.get('beneficiary_age_h', 0))}H_OLD")
            if anomaly_signals.get("z_score", 0) > 2:
                reason_codes.append(f"AMOUNT_{anomaly_signals['z_score']:.1f}x_ABOVE_AVERAGE")
            if anomaly_signals.get("velocity", 0) > 5:
                reason_codes.append("VELOCITY_BURST_DETECTED")
            if req.amount >= 2000.0 and not reason_codes:
                reason_codes.append("HIGH_AMOUNT")
                
        # Graph reasons
        if graph_signals:
            if graph_signals.get("circular_flow"):
                reason_codes.append("CIRCULAR_MONEY_FLOW")
            if graph_signals.get("layering"):
                reason_codes.append("LAYERING_PATTERN")
            if graph_signals.get("burst_transfers"):
                reason_codes.append("BURST_TRANSFERS")
            if graph_signals.get("hub_account"):
                reason_codes.append("HUB_ACCOUNT")
            if graph_signals.get("funnel_account"):
                reason_codes.append("FUNNEL_ACCOUNT")
                
        if scores.graph_score >= 80.0:
            if "FRAUD_RING_LINK" not in reason_codes:
                reason_codes.append("FRAUD_RING_LINK")
        elif scores.graph_score >= 40.0:
            if "SHARED_COMPROMISED_DEVICE" not in reason_codes:
                reason_codes.append("SHARED_COMPROMISED_DEVICE")
            
        # Fallback if no specific code is triggered but score is high
        if not reason_codes and total_score >= 30.0:
            reason_codes.append("SUSPICIOUS_RISK_AGGREGATION")
            
        # 4. Save Risk Scores to Database
        db_scores = RiskScore(
            transaction_id=transaction_id,
            behavioral_score=scores.behavioral_score,
            device_score=scores.device_score,
            geolocation_score=scores.geolocation_score,
            anomaly_score=scores.anomaly_score,
            graph_score=scores.graph_score,
            total_score=total_score
        )
        db.add(db_scores)
        
        # 5. Save Decision Log to Database
        reason_str = ",".join(reason_codes)
        db_decision = DecisionLog(
            transaction_id=transaction_id,
            decision=decision,
            reason_codes=reason_str
        )
        db.add(db_decision)
        
        # 6. Generate Live Alert if risk is elevated (score >= THRESH_ALLOW)
        if total_score >= settings.THRESH_ALLOW:
            severity = "LOW"
            if total_score >= settings.THRESH_REVIEW:
                severity = "CRITICAL"
            elif total_score >= settings.THRESH_STEP_UP:
                severity = "HIGH"
            elif total_score >= settings.THRESH_ALLOW:
                severity = "MEDIUM"
                
            db_alert = Alert(
                transaction_id=transaction_id,
                user_id=user_id,
                risk_score=total_score,
                severity=severity,
                reason=" | ".join(reason_codes),
                is_resolved=False
            )
            db.add(db_alert)

        # Auto-create fraud case for BLOCK decisions
        if decision == "BLOCK":
            case_type = "unknown"
            if "BOT_PATTERN_DETECTED" in reason_codes or "NEW_DEVICE" in reason_codes:
                case_type = "ato"
            elif "FRAUD_RING_LINK" in reason_codes or "SHARED_COMPROMISED_DEVICE" in reason_codes:
                case_type = "mule"
            elif any(code.startswith("NEW_BENEFICIARY") for code in reason_codes):
                case_type = "social_engineering"
            
            db_case = FraudCase(
                id=str(uuid.uuid4()),
                user_id=user_id,
                transaction_id=transaction_id,
                case_type=case_type,
                outcome="under_review",
                severity=severity
            )
            db.add(db_case)
            
        db.flush()
        # 7. Formulate and return API response payload
        from .reason_codes import get_reason_detail
        detailed_reasons = [get_reason_detail(code) for code in reason_codes]
        return DecisionResponse(
            transaction_id=transaction_id,
            risk_score=total_score,
            decision=decision,
            reason_codes=reason_codes,
            reasons_detailed=detailed_reasons,
            breakdown=scores,
            scam_classification=scam_analysis.get("classification") if scam_analysis else None,
            scam_explanation=scam_analysis.get("explanation") if scam_analysis else None,
            timestamp=datetime.now()
        )
