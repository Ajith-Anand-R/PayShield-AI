import os
import pytest
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.models import User, Device, BehaviorProfile, Transaction
from app.schemas.schemas import BehaviorSignal, DeviceSignal, TransactionScoreRequest
from app.main import app
from fastapi.testclient import TestClient

# Set up in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


import numpy as np
from app.engines.behavioral import BehavioralEngine
from app.engines.device import DeviceTrustEngine
from app.engines.geolocation import GeolocationRiskEngine
from app.engines.anomaly import TransactionAnomalyEngine
from app.engines.graph import FraudGraphEngine
from app.services.fusion import RiskFusionEngine


class MockBehavioralModel:
    def predict_proba(self, X):
        is_bot = X[0][5]
        prob = 0.98 if is_bot == 1.0 else 0.10
        return np.array([[1.0 - prob, prob]])


class MockDeviceModel:
    def predict_proba(self, X):
        is_new = X[0][0]
        has_other = X[0][3]
        if has_other == 1.0:
            prob = 0.85
        elif is_new == 1.0:
            prob = 0.50
        else:
            prob = 0.10
        return np.array([[1.0 - prob, prob]])


class MockGeolocationModel:
    def predict_proba(self, X):
        distance = X[0][4]
        prob = 0.85 if distance > 1000.0 else (0.40 if distance > 10.0 else 0.10)
        return np.array([[1.0 - prob, prob]])


class MockAnomalyModel:
    def predict_proba(self, X):
        amount_ratio = X[0][0]
        prob = 0.75 if amount_ratio > 10.0 else 0.15
        return np.array([[1.0 - prob, prob]])


class MockGraphModel:
    def predict_proba(self, X):
        dist = X[0][0]
        shared = X[0][6]
        prob = 0.85 if (dist > 0.0 or shared > 0.0) else 0.10
        return np.array([[1.0 - prob, prob]])


class MockFusionModel:
    def predict_proba(self, X):
        behav, device, geo, anomaly, graph = X[0][0], X[0][1], X[0][2], X[0][3], X[0][4]
        if device > 80.0 and geo > 80.0 and graph > 80.0:
            prob = 0.90
        elif behav > 90.0 and anomaly > 70.0:
            prob = 0.70
        elif device > 40.0:
            prob = 0.38
        else:
            prob = 0.15
        return np.array([[1.0 - prob, prob]])

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

