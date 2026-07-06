import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from app.database import Base
from app.models.models import User, Device, BehaviorProfile, Transaction, GraphEdge, RiskScore
from app.schemas.schemas import BehaviorSignal, DeviceSignal, TransactionScoreRequest, RiskScoreResponse
from app.engines.behavioral import BehavioralEngine
from app.engines.device import DeviceTrustEngine
from app.engines.anomaly import TransactionAnomalyEngine
from app.engines.graph import FraudGraphEngine
from app.engines.geolocation import GeolocationRiskEngine
from app.services.fusion import RiskFusionEngine

from sqlalchemy.pool import StaticPool

os.environ.setdefault("REDIS_URL", "memory://")

# Set up in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class MockModel:
    def __init__(self, proba_class_1):
        self.proba_class_1 = proba_class_1
        
    def predict_proba(self, X):
        import numpy as np
        return np.array([[1.0 - self.proba_class_1, self.proba_class_1]] * len(X))


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)




def test_behavioral_engine(db_session):
    BehavioralEngine._model = None
    # 1. Create a user
    user = User(id="user_test_1", username="test_user_1", is_fraudster=False)
    db_session.add(user)
    db_session.commit()

    # 2. Score first time (should seed profile and return 0.0)
    sig_seed = BehaviorSignal(
        keystroke_dwell=0.10,
        keystroke_flight=0.15,
        mouse_speed=200.0,
        mouse_jitter=10.0,
        scroll_velocity=50.0
    )
    score1 = BehavioralEngine.calculate_risk(db_session, "user_test_1", sig_seed)
    assert score1 == 0.0

    # Verify profile was created
    profile = db_session.query(BehaviorProfile).filter(BehaviorProfile.user_id == "user_test_1").first()
    assert profile is not None
    assert profile.keystroke_dwell_avg == 0.10

    # 3. Match closely (small variation)
    sig_close = BehaviorSignal(
        keystroke_dwell=0.11,
        keystroke_flight=0.14,
        mouse_speed=190.0,
        mouse_jitter=9.5,
        scroll_velocity=48.0
    )
    score_close = BehavioralEngine.calculate_risk(db_session, "user_test_1", sig_close)
    assert score_close < 20.0

    # 4. Deviate widely (compromised behavioral DNA)
    sig_deviate = BehaviorSignal(
        keystroke_dwell=0.55,  # 450% dwell mutation
        keystroke_flight=0.95,
        mouse_speed=10.0,
        mouse_jitter=1.0,
        scroll_velocity=5.0
    )
    score_deviate = BehavioralEngine.calculate_risk(db_session, "user_test_1", sig_deviate)
    assert score_deviate > 60.0

    # 5. Bot pattern (mouse speed but zero mouse jitter)
    sig_bot = BehaviorSignal(
        keystroke_dwell=0.10,
        keystroke_flight=0.15,
        mouse_speed=200.0,
        mouse_jitter=0.0,  # PERFECT uniformity/automation
        scroll_velocity=50.0
    )
    score_bot = BehavioralEngine.calculate_risk(db_session, "user_test_1", sig_bot)
    assert score_bot >= 95.0

