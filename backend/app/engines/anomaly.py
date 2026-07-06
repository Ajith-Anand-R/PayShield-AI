import numpy as np
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os
import pickle
from ..models.models import Transaction

class TransactionAnomalyEngine:
    _model = None
    
    @classmethod
    def _load_model(cls):
        if cls._model is None:
            from .training import ANOMALY_MODEL_FILE
            if os.path.exists(ANOMALY_MODEL_FILE):
                try:
                    with open(ANOMALY_MODEL_FILE, "rb") as f:
                        cls._model = pickle.load(f)
                except Exception as e:
                    print(f"[PayShield] Error loading anomaly model: {e}")

    @classmethod
    def train_model(cls, db: Session):
        """
        Backwards-compatible entry point retained for callers/tests.

        Delegates to the unified, calibrated training pipeline (``train_all_engines``)
        so there is a single source of truth for model training. The previous
        standalone path trained an uncalibrated RandomForest on label-leaking synthetic
        data and reported a meaningless 100% accuracy; it has been removed.
        """
        from .training import train_all_engines
        train_all_engines(db)
        cls._model = None
        cls._load_model()

    @staticmethod
    def _heuristic_anomaly_score(amount_ratio, velocity_1h, velocity_24h, geo_distance, hour) -> float:
        """
        Rule-based fallback used when the trained model is unavailable or inference
        fails. Mirrors the fraud vectors the model is trained on so the service
        degrades gracefully instead of erroring out.
        """
        score = 0.0
        if amount_ratio >= 10:
            score += 60.0
        elif amount_ratio >= 4:
            score += 35.0
        elif amount_ratio >= 2:
            score += 15.0
        if velocity_1h >= 7:
            score += 30.0
        elif velocity_1h >= 4:
            score += 15.0
        if geo_distance >= 800:
            score += 35.0
        elif geo_distance >= 300:
            score += 15.0
        if hour in (0, 1, 2, 3, 4):
            score += 10.0
        return min(score, 100.0)

    @classmethod
    def calculate_zscore_risk(cls, db: Session, user_id: str, amount: float) -> tuple[float, float]:
        """
        Returns (risk_score_0_100, z_score_value)
        """
        history = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.status == "ALLOW"
        ).order_by(Transaction.timestamp.desc()).limit(100).all()
        
        if len(history) < 5:
            return 0.0, 0.0
        
        amounts = [t.amount for t in history]
        avg = sum(amounts) / len(amounts)
        std = (sum((x - avg) ** 2 for x in amounts) / len(amounts)) ** 0.5
        if std < 1:
            std = 1
        
        z = (amount - avg) / std
        
        if z <= 2:
            score = 0.0
        elif z <= 3:
            score = 25.0
        elif z <= 4:
            score = 40.0
        else:
            score = 60.0
        
        return score, z

    @classmethod
    def calculate_risk(
        cls,
        db: Session,
        user_id: str,
        amount: float,
        location: str,
        beneficiary_age_hours: float | None = None,
        new_beneficiary: bool = False,
        latitude: float | None = None,
        longitude: float | None = None
    ) -> tuple[float, dict]:
        """
        Extracts features for the incoming transaction and runs RandomForestClassifier probability inference.
        Returns an anomaly risk score between 0 and 100 with diagnostic signals.
        """
        # Ensure model is loaded (heuristic fallback handles a missing model below)
        cls._load_model()

        now = datetime.now()
        hour = now.hour
        
        # Calculate real-time transaction velocities
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)
        
        velocity_1h = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.timestamp >= one_hour_ago
        ).count() + 1  # include current transaction
        
        velocity_24h = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.timestamp >= one_day_ago
        ).count() + 1
        
        # Determine geo_distance from last transaction
        last_tx = db.query(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.timestamp.desc()).first()
        if not last_tx:
            geo_distance = 0.0  # first transaction
        else:
            if latitude is not None and longitude is not None and last_tx.latitude is not None and last_tx.longitude is not None:
                from .geolocation import GeolocationRiskEngine
                geo_distance = GeolocationRiskEngine.haversine_distance(
                    last_tx.latitude, last_tx.longitude, latitude, longitude
                )
            else:
                if last_tx.location == location:
                    geo_distance = 0.0
                else:
                    if "Overseas" in location or "London" in location or "Tokyo" in location:
                        geo_distance = 3500.0
                    elif "New City" in location or "California" in location:
                        geo_distance = 500.0
                    else:
                        geo_distance = 50.0
                        
        # Calculate user's average historical transaction amount
        user_history = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.status == "ALLOW"
        ).all()
        if user_history:
            user_avg_amount = sum(t.amount for t in user_history) / len(user_history)
        else:
            # Fallback to global average of ALLOWED transactions if available
            global_history = db.query(Transaction).filter(Transaction.status == "ALLOW").all()
            if global_history:
                user_avg_amount = sum(t.amount for t in global_history) / len(global_history)
            else:
                user_avg_amount = 500.0  # static default baseline for first-time transaction
            
        amount_ratio = amount / (user_avg_amount + 1.0)
                    
        # Feature vector
        x = np.array([[amount_ratio, hour, velocity_1h, velocity_24h, geo_distance]])

        # Supervised probability estimation for Class 1 (Fraud anomaly), with a
        # heuristic fallback if the model is missing or inference fails.
        supervised_anomaly_score = None
        if cls._model is not None:
            try:
                supervised_anomaly_score = float(cls._model.predict_proba(x)[0][1] * 100.0)
            except Exception as e:
                print(f"[PayShield] Anomaly model inference failed, using heuristic: {e}")
        if supervised_anomaly_score is None:
            supervised_anomaly_score = cls._heuristic_anomaly_score(
                amount_ratio, velocity_1h, velocity_24h, geo_distance, hour
            )
        
        zscore_risk, z_val = cls.calculate_zscore_risk(db, user_id, amount)
        
        from ..services.redis_client import get_txn_count
        velocity = get_txn_count(user_id)
        velocity_risk = 0.0
        if velocity > 5:
            velocity_risk = 20.0
        elif velocity > 3:
            velocity_risk = 10.0
        
        beneficiary_risk = 0.0
        if new_beneficiary:
            if beneficiary_age_hours is not None and beneficiary_age_hours < 1:
                beneficiary_risk = 30.0
            elif beneficiary_age_hours is not None and beneficiary_age_hours < 24:
                beneficiary_risk = 20.0
        
        high_value_risk = 10.0 if amount > 50000 else 0.0
        
        base_score = max(supervised_anomaly_score, zscore_risk)
        final_score = min(base_score + velocity_risk + beneficiary_risk + high_value_risk, 100.0)
        
        return round(final_score, 2), {
            "z_score": z_val,
            "velocity": velocity,
            "new_beneficiary": new_beneficiary,
            "beneficiary_age_h": beneficiary_age_hours
        }