def test_canonical_scenarios(db_session):
    # Override database dependency in app
    app.dependency_overrides[get_db] = lambda: db_session

    # Wire Mock Models to exercise real ML path with controlled outputs
    BehavioralEngine._model = MockBehavioralModel()
    DeviceTrustEngine._model = MockDeviceModel()
    GeolocationRiskEngine._model = MockGeolocationModel()
    TransactionAnomalyEngine._model = MockAnomalyModel()
    FraudGraphEngine._model = MockGraphModel()
    RiskFusionEngine._model = MockFusionModel()

    try:
        client = TestClient(app)

        # 1. Create a safe user and seed their baseline
        user_safe = User(id="user_safe", username="safe_user", is_fraudster=False)
        db_session.add(user_safe)
        
        # Seed safe user's baseline behavior
        behav_base = BehaviorProfile(
            user_id="user_safe",
            keystroke_dwell_avg=0.10,
            keystroke_flight_avg=0.15,
            mouse_speed_avg=200.0,
            mouse_jitter_avg=10.0,
            scroll_velocity_avg=50.0
        )
        db_session.add(behav_base)
        
        # Seed safe user's registered safe device
        device_safe = Device(
            user_id="user_safe",
            device_hash="device_safe_hash",
            browser="Chrome",
            os="macOS",
            ip_address="192.168.1.100",
            location="San Francisco, USA",
            city="San Francisco",
            country="USA",
            is_trusted=True
        )
        db_session.add(device_safe)
        
        # Seed previous transaction in San Francisco
        tx_prev = Transaction(
            id="tx_prev_id",
            user_id="user_safe",
            amount=50.0,
            target_account="acc_merchant_1",
            device_hash="device_safe_hash",
            location="San Francisco, USA",
            latitude=37.7749,
            longitude=-122.4194,
            city="San Francisco",
            country="USA",
            status="ALLOW",
            timestamp=datetime.now() - timedelta(hours=2)
        )
        db_session.add(tx_prev)
        db_session.commit()

        # --- Scenario 1: Safe Payment ---
        # Inputs: known device, normal amount, baseline behavior, familiar geo
        req_safe = {
            "user_id": "user_safe",
            "session_id": "session_safe",
            "amount": 45.0,
            "target_account": "acc_merchant_1",
            "channel": "UPI",
            "currency": "INR",
            "remarks": "Grocery shopping",
            "device": {
                "device_hash": "device_safe_hash",
                "browser": "Chrome",
                "os": "macOS",
                "ip_address": "192.168.1.100",
                "location": "San Francisco, USA",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "city": "San Francisco",
                "country": "USA"
            },
            "behavior": {
                "keystroke_dwell": 0.10,
                "keystroke_flight": 0.15,
                "mouse_speed": 200.0,
                "mouse_jitter": 10.0,
                "scroll_velocity": 50.0
            }
        }
        resp_safe = client.post("/api/transaction/score", json=req_safe)
        assert resp_safe.status_code == 200
        data_safe = resp_safe.json()
        assert data_safe["decision"] == "ALLOW"
        assert data_safe["risk_score"] < 30.0

        # --- Scenario 2: Device/Identity Drift ---
        # Inputs: new device, IP+city change, mild behavior drift
        req_drift = {
            "user_id": "user_safe",
            "session_id": "session_drift",
            "amount": 80.0,
            "target_account": "acc_merchant_1",
            "channel": "UPI",
            "currency": "INR",
            "remarks": "Gym subscription",
            "device": {
                "device_hash": "device_new_hash",  # new device hash
                "browser": "Safari",
                "os": "macOS",
                "ip_address": "192.168.2.150",     # minor IP subnet shift
                "location": "Oakland, USA",        # city change
                "latitude": 37.8044,
                "longitude": -122.2712,
                "city": "Oakland",
                "country": "USA"
            },
            "behavior": {
                "keystroke_dwell": 0.12,           # mild behavioral drift
                "keystroke_flight": 0.18,
                "mouse_speed": 180.0,
                "mouse_jitter": 8.0,
                "scroll_velocity": 45.0
            }
        }
        resp_drift = client.post("/api/transaction/score", json=req_drift)
        assert resp_drift.status_code == 200
        data_drift = resp_drift.json()
        assert data_drift["decision"] == "STEP_UP"
        assert 30.0 <= data_drift["risk_score"] < 55.0

        # --- Scenario 3: Bot / Midnight Anomaly ---
        # Inputs: 3AM, extreme amount, zero mouse jitter (bot), velocity burst
        # Wait, the timestamp in score_transaction uses datetime.now() inside api.py
        # To simulate 3AM, we can score it, but let's make sure the bot signals and extreme amount are high enough.
        req_bot = {
            "user_id": "user_safe",
            "session_id": "session_bot",
            "amount": 9000.0,                      # extreme amount (user average is ~50)
            "target_account": "acc_unknown_target",
            "channel": "UPI",
            "currency": "INR",
            "remarks": "Urgent transfer",
            "device": {
                "device_hash": "device_safe_hash",
                "browser": "Chrome",
                "os": "macOS",
                "ip_address": "192.168.1.100",
                "location": "San Francisco, USA",
                "latitude": 37.7749,
                "longitude": -122.4194,
                "city": "San Francisco",
                "country": "USA"
            },
            "behavior": {
                "keystroke_dwell": 0.10,
                "keystroke_flight": 0.15,
                "mouse_speed": 200.0,
                "mouse_jitter": 0.0,               # Bot pattern (zero mouse jitter)
                "scroll_velocity": 50.0
            }
        }
        # Simulate velocity burst by executing a few quick requests or just letting the bot scoring trigger it
        # Actually, let's first score to check.
        resp_bot = client.post("/api/transaction/score", json=req_bot)
        assert resp_bot.status_code == 200
        data_bot = resp_bot.json()
        assert data_bot["decision"] in ["REVIEW", "BLOCK"]
        assert data_bot["risk_score"] >= 55.0

        # --- Scenario 4: Fraud Ring / Mule ---
        # Inputs: device shared with known fraudster + scam remark + impossible travel
        # 1. Create a fraudster user
        user_fraud = User(id="user_fraudster", username="fraud_user", is_fraudster=True)
        db_session.add(user_fraud)
        
        # 2. Register shared device to fraudster
        device_fraud = Device(
            user_id="user_fraudster",
            device_hash="device_shared_malicious",
            browser="Firefox",
            os="Linux",
            ip_address="10.0.0.1",
            location="Unknown",
            is_trusted=True
        )
        db_session.add(device_fraud)
        db_session.commit()
        
        # Sync the graph so it knows about the fraudster node and the device linkage
        FraudGraphEngine.sync_graph_from_db(db_session)

        # 3. Safe user tries to do transaction using the shared malicious device
        # from London (impossible travel hop from San Francisco in 5 mins), with scam remark
        req_fraud_ring = {
            "user_id": "user_safe",
            "session_id": "session_mule",
            "amount": 250.0,
            "target_account": "acc_mule_recipient",
            "channel": "UPI",
            "currency": "INR",
            "remarks": "support helpline refund prize money call now", # Scam remark
            "device": {
                "device_hash": "device_shared_malicious",
                "browser": "Firefox",
                "os": "Linux",
                "ip_address": "80.80.80.80",
                "location": "London, UK",           # Geolocation jump from San Francisco
                "latitude": 51.5074,
                "longitude": -0.1278,
                "city": "London",
                "country": "UK"
            },
            "behavior": {
                "keystroke_dwell": 0.10,
                "keystroke_flight": 0.15,
                "mouse_speed": 200.0,
                "mouse_jitter": 10.0,
                "scroll_velocity": 50.0
            }
        }
        resp_fraud = client.post("/api/transaction/score", json=req_fraud_ring)
        assert resp_fraud.status_code == 200
        data_fraud = resp_fraud.json()
        assert data_fraud["decision"] == "BLOCK"
        assert data_fraud["risk_score"] >= 80.0

    finally:
        app.dependency_overrides.clear()
        BehavioralEngine._model = None
        DeviceTrustEngine._model = None
        GeolocationRiskEngine._model = None
        TransactionAnomalyEngine._model = None
        FraudGraphEngine._model = None
        RiskFusionEngine._model = None