def test_device_trust_engine(db_session):
    DeviceTrustEngine._model = None
    user = User(id="user_test_2", username="test_user_2", is_fraudster=False)
    db_session.add(user)
    db_session.commit()

    sig_register = DeviceSignal(
        device_hash="device_trusted_1",
        browser="Chrome",
        os="macOS",
        ip_address="192.168.1.100",
        location="San Francisco, USA"
    )
    
    # First device should register and return 0
    score_reg = DeviceTrustEngine.calculate_risk(db_session, "user_test_2", sig_register)
    assert score_reg == 0.0

    # Exact device match
    score_exact = DeviceTrustEngine.calculate_risk(db_session, "user_test_2", sig_register)
    assert score_exact == 0.0

    # Same device, different location / IP (dynamic IP subnet shift)
    sig_ip_shift = DeviceSignal(
        device_hash="device_trusted_1",
        browser="Chrome",
        os="macOS",
        ip_address="192.168.1.201",  # modified IP
        location="San Francisco, USA"
    )
    score_ip_shift = DeviceTrustEngine.calculate_risk(db_session, "user_test_2", sig_ip_shift)
    assert score_ip_shift == 10.0

    # Completely new device (should trigger warning score)
    sig_new_device = DeviceSignal(
        device_hash="device_unknown_laptop",
        browser="Safari",
        os="iOS",
        ip_address="203.0.113.88",
        location="London, UK"
    )
    score_new = DeviceTrustEngine.calculate_risk(db_session, "user_test_2", sig_new_device)
    assert score_new == 50.0  # New device for user (+30) + never seen globally (+20)

    # Let's add a second user who shares the first device (device_trusted_1)
    user2 = User(id="user_test_2b", username="test_user_2b", is_fraudster=False)
    db_session.add(user2)
    db_session.commit()

    # user_test_2b's first device is device_trusted_1.
    # Since it's their very first device, they get 0.0 risk score
    score_shared_first = DeviceTrustEngine.calculate_risk(db_session, "user_test_2b", sig_register)
    assert score_shared_first == 0.0

    # Let's add a third user who also tries to use device_trusted_1 as a new device
    user3 = User(id="user_test_2c", username="test_user_2c", is_fraudster=False)
    db_session.add(user3)
    db_session.commit()

    # Now let's register another device first for user3, so device_trusted_1 is NOT their first device.
    sig_dummy = DeviceSignal(
        device_hash="user3_dummy",
        browser="Chrome",
        os="Windows",
        ip_address="192.168.1.5",
        location="San Francisco, USA"
    )
    assert DeviceTrustEngine.calculate_risk(db_session, "user_test_2c", sig_dummy) == 0.0

    # Now user3 registers device_trusted_1 (which is shared by user_test_2 and user_test_2b)
    # - New device for user (+30)
    # - Not never seen globally (+0)
    # - Rare device globally (+15)
    # - Multiple accounts sharing same device (+40)
    # - Total risk = 30 + 15 + 40 = 85.0
    score_shared_new = DeviceTrustEngine.calculate_risk(db_session, "user_test_2c", sig_register)
    assert score_shared_new == 85.0

def test_anomaly_engine(db_session):
    TransactionAnomalyEngine._model = None
    # Delegates to the unified calibrated training pipeline (single source of truth)
    TransactionAnomalyEngine.train_model(db_session)
    
    # Calculate score for normal amount
    score_normal, _ = TransactionAnomalyEngine.calculate_risk(db_session, "user_test_3", 50.0, "Home")
    
    # Calculate score for massive amount
    score_high, _ = TransactionAnomalyEngine.calculate_risk(db_session, "user_test_3", 15000.0, "London")
    
    assert score_high > score_normal

def test_fraud_graph_engine(db_session):
    FraudGraphEngine._model = None
    # 1. Add normal user and fraudster user
    normal = User(id="user_norm", username="normal_user", is_fraudster=False)
    fraudster = User(id="user_fraud", username="fraudster_user", is_fraudster=True)
    db_session.add(normal)
    db_session.add(fraudster)
    db_session.commit()

    # 2. Fraudster registers a device
    fraud_device = Device(
        user_id="user_fraud",
        device_hash="device_shared_malicious",
        browser="Chrome",
        os="Linux",
        ip_address="10.0.0.1",
        location="Unknown",
        is_trusted=True
    )
    db_session.add(fraud_device)
    db_session.commit()

    # Sync the in-memory graph with the database
    FraudGraphEngine.sync_graph_from_db(db_session)

    # 3. Normal user does transaction, but uses the SAME device hash (device_shared_malicious)!
    # This links the normal user directly to the fraudster in the fraud graph
    score_graph, graph_signals = FraudGraphEngine.calculate_risk(db_session, "user_norm", "device_shared_malicious", "acc_recipient_99")
    
    # Path: user_norm -> device_shared_malicious -> user_fraud (which is_fraudster=True)
    # Min distance = 2 (shared device with fraudster)
    # Expected score = 80.0
    assert score_graph == 80.0
    assert graph_signals["shared_device"] is True

