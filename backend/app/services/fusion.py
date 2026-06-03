from sqlalchemy.orm import Session
from ..config import settings
from ..schemas.schemas import RiskScoreResponse, DecisionResponse, TransactionScoreRequest
from ..models.models import RiskScore, DecisionLog, Alert, Transaction, FraudCase
from datetime import datetime
import uuid

class RiskFusionEngine:
    @staticmethod
    def fuse_and_decide(
        db: Session,
        transaction_id: str,
        user_id: str,
        req: TransactionScoreRequest,
        scores: RiskScoreResponse,
        anomaly_signals: dict | None = None
    ) -> DecisionResponse:
        """
        Combines behavioral, device, anomaly, and graph risk scores into a single weighted score.
        Computes the final authorization decision and explainable reason codes.
        Saves scores, decision logs, and generates alerts if risk is elevated.
        """
        # 1. Compute weighted total risk score
        total_score = (
            settings.WEIGHT_BEHAVIORAL * scores.behavioral_score +
            settings.WEIGHT_DEVICE * scores.device_score +
            settings.WEIGHT_ANOMALY * scores.anomaly_score +
            settings.WEIGHT_GRAPH * scores.graph_score
        )
        total_score = round(total_score, 2)
        scores.total_score = total_score
        
        # 2. Determine Action Decision
        # 0-29: ALLOW
        # 30-54: STEP_UP
        # 55-74: DELAY
        # 75+: BLOCK
        decision = "ALLOW"
        if total_score >= settings.THRESH_DELAY:
            decision = "BLOCK"
        elif total_score >= settings.THRESH_STEP_UP:
            decision = "DELAY"
        elif total_score >= settings.THRESH_ALLOW:
            decision = "STEP_UP"
            
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
        if scores.graph_score >= 80.0:
            reason_codes.append("FRAUD_RING_LINK")
        elif scores.graph_score >= 40.0:
            reason_codes.append("SHARED_COMPROMISED_DEVICE")
            
        # Fallback if no specific code is triggered but score is high
        if not reason_codes and total_score >= 30.0:
            reason_codes.append("SUSPICIOUS_RISK_AGGREGATION")
            
        # 4. Save Risk Scores to Database
        db_scores = RiskScore(
            transaction_id=transaction_id,
            behavioral_score=scores.behavioral_score,
            device_score=scores.device_score,
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
        
        # 6. Generate Live Alert if risk is elevated (score >= 30)
        if total_score >= 30.0:
            severity = "LOW"
            if total_score >= settings.THRESH_DELAY:
                severity = "CRITICAL"
            elif total_score >= settings.THRESH_STEP_UP:
                severity = "HIGH"
            elif total_score >= 30.0:
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
            
        # Commit DB records
        db.commit()
        
        # 7. Formulate and return API response payload
        return DecisionResponse(
            transaction_id=transaction_id,
            risk_score=total_score,
            decision=decision,
            reason_codes=reason_codes,
            breakdown=scores,
            timestamp=datetime.now()
        )
