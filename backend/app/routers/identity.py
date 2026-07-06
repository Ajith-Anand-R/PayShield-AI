"""
Identity router — auth, device fingerprinting, behaviour capture, session.

Prefix: /api/identity  (mounted in main.py; old /api/* paths are preserved
via the legacy router in routes/api.py which remains registered for backward
compatibility during the Phase-4 migration window).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models import models
from ..schemas import schemas

router = APIRouter(prefix="/api/identity", tags=["identity"])


@router.post("/auth/register", response_model=schemas.UserResponse)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user identity."""
    db_user = db.query(models.User).filter(models.User.id == user_data.id).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User already registered")
    db_user = models.User(
        id=user_data.id,
        username=user_data.username,
        is_fraudster=user_data.is_fraudster
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/auth/login", response_model=schemas.UserResponse)
def login(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    """Authenticate a user (demo — no password hashing yet)."""
    db_user = db.query(models.User).filter(models.User.id == user_data.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.post("/device/register", response_model=schemas.DeviceResponse)
def register_device(device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    """Register or refresh a device fingerprint for a user."""
    db_device = db.query(models.Device).filter(
        models.Device.user_id == device.user_id,
        models.Device.device_hash == device.device_hash
    ).first()

    if not db_device:
        db_device = models.Device(
            user_id=device.user_id,
            device_hash=device.device_hash,
            browser=device.browser,
            os=device.os,
            ip_address=device.ip_address,
            location=device.location,
            screen_resolution=device.screen_resolution,
            timezone=device.timezone,
            language=device.language,
            user_agent=device.user_agent,
            latitude=device.latitude,
            longitude=device.longitude,
            city=device.city,
            region=device.region,
            country=device.country,
            is_trusted=True,
            trust_score=1.0
        )
        db.add(db_device)
    else:
        db_device.last_seen = datetime.now()
        db_device.ip_address = device.ip_address
        db_device.location = device.location
        db_device.screen_resolution = device.screen_resolution
        db_device.timezone = device.timezone
        db_device.language = device.language
        db_device.user_agent = device.user_agent
        db_device.latitude = device.latitude
        db_device.longitude = device.longitude
        db_device.city = device.city
        db_device.region = device.region
        db_device.country = device.country

    db.commit()
    db.refresh(db_device)
    return db_device


@router.post("/behavior/capture", response_model=schemas.BehaviorProfileResponse)
def capture_behavior(behavior: schemas.BehaviorCapture, db: Session = Depends(get_db)):
    """Upsert biometric behaviour baseline for a user."""
    profile = (
        db.query(models.BehaviorProfile)
        .filter(models.BehaviorProfile.user_id == behavior.user_id)
        .first()
    )
    if not profile:
        profile = models.BehaviorProfile(
            user_id=behavior.user_id,
            keystroke_dwell_avg=behavior.keystroke_dwell_avg,
            keystroke_flight_avg=behavior.keystroke_flight_avg,
            mouse_speed_avg=behavior.mouse_speed_avg,
            mouse_jitter_avg=behavior.mouse_jitter_avg,
            scroll_velocity_avg=behavior.scroll_velocity_avg
        )
        db.add(profile)
    else:
        profile.keystroke_dwell_avg = behavior.keystroke_dwell_avg
        profile.keystroke_flight_avg = behavior.keystroke_flight_avg
        profile.mouse_speed_avg = behavior.mouse_speed_avg
        profile.mouse_jitter_avg = behavior.mouse_jitter_avg
        profile.scroll_velocity_avg = behavior.scroll_velocity_avg

    db.commit()
    db.refresh(profile)
    return profile


@router.post("/session/start", response_model=schemas.SessionStartResponse)
def start_session(req: schemas.SessionStartRequest, db: Session = Depends(get_db)):
    """Start a new user session with geo and device trust checks."""
    import uuid
    session_id = str(uuid.uuid4())
    risk_flags: list[str] = []

    device = db.query(models.Device).filter(
        models.Device.user_id == req.user_id,
        models.Device.device_hash == req.device_fingerprint
    ).first()

    device_known = device is not None and device.is_trusted
    if not device_known:
        risk_flags.append("new_device")

    from ..services.redis_client import get_last_ip, set_last_ip
    last_ip = get_last_ip(req.user_id)
    geo_match = True
    if last_ip and last_ip.split(".")[:2] != req.ip_address.split(".")[:2]:
        geo_match = False
        risk_flags.append("ip_change")

    db_session = models.Session(
        id=session_id,
        user_id=req.user_id,
        device_id=device.id if device else None,
        ip_address=req.ip_address,
        started_at=datetime.now()
    )
    db.add(db_session)
    db.commit()
    set_last_ip(req.user_id, req.ip_address)

    return schemas.SessionStartResponse(
        session_id=session_id,
        device_known=device_known,
        device_trust_score=1.0 if device_known else 0.2,
        geo_match=geo_match,
        risk_flags=risk_flags
    )