def test_transaction_sequencing_and_fusion(db_session):
    RiskFusionEngine._model = None
    # 1. Create User
    user = User(id="user_seq", username="seq_user", is_fraudster=False)
    db_session.add(user)
    db_session.commit()

    # 2. Add parents and children transactions in the correct sequence to prove referential integrity
    tx_id = "test_seq_tx_123"
    
    # 3. Simulate score_transaction sequence: write Transaction record first (PENDING status)
    tx = Transaction(
        id=tx_id,
        user_id="user_seq",
        amount=150.0,
        target_account="acc_target_merchant",
        device_hash="device_fingerprint_seq",
        location="New York, USA",
        status="PENDING"
    )
    db_session.add(tx)
    db_session.commit()
    
    # 4. Create sub scores
    scores = RiskScoreResponse(
        behavioral_score=10.0,
        device_score=50.0,
        geolocation_score=0.0,
        anomaly_score=20.0,
        graph_score=0.0,
        total_score=0.0
    )
    
    # 5. Simulate fusion
    req = TransactionScoreRequest(
        user_id="user_seq",
        amount=150.0,
        target_account="acc_target_merchant",
        device=DeviceSignal(
            device_hash="device_fingerprint_seq",
            browser="Chrome",
            os="macOS",
            ip_address="192.168.1.50",
            location="New York, USA"
        ),
        behavior=BehaviorSignal(
            keystroke_dwell=0.1,
            keystroke_flight=0.15,
            mouse_speed=200.0,
            mouse_jitter=10.0,
            scroll_velocity=50.0
        )
    )
    
    # Calling fusion engine which inserts sub-tables and commits the session
    decision_resp = RiskFusionEngine.fuse_and_decide(db_session, tx_id, "user_seq", req, scores, {}, None, {})
    
    # Verify Pydantic breakdown score updates correctly
    # Total score = 0.15 * 10 + 0.20 * 50 + 0.15 * 0 + 0.30 * 20 + 0.20 * 0 = 1.5 + 10.0 + 6.0 = 17.5
    assert decision_resp.risk_score == 17.5
    assert decision_resp.breakdown.total_score == 17.5
    
    # Verify database inserts were successful and FK restraints did not fail
    db_score = db_session.query(RiskScore).filter(RiskScore.transaction_id == tx_id).first()
    assert db_score is not None
    assert db_score.total_score == 17.5

def test_geolocation_engine(db_session):
    from app.engines.geolocation import GeolocationRiskEngine
    GeolocationRiskEngine._model = None
    # 1. Create a user
    user = User(id="user_geo_test", username="geo_user", is_fraudster=False)
    db_session.add(user)
    db_session.commit()

    # 2. Register first transaction from Chennai
    tx_chennai = Transaction(
        id="tx_c1",
        user_id="user_geo_test",
        amount=100.0,
        target_account="acc_target_merchant",
        device_hash="device_fingerprint_geo",
        location="Chennai, IN",
        latitude=13.0827,
        longitude=80.2707,
        city="Chennai",
        country="IN",
        status="ALLOW"
    )
    db_session.add(tx_chennai)
    db_session.commit()

    # 3. Score a new transaction from Delhi 5 minutes later
    sig_delhi = DeviceSignal(
        device_hash="device_fingerprint_geo",
        browser="Chrome",
        os="macOS",
        ip_address="192.168.1.10",
        location="Delhi, IN",
        latitude=28.7041,
        longitude=77.1025,
        city="Delhi",
        country="IN"
    )

    score = GeolocationRiskEngine.calculate_risk(db_session, "user_geo_test", sig_delhi)
    # Expected risks added:
    # - New location for user (+15.0)
    # - Sudden city change (+10.0)
    # - Impossible travel (+60.0) -> Distance Chennai to Delhi is ~1700km, in < 5 mins it is impossible.
    # Total expected score = 15.0 + 10.0 + 60.0 = 85.0
    assert score == 85.0

