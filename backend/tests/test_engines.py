import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app.database import Base
from app.models.models import User, Device, BehaviorProfile, Transaction, GraphEdge, RiskScore
from app.schemas.schemas import BehaviorSignal, DeviceSignal, TransactionScoreRequest, RiskScoreResponse
from app.engines.behavioral import BehavioralEngine
from app.engines.device import DeviceTrustEngine
from app.engines.anomaly import TransactionAnomalyEngine
from app.engines.graph import FraudGraphEngine
from app.services.fusion import RiskFusionEngine

os.environ.setdefault("REDIS_URL", "memory://")

# Set up in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
    assert score_new >= 50.0

def test_anomaly_engine(db_session):
    # Train Isolation Forest on seeded synthetic data
    TransactionAnomalyEngine.train_model(db_session)
    
    # Calculate score for normal amount
    score_normal, _ = TransactionAnomalyEngine.calculate_risk(db_session, "user_test_3", 50.0, "Home")
    
    # Calculate score for massive amount
    score_high, _ = TransactionAnomalyEngine.calculate_risk(db_session, "user_test_3", 15000.0, "London")
    
    assert score_high > score_normal

def test_fraud_graph_engine(db_session):
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

    # 3. Normal user does transaction, but uses the SAME device hash (device_shared_malicious)!
    # This links the normal user directly to the fraudster in the fraud graph
    score_graph = FraudGraphEngine.calculate_risk(db_session, "user_norm", "device_shared_malicious", "acc_recipient_99")
    
    # Path: user_norm -> device_shared_malicious -> user_fraud (which is_fraudster=True)
    # Min distance = 2 (shared device with fraudster)
    # Expected score = 80.0
    assert score_graph == 80.0

def test_transaction_sequencing_and_fusion(db_session):
    # 1. Create User
    user = User(id="user_seq", username="seq_user", is_fraudster=False)
    db_session.add(user)
    db_session.commit()

    # 2. Add parents and children transactions in the correct sequence to prove referential integrity
    tx_id = "test_seq_tx_123"
    
    # 3. Simulate score_transaction sequence: write Transaction record first (PNDING status)
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
    # Note: Added to session, not committed yet
    
    # 4. Create sub scores
    scores = RiskScoreResponse(
        behavioral_score=10.0,
        device_score=50.0,
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
    decision_resp = RiskFusionEngine.fuse_and_decide(db_session, tx_id, "user_seq", req, scores, {})
    
    # Verify Pydantic breakdown score updates correctly
    assert decision_resp.risk_score == 21.5
    assert decision_resp.breakdown.total_score == 21.5
    
    # Verify database inserts were successful and FK restraints did not fail
    db_score = db_session.query(RiskScore).filter(RiskScore.transaction_id == tx_id).first()
    assert db_score is not None
    assert db_score.total_score == 21.5
