import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..models.models import Transaction

class TransactionAnomalyEngine:
    _model = None
    
    @classmethod
    def train_model(cls, db: Session):
        """
        Trains the Isolation Forest model on historical transaction patterns.
        If no history exists, we seed the DB with realistic synthetic baseline data first.
        """
        # Fetch last 1000 transactions to train the model
        history = db.query(Transaction).filter(Transaction.status == "ALLOWED").order_by(Transaction.timestamp.desc()).limit(1000).all()
        
        # If we have less than 50 transactions, we generate local synthetic normal data for training
        # to ensure the ML model can compile and perform inference immediately.
        X_train = []
        if len(history) < 50:
            # Generate 200 synthetic normal transactions
            # Normal distribution of amounts around $50-$150, hours mostly daytime (9am - 8pm), low velocity
            prob_raw = np.array([0.05, 0.08, 0.09, 0.09, 0.08, 0.07, 0.07, 0.07, 0.08, 0.08, 0.07, 0.06, 0.04, 0.03, 0.02, 0.01, 0.01, 0.005, 0.005, 0.005, 0.005, 0.005, 0.01, 0.03])
            prob_normalized = prob_raw / prob_raw.sum()
            for _ in range(200):
                amount = float(np.random.normal(75, 40))
                amount = max(5.0, amount)  # min $5
                hour = int(np.random.choice(
                    a=[8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7],
                    p=prob_normalized
                ))
                velocity_1h = int(np.random.poisson(0.5)) + 1
                velocity_24h = int(np.random.poisson(2.5)) + 1
                geo_distance = float(np.random.exponential(15)) # mostly local
                
                X_train.append([amount, hour, velocity_1h, velocity_24h, geo_distance])
        else:
            # Convert actual history to feature vectors
            for tx in history:
                hour = tx.timestamp.hour
                # Calculate velocity dynamically (in-memory for training)
                vel_1h = db.query(Transaction).filter(
                    Transaction.user_id == tx.user_id,
                    Transaction.timestamp >= tx.timestamp - timedelta(hours=1),
                    Transaction.timestamp <= tx.timestamp
                ).count()
                
                vel_24h = db.query(Transaction).filter(
                    Transaction.user_id == tx.user_id,
                    Transaction.timestamp >= tx.timestamp - timedelta(days=1),
                    Transaction.timestamp <= tx.timestamp
                ).count()
                
                # Mock geo_distance based on location changes
                # In real life, we calculate distance. Here we use 0.0 for normal, larger for new
                geo_distance = 0.0 if tx.location == "Home" else 150.0
                X_train.append([tx.amount, hour, vel_1h, vel_24h, geo_distance])
        
        # Train the Isolation Forest
        cls._model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        cls._model.fit(X_train)

    @classmethod
    def calculate_zscore_risk(cls, db: Session, user_id: str, amount: float) -> tuple[float, float]:
        """
        Returns (risk_score_0_100, z_score_value)
        """
        history = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.status == "ALLOWED"
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
        new_beneficiary: bool = False
    ) -> tuple[float, dict]:
        """
        Extracts features for the incoming transaction and runs Isolation Forest inference.
        Returns an anomaly risk score between 0 and 100 with diagnostic signals.
        """
        # Ensure model is trained; if not, train it
        if cls._model is None:
            cls.train_model(db)
            
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
            if last_tx.location == location:
                geo_distance = 0.0
            else:
                # Basic distance mocking based on location names
                # Home/Work = short distance, Overseas/New Country = extreme distance
                if "Overseas" in location or "London" in location or "Tokyo" in location:
                    geo_distance = 3500.0
                elif "New City" in location or "California" in location:
                    geo_distance = 500.0
                else:
                    geo_distance = 50.0
                    
        # Feature vector
        x = np.array([[amount, hour, velocity_1h, velocity_24h, geo_distance]])
        
        # isolation forest decision_function outputs negative values for anomalies, positive for inliers
        # Values range roughly from -0.5 (most anomalous) to +0.5 (most normal)
        raw_score = cls._model.decision_function(x)[0]
        
        # Normalize to 0-100 range:
        # standard normal transactions yield raw_score around 0.15 - 0.25 -> risk 0-20
        # highly anomalous yields raw_score around -0.15 to -0.30 -> risk 80-100
        # Formula: score = (inlier_score - raw_score) * scale
        # We can map raw_score of 0.20 to 0.0 risk, and raw_score of -0.20 to 100.0 risk
        normalized_score = (0.20 - raw_score) * 250.0
        isolation_forest_score = min(max(normalized_score, 0.0), 100.0)
        
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
        
        base_score = max(isolation_forest_score, zscore_risk)
        final_score = min(base_score + velocity_risk + beneficiary_risk + high_value_risk, 100.0)
        
        return round(final_score, 2), {
            "z_score": z_val,
            "velocity": velocity,
            "new_beneficiary": new_beneficiary,
            "beneficiary_age_h": beneficiary_age_hours
        }