def test_graph_mule_detection(db_session):
    FraudGraphEngine._model = None
    # 1. Create users
    u_a = User(id="user_a", username="User A", is_fraudster=False)
    u_b = User(id="user_b", username="User B", is_fraudster=False)
    u_c = User(id="user_c", username="User C", is_fraudster=False)
    db_session.add_all([u_a, u_b, u_c])
    db_session.commit()

    # 2. Let's create transactions to build a circular flow A -> B -> C -> A
    tx_ab = Transaction(
        id="tx_ab", user_id="user_a", amount=100, target_account="user_b",
        device_hash="dev1", location="Chennai", status="ALLOW"
    )
    tx_bc = Transaction(
        id="tx_bc", user_id="user_b", amount=100, target_account="user_c",
        device_hash="dev2", location="Chennai", status="ALLOW"
    )
    tx_ca = Transaction(
        id="tx_ca", user_id="user_c", amount=100, target_account="user_a",
        device_hash="dev3", location="Chennai", status="ALLOW"
    )
    db_session.add_all([tx_ab, tx_bc, tx_ca])
    db_session.commit()

    # Sync and check circular flow
    FraudGraphEngine.sync_graph_from_db(db_session)
    assert FraudGraphEngine.detect_circular_flow("user_a") is True
    assert FraudGraphEngine.detect_circular_flow("user_b") is True

    # 3. Test layering pattern: A -> B -> C -> TargetAccount
    # Let's check user_b who sits in the middle of A -> B -> C
    assert FraudGraphEngine.detect_layering("user_b") is True

    # 4. Test hub account: user_a transfers to 6 different target accounts
    for i in range(6):
        tx = Transaction(
            id=f"tx_hub_{i}", user_id="user_a", amount=10, target_account=f"account_target_{i}",
            device_hash="dev1", location="Chennai", status="ALLOW"
        )
        db_session.add(tx)
    db_session.commit()
    FraudGraphEngine.sync_graph_from_db(db_session)
    assert FraudGraphEngine.detect_hub_account("user_a") is True

    # 5. Test funnel account: user_c receives from 4 different users and sends to 1
    # It already receives from user_b (via tx_bc). Let's add 3 more senders.
    for i in range(3):
        u_sender = User(id=f"sender_{i}", username=f"Sender {i}", is_fraudster=False)
        db_session.add(u_sender)
        tx = Transaction(
            id=f"tx_funnel_{i}", user_id=f"sender_{i}", amount=10, target_account="user_c",
            device_hash="dev1", location="Chennai", status="ALLOW"
        )
        db_session.add(tx)
    db_session.commit()
    FraudGraphEngine.sync_graph_from_db(db_session)
    assert FraudGraphEngine.detect_funnel_account("user_c") is True

    # 6. Test burst transfers: 5 transactions in the last hour
    assert FraudGraphEngine.detect_burst_transfers(db_session, "user_a") is True

