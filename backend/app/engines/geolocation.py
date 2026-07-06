import os
import pickle
import numpy as np
from sqlalchemy.orm import Session
from ..models.models import Transaction
from ..schemas.schemas import DeviceSignal
from ..config import settings
import math

class GeolocationRiskEngine:
    _model = None

    @classmethod
    def _load_model(cls):
        if cls._model is None:
            from .training import GEOLOC_MODEL_FILE
            if os.path.exists(GEOLOC_MODEL_FILE):
                try:
                    with open(GEOLOC_MODEL_FILE, "rb") as f:
                        cls._model = pickle.load(f)
                except Exception as e:
                    print(f"[PayShield] Error loading geolocation model: {e}")

    @classmethod
    def calculate_risk(cls, db: Session, user_id: str, signal: DeviceSignal) -> float:
        """
        Calculates geolocation anomaly risks (new location, impossible travel, city/country changes).
        Returns a score between 0.0 and 100.0.
        """
        # If no geolocation coordinates or city/country info is provided, return 0.0
        if signal.latitude is None or signal.longitude is None:
            if not signal.city and not signal.country:
                return 0.0

        # Retrieve the user's last successful transaction
        last_txn = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.status == "ALLOW"
        ).order_by(Transaction.timestamp.desc()).first()

        # Extract features for model
        is_new_location = 0.0
        if signal.city:
            loc_history = db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.status == "ALLOW",
                Transaction.city == signal.city
            ).first()
            if not loc_history:
                is_new_location = 1.0

        is_city_change = 0.0
        if last_txn and signal.city and last_txn.city and signal.city != last_txn.city:
            is_city_change = 1.0

        is_country_change = 0.0
        if last_txn and signal.country and last_txn.country and signal.country != last_txn.country:
            is_country_change = 1.0

        travel_speed = 0.0
        distance = 0.0

        if (last_txn and signal.latitude is not None and signal.longitude is not None and 
            last_txn.latitude is not None and last_txn.longitude is not None):
            
            # Distance in km
            distance = GeolocationRiskEngine.haversine_distance(
                last_txn.latitude, last_txn.longitude,
                signal.latitude, signal.longitude
            )
            
            # Time difference in hours
            from datetime import datetime, timezone
            t1 = last_txn.timestamp
            t2 = datetime.now(timezone.utc)
            
            # Standardize timezone offset info
            if t1.tzinfo is not None and t2.tzinfo is None:
                t2 = t2.replace(tzinfo=timezone.utc)
            elif t1.tzinfo is None and t2.tzinfo is not None:
                t1 = t1.replace(tzinfo=timezone.utc)
                
            time_diff_s = (t2 - t1).total_seconds()
            time_diff_h = time_diff_s / 3600.0

            if time_diff_h > 0:
                travel_speed = distance / time_diff_h

        cls._load_model()
        if cls._model is not None:
            # Model features: [is_new_location, is_city_change, is_country_change, travel_speed, distance]
            x = np.array([[is_new_location, is_city_change, is_country_change, travel_speed, distance]])
            probs = cls._model.predict_proba(x)[0]
            score = float(probs[1] * 100.0)
        else:
            score = 0.0
            
            # 1. Check if this is a new location/city for the user
            if is_new_location == 1.0:
                score += settings.GEOLOC_NEW_LOCATION_RISK

            # If there's no previous transaction history, we can't detect jumps or impossible travel
            if not last_txn:
                return min(score, 95.0)

            # 2. Check for sudden city change
            if is_city_change == 1.0:
                score += settings.GEOLOC_CITY_CHANGE_RISK

            # 3. Check for sudden country change
            if is_country_change == 1.0:
                score += settings.GEOLOC_COUNTRY_CHANGE_RISK

            # 4. Check for impossible travel speed using Haversine formula
            if travel_speed > settings.MAX_TRAVEL_SPEED_KMH:
                score += settings.GEOLOC_IMPOSSIBLE_TRAVEL_RISK

        score = min(score, 95.0)
        return round(score, 2)

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Computes great-circle distance between two GPS coordinates in kilometers.
        """
        R = 6371.0  # Earth's radius in km
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        
        return R * c

