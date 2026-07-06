import asyncio
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Disable rate limit and authentication environment variables
os.environ["REDIS_URL"] = "memory://"
os.environ["AUTH_ENABLED"] = "true"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

from app.main import app
from app.database import SessionLocal, engine
from app.models.models import User, Device, BehaviorProfile, ApiClient
import hashlib
import uuid

# Seeding
db = SessionLocal()
try:
    user = db.query(User).filter(User.id == "user_profile_test").first()
    if not user:
        user = User(id="user_profile_test", username="profiler", is_fraudster=False)
        db.add(user)
        db.commit()
    profile = db.query(BehaviorProfile).filter(BehaviorProfile.user_id == "user_profile_test").first()
    if not profile:
        profile = BehaviorProfile(
            user_id="user_profile_test",
            keystroke_dwell_avg=0.10, keystroke_flight_avg=0.15,
            mouse_speed_avg=220.0, mouse_jitter_avg=10.0, scroll_velocity_avg=50.0
        )
        db.add(profile)
        db.commit()
    device = db.query(Device).filter(Device.user_id == "user_profile_test", Device.device_hash == "dev_profile_hash").first()
    if not device:
        device = Device(
            user_id="user_profile_test", device_hash="dev_profile_hash",
            browser="Chrome", os="Windows", ip_address="127.0.0.1", location="Chennai, IN",
            city="Chennai", country="IN", is_trusted=True, trust_score=1.0
        )
        db.add(device)
        db.commit()
    api_client = db.query(ApiClient).filter(ApiClient.name == "default-dev").first()
    if not api_client:
        api_client = ApiClient(
            id=str(uuid.uuid4()), name="default-dev",
            api_key_hash=hashlib.sha256("dev-secret".encode()).hexdigest(),
            is_active=True, rate_limit_per_min=1000000
        )
        db.add(api_client)
        db.commit()
finally:
    db.close()

from app.schemas.schemas import TransactionScoreRequest, DeviceSignal, BehaviorSignal
from fastapi import BackgroundTasks

req = TransactionScoreRequest(
    user_id="user_profile_test",
    session_id="session_profile_test",
    amount=50.0,
    target_account="recipient_profile_test",
    device=DeviceSignal(
        device_hash="dev_profile_hash", browser="Chrome", os="Windows",
        ip_address="127.0.0.1", location="Chennai, IN",
        latitude=13.0827, longitude=80.2707, city="Chennai", country="IN"
    ),
    behavior=BehaviorSignal(
        keystroke_dwell=0.10, keystroke_flight=0.15,
        mouse_speed=220.0, mouse_jitter=10.0, scroll_velocity=50.0
    )
)

async def profile_request():
    from app.routers.scoring import _run_scoring_pipeline
    db = SessionLocal()
    bg_tasks = BackgroundTasks()
    
    print("[Profile] Starting request profile...")
    t0 = time.perf_counter()
    
    # Let's time individual sections of _run_scoring_pipeline by copying its steps
    # or just calling it after warming up.
    # Warmup
    print("Warming up models...")
    await _run_scoring_pipeline(req, bg_tasks, db)
    print("Warmup done.")
    
    # Actual timed run
    t_start = time.perf_counter()
    
    t_step = time.perf_counter()
    user = db.query(User).filter(User.id == req.user_id).first()
    print(f"User query: {(time.perf_counter() - t_step)*1000.0:.2f} ms")
    
    t_step = time.perf_counter()
    # 1. Behavioral
    from app.engines.behavioral import BehavioralEngine
    BehavioralEngine.calculate_risk(db, req.user_id, req.behavior)
    print(f"BehavioralEngine: {(time.perf_counter() - t_step)*1000.0:.2f} ms")
    
    t_step = time.perf_counter()
    # 2. Device
    from app.engines.device import DeviceTrustEngine
    DeviceTrustEngine.calculate_risk(db, req.user_id, req.device)
    print(f"DeviceTrustEngine: {(time.perf_counter() - t_step)*1000.0:.2f} ms")
    
    t_step = time.perf_counter()
    # 3. Geolocation
    from app.engines.geolocation import GeolocationRiskEngine
    GeolocationRiskEngine.calculate_risk(db, req.user_id, req.device)
    print(f"GeolocationRiskEngine: {(time.perf_counter() - t_step)*1000.0:.2f} ms")
    
    t_step = time.perf_counter()
    # 4. Anomaly
    from app.engines.anomaly import TransactionAnomalyEngine
    TransactionAnomalyEngine.calculate_risk(db, req.user_id, req.amount, req.device.location)
    print(f"TransactionAnomalyEngine: {(time.perf_counter() - t_step)*1000.0:.2f} ms")
    
    t_step = time.perf_counter()
    # 5. Graph
    from app.engines.graph import FraudGraphEngine
    FraudGraphEngine.calculate_risk(db, req.user_id, req.device.device_hash, req.target_account)
    print(f"FraudGraphEngine: {(time.perf_counter() - t_step)*1000.0:.2f} ms")
    
    t_step = time.perf_counter()
    # 6. Scam detector
    from app.services.scam_detector import ScamDetectorService
    ScamDetectorService.analyze_remarks(req.remarks)
    print(f"ScamDetectorService: {(time.perf_counter() - t_step)*1000.0:.2f} ms")
    
    t_step = time.perf_counter()
    # 7. Commit
    db.commit()
    print(f"DB commit: {(time.perf_counter() - t_step)*1000.0:.2f} ms")
    
    total = (time.perf_counter() - t_start)*1000.0
    print(f"Total step-by-step time: {total:.2f} ms")
    db.close()

if __name__ == "__main__":
    asyncio.run(profile_request())