def test_razorpay_endpoints(db_session):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    
    # Override dependency to use in-memory test db
    app.dependency_overrides[get_db] = lambda: db_session
    
    try:
        client = TestClient(app)
        
        # 1. Create a user
        user = User(id="user_razorpay", username="razorpay_user", is_fraudster=False)
        db_session.add(user)
        db_session.commit()
        
        # 2. Add an approved transaction
        tx_approved = Transaction(
            id="tx_razorpay_approved",
            user_id="user_razorpay",
            amount=500.0,
            target_account="acc_target",
            device_hash="dev_hash",
            location="Chennai",
            status="ALLOW",
            risk_decision="ALLOW"
        )
        # 3. Add a blocked transaction
        tx_blocked = Transaction(
            id="tx_razorpay_blocked",
            user_id="user_razorpay",
            amount=50000.0,
            target_account="acc_target",
            device_hash="dev_hash",
            location="Chennai",
            status="BLOCK",
            risk_decision="BLOCK"
        )
        db_session.add(tx_approved)
        db_session.add(tx_blocked)
        db_session.commit()
        
        # 4. Request order for blocked transaction -> should fail (HTTP 400)
        resp_blocked = client.post("/api/razorpay/order", json={
            "transaction_id": "tx_razorpay_blocked",
            "amount": 50000.0
        })
        assert resp_blocked.status_code == 400
        
        # 5. Request order for approved transaction -> should succeed (HTTP 200)
        resp_approved = client.post("/api/razorpay/order", json={
            "transaction_id": "tx_razorpay_approved",
            "amount": 500.0
        })
        assert resp_approved.status_code == 200
        data = resp_approved.json()
        assert "order_id" in data
        assert data["amount"] == 500.0
        
        # 6. Submit payment success callback
        resp_success = client.post("/api/razorpay/success", json={
            "transaction_id": "tx_razorpay_approved",
            "razorpay_payment_id": "pay_test_12345",
            "razorpay_order_id": data["order_id"],
            "razorpay_signature": "signature_test"
        })
        assert resp_success.status_code == 200
        
        # Verify transaction status is updated
        updated_tx = db_session.query(Transaction).filter(Transaction.id == "tx_razorpay_approved").first()
        assert updated_tx.status == "ALLOW"
        import json
        exp = json.loads(updated_tx.risk_explanation)
        assert exp["razorpay_payment_id"] == "pay_test_12345"
    finally:
        app.dependency_overrides.clear()

def test_heavy_training(db_session):
    from app.engines.training import (
        train_all_engines,
        BEHAVIORAL_MODEL_FILE,
        DEVICE_MODEL_FILE,
        GEOLOC_MODEL_FILE,
        ANOMALY_MODEL_FILE,
        GRAPH_MODEL_FILE,
        FUSION_MODEL_FILE
    )
    import os
    
    # Run train_all_engines
    train_all_engines(db_session)
    
    # Assert all serialized model files exist on disk
    assert os.path.exists(BEHAVIORAL_MODEL_FILE)
    assert os.path.exists(DEVICE_MODEL_FILE)
    assert os.path.exists(GEOLOC_MODEL_FILE)
    assert os.path.exists(ANOMALY_MODEL_FILE)
    assert os.path.exists(GRAPH_MODEL_FILE)
    assert os.path.exists(FUSION_MODEL_FILE)

    # Each model must ship a versioned metadata sidecar with a feature schema.
    import json
    meta_path = os.path.splitext(FUSION_MODEL_FILE)[0] + ".meta.json"
    assert os.path.exists(meta_path)
    meta = json.loads(open(meta_path).read())
    assert meta["version"] == "2.0.0"
    assert len(meta["feature_names"]) == meta["n_features"]

    # Anti-leakage guard: features must no longer be derived from the label, so no
    # model should be perfectly separable. A perfect AUC means leakage has regressed.
    from app.models.models import ModelRegistry
    active = db_session.query(ModelRegistry).filter(ModelRegistry.is_active == True).all()
    assert len(active) >= 6
    aucs = [json.loads(m.metrics_json).get("auc", 0.0) for m in active]
    assert max(aucs) < 1.0, f"Perfect AUC indicates label-leakage regression: {aucs}"
    assert max(aucs) > 0.6, f"Models failed to learn meaningful signal: {aucs}"