def test_metrics_endpoints(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        from app.models.models import ModelRegistry, Transaction
        db_session.add(ModelRegistry(
            model_name="behavioral",
            version="1.0.0",
            metrics_json='{"precision": 0.92, "recall": 0.88}',
            is_active=True,
            artifact_path="behavioral_model.pkl"
        ))
        db_session.add(Transaction(
            id="tx_latency_test",
            user_id="user_safe",
            amount=100.0,
            status="ALLOW",
            latency_ms=12.5
        ))
        db_session.commit()
        
        client = TestClient(app)
        
        resp = client.get("/api/model/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "behavioral" in data
        assert data["behavioral"]["metrics"]["precision"] == 0.92
        
        resp_lat = client.get("/api/metrics/latency")
        assert resp_lat.status_code == 200
        data_lat = resp_lat.json()
        assert data_lat["p50"] == 12.5
        assert data_lat["count"] == 1
    finally:
        app.dependency_overrides.clear()


# ── Phase 5 tests ──────────────────────────────────────────────────────────────

def test_health_endpoint(db_session):
    """GET /health must return 200 and {"status": "ok"} unconditionally."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
    finally:
        app.dependency_overrides.clear()


def test_ready_endpoint(db_session):
    """GET /ready must return a dict with a 'components' key."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        resp = client.get("/ready")
        # Either 200 (all ok) or 503 (degraded) — shape must be correct regardless.
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "status" in body
        assert "components" in body
        assert "database" in body["components"]
    finally:
        app.dependency_overrides.clear()


def test_scoring_requires_api_key(db_session):
    """
    When AUTH_ENABLED=True, POST /api/scoring/transaction/score without
    X-API-Key must return 401.
    """
    import app.config as cfg_module
    original = cfg_module.settings.AUTH_ENABLED
    cfg_module.settings.AUTH_ENABLED = True

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app, raise_server_exceptions=False)

        req_body = {
            "user_id": "user_auth_test",
            "amount": 100.0,
            "currency": "INR",
            "channel": "UPI",
            "target_account": "target_001",
            "device": {
                "device_hash": "hash_auth",
                "browser": "Chrome",
                "os": "Windows",
                "ip_address": "10.0.0.1",
                "location": "Delhi"
            },
            "behavior": {
                "keystroke_dwell": 0.10,
                "keystroke_flight": 0.15,
                "mouse_speed": 250.0,
                "mouse_jitter": 12.0,
                "scroll_velocity": 80.0
            }
        }
        resp = client.post("/api/scoring/transaction/score", json=req_body)
        assert resp.status_code == 401, (
            f"Expected 401 when AUTH_ENABLED=True and no key provided, got {resp.status_code}"
        )
    finally:
        cfg_module.settings.AUTH_ENABLED = original
        app.dependency_overrides.clear()
