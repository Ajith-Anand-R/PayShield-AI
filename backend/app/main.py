from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from .config import settings
from .routes.api import router, _internal_score
from .engines.anomaly import TransactionAnomalyEngine
from .engines.graph import FraudGraphEngine
from .services.stream_generator import stream_generator
from .models import models

# Create database tables
Base.metadata.create_all(bind=engine)


def _auto_seed_if_empty():
    """Seed the database with baseline data if it's empty (first run)."""
    db = SessionLocal()
    try:
        user_count = db.query(models.User).count()
        if user_count > 0:
            print(f"[PayShield] Database has {user_count} users — skipping seed.")
            return False

        print("[PayShield] Empty database detected — running auto-seed...")

        # Core users
        core_users = [
            models.User(id="user_alice", username="alice_chennai", is_fraudster=False),
            models.User(id="user_bob", username="bob_mumbai", is_fraudster=False),
            models.User(id="user_charlie", username="charlie_delhi", is_fraudster=False),
            models.User(id="user_diana", username="diana_hyderabad", is_fraudster=False),
            models.User(id="user_eve", username="eve_kolkata", is_fraudster=False),
            models.User(id="user_frank", username="frank_ahmedabad", is_fraudster=False),
            models.User(id="user_grace", username="grace_jaipur", is_fraudster=False),
            models.User(id="user_henry", username="henry_lucknow", is_fraudster=False),
            models.User(id="user_iris", username="iris_kochi", is_fraudster=False),
            models.User(id="user_jake", username="jake_chandigarh", is_fraudster=False),
            models.User(id="user_mallory", username="mallory_fraud", is_fraudster=True),
            models.User(id="user_mule", username="mule_account", is_fraudster=False),
            models.User(id="user_ring_member", username="ring_member_acct", is_fraudster=False),
        ]
        for u in core_users:
            db.add(u)

        # Ring users
        for uid in ["user_ring_a", "user_ring_b", "user_ring_c", "user_ring_d"]:
            db.add(models.User(id=uid, username=f"{uid}_acct", is_fraudster=False))
        for uid in ["user_sender_1", "user_sender_2"]:
            db.add(models.User(id=uid, username=f"{uid}_acct", is_fraudster=False))

        db.commit()

        # Behavior profiles for all main users
        profiles = [
            ("user_alice", 0.10, 0.15, 250.0, 12.0, 80.0),
            ("user_bob", 0.12, 0.18, 200.0, 10.0, 70.0),
            ("user_charlie", 0.09, 0.13, 280.0, 15.0, 90.0),
            ("user_diana", 0.11, 0.16, 220.0, 9.0, 65.0),
            ("user_eve", 0.13, 0.20, 190.0, 11.0, 75.0),
            ("user_frank", 0.10, 0.14, 260.0, 13.0, 85.0),
            ("user_grace", 0.08, 0.12, 300.0, 14.0, 95.0),
            ("user_henry", 0.14, 0.22, 170.0, 8.0, 60.0),
            ("user_iris", 0.10, 0.15, 240.0, 11.0, 78.0),
            ("user_jake", 0.11, 0.17, 210.0, 10.0, 72.0),
        ]
        for uid, dwell, flight, speed, jitter, scroll in profiles:
            db.add(models.BehaviorProfile(
                user_id=uid, keystroke_dwell_avg=dwell, keystroke_flight_avg=flight,
                mouse_speed_avg=speed, mouse_jitter_avg=jitter, scroll_velocity_avg=scroll
            ))

        db.commit()

        # Devices
        devices = [
            ("user_alice", "device_alice_macbook", "Chrome", "macOS", "192.168.1.50", "Chennai, IN", True),
            ("user_bob", "device_bob_windows", "Firefox", "Windows", "192.168.1.75", "Mumbai, IN", True),
            ("user_charlie", "device_charlie_android", "Chrome", "Android", "192.168.2.10", "Delhi, IN", True),
            ("user_diana", "device_diana_iphone", "Safari", "iOS", "192.168.3.20", "Hyderabad, IN", True),
            ("user_eve", "device_eve_windows", "Edge", "Windows", "192.168.4.30", "Kolkata, IN", True),
            ("user_frank", "device_frank_mac", "Firefox", "macOS", "192.168.5.40", "Ahmedabad, IN", True),
            ("user_grace", "device_grace_android", "Chrome", "Android", "192.168.6.50", "Jaipur, IN", True),
            ("user_henry", "device_henry_windows", "Chrome", "Windows", "192.168.7.60", "Lucknow, IN", True),
            ("user_iris", "device_iris_mac", "Safari", "macOS", "192.168.8.70", "Kochi, IN", True),
            ("user_jake", "device_jake_linux", "Firefox", "Linux", "192.168.9.80", "Chandigarh, IN", True),
            ("user_mallory", "device_compromised_root", "Opera", "Linux", "203.0.113.12", "Unknown", False),
        ]
        for uid, dhash, browser, os_name, ip, loc, trusted in devices:
            db.add(models.Device(
                user_id=uid, device_hash=dhash, browser=browser, os=os_name,
                ip_address=ip, location=loc, is_trusted=trusted
            ))

        # Ring member devices (compromised)
        for uid in ["user_ring_a", "user_ring_b", "user_ring_c", "user_ring_d", "user_ring_member"]:
            db.add(models.Device(
                user_id=uid, device_hash="device_compromised_root",
                browser="Chrome", os="Android", ip_address="203.0.113.50",
                location="Unknown", is_trusted=False
            ))

        db.commit()

        # Historical transactions for ML training
        from datetime import timedelta, datetime as dt
        base_time = dt.now() - timedelta(days=30)
        for i in range(50):
            timestamp = base_time + timedelta(hours=i * 12)
            tx = models.Transaction(
                id=f"tx_alice_seed_{i}", user_id="user_alice",
                amount=7500.0 + (i % 5) * 500.0, timestamp=timestamp,
                target_account=f"acc_vendor_{i % 3}", device_hash="device_alice_macbook",
                location="Chennai, IN", channel="UPI", currency="INR", status="ALLOWED"
            )
            db.add(tx)
            db.add(models.RiskScore(
                transaction_id=tx.id, behavioral_score=5.0, device_score=0.0,
                anomaly_score=10.0, graph_score=0.0, total_score=4.5
            ))

        # Mule network transactions
        ring_users = ["user_ring_a", "user_ring_b", "user_ring_c", "user_ring_d"]
        inbound_senders = ring_users + ["user_bob", "user_sender_1", "user_sender_2"]
        for idx, sender in enumerate(inbound_senders):
            db.add(models.Transaction(
                id=f"tx_mule_in_{idx}", user_id=sender,
                amount=1200.0 + idx * 150.0, target_account="user_mule",
                device_hash=f"device_{sender}_phone", location="Delhi, IN",
                channel="UPI", currency="INR", status="ALLOWED"
            ))

        db.commit()
        return True
    except Exception as e:
        print(f"[PayShield] Auto-seed error: {e}")
        db.rollback()
        return False
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages startup and shutdown lifecycle."""
    print("[PayShield] Starting up...")

    # Auto-seed if database is empty
    _auto_seed_if_empty()

    # Train ML and sync graph
    db = SessionLocal()
    try:
        TransactionAnomalyEngine.train_model(db)
        print("[PayShield] ML Anomaly engine trained and ready.")
        FraudGraphEngine.load_graph()
        FraudGraphEngine.sync_graph_from_db(db)
        print("[PayShield] Fraud graph synced.")
    except Exception as e:
        print(f"[PayShield] Engine init error: {e}")
    finally:
        db.close()

    # Auto-start the real-time transaction stream
    stream_generator.start(_internal_score)
    print("[PayShield] Live transaction stream auto-started.")

    yield  # App is running

    # Shutdown
    stream_generator.stop()
    print("[PayShield] Shut down complete.")


app = FastAPI(
    title="PayShield: Real-Time Payment Authorization Risk Middleware",
    description="Fuses Behavioral DNA, Device Trust, ML Anomaly, and Graph intelligence to stop fraud.",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "PayShield Risk Middleware",
        "version": "2.0.0 — Live Stream Mode",
        "stream": stream_generator.get_status().model_dump(),
        "thresholds": {
            "allow": settings.THRESH_ALLOW,
            "step_up": settings.THRESH_STEP_UP,
            "delay": settings.THRESH_DELAY
        }
    }