def test_engines_ml_paths(db_session):
    # Test that the engines execute the ML path when a model is present
    # We mock _model with MockModel to keep the tests fast, deterministic, and verify the path
    
    # 1. Create a user
    user = User(id="user_ml", username="ml_user", is_fraudster=False)
    db_session.add(user)
    db_session.commit()
    
    # Behavioral ML path
    BehavioralEngine._model = MockModel(0.45)
    sig_behav = BehaviorSignal(
        keystroke_dwell=0.10, keystroke_flight=0.15,
        mouse_speed=200.0, mouse_jitter=10.0, scroll_velocity=50.0
    )
    # Seed profile first (first check always returns 0.0)
    score1 = BehavioralEngine.calculate_risk(db_session, "user_ml", sig_behav)
    assert score1 == 0.0
    # Second check triggers ML path
    score2 = BehavioralEngine.calculate_risk(db_session, "user_ml", sig_behav)
    assert score2 == 45.0
    
    # Device Trust ML path
    DeviceTrustEngine._model = MockModel(0.65)
    sig_device = DeviceSignal(
        device_hash="device_ml_hash", browser="Chrome", os="macOS",
        ip_address="192.168.1.100", location="SF"
    )
    score_device = DeviceTrustEngine.calculate_risk(db_session, "user_ml", sig_device)
    # First device registers as 0.0, second check triggers ML
    assert score_device == 0.0
    score_device2 = DeviceTrustEngine.calculate_risk(db_session, "user_ml", sig_device)
    assert score_device2 == 65.0
    
    # Geolocation ML path
    GeolocationRiskEngine._model = MockModel(0.75)
    sig_geo = DeviceSignal(
        device_hash="device_ml_hash", browser="Chrome", os="macOS",
        ip_address="192.168.1.100", location="SF",
        latitude=37.7749, longitude=-122.4194, city="SF", country="USA"
    )
    # Setup previous transaction
    tx = Transaction(
        id="tx_ml_geo", user_id="user_ml", amount=10.0,
        device_hash="device_ml_hash", location="SF", status="ALLOW",
        target_account="acc_dest",
        latitude=37.7749, longitude=-122.4194, city="SF", country="USA"
    )
    db_session.add(tx)
    db_session.commit()
    score_geo = GeolocationRiskEngine.calculate_risk(db_session, "user_ml", sig_geo)
    assert score_geo == 75.0
    
    # Fraud Graph ML path
    FraudGraphEngine._model = MockModel(0.85)
    FraudGraphEngine.sync_graph_from_db(db_session)
    score_graph, _ = FraudGraphEngine.calculate_risk(db_session, "user_ml", "device_ml_hash", "acc_dest")
    assert score_graph == 85.0

    # Transaction Anomaly ML path
    TransactionAnomalyEngine._model = MockModel(0.55)
    score_anomaly, anomaly_diag = TransactionAnomalyEngine.calculate_risk(db_session, "user_ml", 150.0, "SF")
    assert score_anomaly == 55.0

    # Risk Fusion ML path
    RiskFusionEngine._model = MockModel(0.95)
    req_fusion = TransactionScoreRequest(
        user_id="user_ml",
        amount=150.0,
        target_account="acc_dest",
        device=DeviceSignal(
            device_hash="device_ml_hash", browser="Chrome", os="macOS",
            ip_address="192.168.1.100", location="SF"
        ),
        behavior=BehaviorSignal(
            keystroke_dwell=0.10, keystroke_flight=0.15,
            mouse_speed=200.0, mouse_jitter=10.0, scroll_velocity=50.0
        )
    )
    scores_fusion = RiskScoreResponse(
        behavioral_score=10.0,
        device_score=50.0,
        geolocation_score=0.0,
        anomaly_score=20.0,
        graph_score=0.0,
        total_score=0.0
    )
    tx_fusion = Transaction(
        id="tx_ml_fusion", user_id="user_ml", amount=150.0,
        device_hash="device_ml_hash", location="SF", status="PENDING",
        target_account="acc_dest"
    )
    db_session.add(tx_fusion)
    db_session.commit()

    decision_resp = RiskFusionEngine.fuse_and_decide(
        db_session, "tx_ml_fusion", "user_ml", req_fusion, scores_fusion, {}, None, {}
    )
    assert decision_resp.risk_score == 95.0
    
    # Clean up model singletons
    BehavioralEngine._model = None
    DeviceTrustEngine._model = None
    GeolocationRiskEngine._model = None
    FraudGraphEngine._model = None
    TransactionAnomalyEngine._model = None
    RiskFusionEngine._model = None




