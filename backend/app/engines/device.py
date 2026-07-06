import os
import pickle
import numpy as np
from sqlalchemy.orm import Session
from ..models.models import Device
from ..schemas.schemas import DeviceSignal
from datetime import datetime

class DeviceTrustEngine:
    _model = None

    @classmethod
    def _load_model(cls):
        if cls._model is None:
            from .training import DEVICE_MODEL_FILE
            if os.path.exists(DEVICE_MODEL_FILE):
                try:
                    with open(DEVICE_MODEL_FILE, "rb") as f:
                        cls._model = pickle.load(f)
                except Exception as e:
                    print(f"[PayShield] Error loading device model: {e}")

    @classmethod
    def calculate_risk(cls, db: Session, user_id: str, signal: DeviceSignal) -> float:
        """
        Compares incoming device fingerprints against the user's registered history.
        Returns a device risk score between 0 and 100.
        """
        # Fetch all devices registered to this user
        user_devices = db.query(Device).filter(Device.user_id == user_id).all()
        
        # Check global registrations of this device hash BEFORE committing the current session
        global_devices = db.query(Device).filter(Device.device_hash == signal.device_hash).all()
        distinct_users = {d.user_id for d in global_devices}
        
        # Check if the device exists for this user BEFORE updating it
        existing_profile = next((d for d in user_devices if d.device_hash == signal.device_hash), None)
        
        # If this is the user's very first device, register it and mark as trusted (score = 0.0)
        if not user_devices:
            new_device = Device(
                user_id=user_id,
                device_hash=signal.device_hash,
                browser=signal.browser,
                os=signal.os,
                ip_address=signal.ip_address,
                location=signal.location,
                screen_resolution=signal.screen_resolution,
                timezone=signal.timezone,
                language=signal.language,
                user_agent=signal.user_agent,
                latitude=signal.latitude,
                longitude=signal.longitude,
                city=signal.city,
                region=signal.region,
                country=signal.country,
                is_trusted=True,
                trust_score=1.0
            )
            db.add(new_device)
            db.flush()
            return 0.0
            
        # Check if the device has been blacklisted / marked as untrusted
        if existing_profile and not existing_profile.is_trusted:
            return 100.0
            
        # Extract features for model
        is_new_for_user = 1.0 if (existing_profile is None) else 0.0
        is_never_seen_globally = 1.0 if (len(distinct_users) == 0) else 0.0
        is_rare_globally = 1.0 if (len(distinct_users) <= 2) else 0.0
        has_other_users = 1.0 if any(uid != user_id for uid in distinct_users) else 0.0
        ip_mismatch = 0.0
        loc_mismatch = 0.0
        if not is_new_for_user and existing_profile:
            ip_mismatch = 1.0 if existing_profile.ip_address != signal.ip_address else 0.0
            loc_mismatch = 1.0 if existing_profile.location != signal.location else 0.0

        cls._load_model()
        score = None
        if cls._model is not None:
            try:
                # Model features: [is_new_for_user, is_never_seen_globally, is_rare_globally, has_other_users, ip_mismatch, loc_mismatch]
                x = np.array([[is_new_for_user, is_never_seen_globally, is_rare_globally, has_other_users, ip_mismatch, loc_mismatch]])
                score = float(cls._model.predict_proba(x)[0][1] * 100.0)
            except Exception as e:
                print(f"[PayShield] Device model inference failed, using heuristic: {e}")
                score = None
        if score is None:
            score = 0.0
            
            # 1. New device for user (+30 risk)
            if is_new_for_user:
                score += 30.0
                
                # 2. Device never seen globally (+20 risk)
                if is_never_seen_globally:
                    score += 20.0
                else:
                    # 3. Rare device globally (+15 risk)
                    if is_rare_globally:
                        score += 15.0
                        
            # 4. Multiple accounts sharing same device (+40 risk)
            if has_other_users:
                score += 40.0
                
            # For known devices, add IP/Location change risk if applicable
            if not is_new_for_user and existing_profile:
                if ip_mismatch and loc_mismatch:
                    score += 40.0
                elif ip_mismatch:
                    score += 10.0
                    
        # Register or update device profile in DB now
        if not existing_profile:
            new_device = Device(
                user_id=user_id,
                device_hash=signal.device_hash,
                browser=signal.browser,
                os=signal.os,
                ip_address=signal.ip_address,
                location=signal.location,
                screen_resolution=signal.screen_resolution,
                timezone=signal.timezone,
                language=signal.language,
                user_agent=signal.user_agent,
                latitude=signal.latitude,
                longitude=signal.longitude,
                city=signal.city,
                region=signal.region,
                country=signal.country,
                is_trusted=True,
                trust_score=1.0
            )
            db.add(new_device)
        else:
            existing_profile.last_seen = datetime.now()
            existing_profile.ip_address = signal.ip_address
            existing_profile.location = signal.location
            existing_profile.screen_resolution = signal.screen_resolution
            existing_profile.timezone = signal.timezone
            existing_profile.language = signal.language
            existing_profile.user_agent = signal.user_agent
            existing_profile.latitude = signal.latitude
            existing_profile.longitude = signal.longitude
            existing_profile.city = signal.city
            existing_profile.region = signal.region
            existing_profile.country = signal.country
            
        db.flush()
        score = min(score, 95.0)
        return round(score, 2)


