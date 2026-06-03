from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from ..database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)  # user_id
    username = Column(String, unique=True, index=True)
    is_fraudster = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    device_hash = Column(String, index=True)
    browser = Column(String)
    os = Column(String)
    ip_address = Column(String)
    location = Column(String)
    is_trusted = Column(Boolean, default=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

class BehaviorProfile(Base):
    __tablename__ = "behavior_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, index=True)
    # Keystroke dynamics
    keystroke_dwell_avg = Column(Float, default=0.0)   # duration key is held down
    keystroke_flight_avg = Column(Float, default=0.0)  # interval between keystrokes
    # Mouse movement dynamics
    mouse_speed_avg = Column(Float, default=0.0)
    mouse_jitter_avg = Column(Float, default=0.0)
    # Scroll patterns
    scroll_velocity_avg = Column(Float, default=0.0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String)
    country = Column(String)
    city = Column(String)
    avg_keystroke_ms = Column(Integer)
    mouse_event_count = Column(Integer)
    session_duration_s = Column(Integer)

class Beneficiary(Base):
    __tablename__ = "beneficiaries"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    account_number = Column(String)
    ifsc = Column(String)
    name = Column(String)
    first_added = Column(DateTime(timezone=True), server_default=func.now())
    txn_count = Column(Integer, default=0)
    total_sent = Column(Float, default=0.0)

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True, index=True)  # transaction_id
    user_id = Column(String, ForeignKey("users.id"), index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)
    beneficiary_id = Column(String, ForeignKey("beneficiaries.id"), nullable=True)
    amount = Column(Float)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    target_account = Column(String, index=True)
    device_hash = Column(String)
    location = Column(String)
    channel = Column(String, default="UPI")   # UPI, NEFT, IMPS, card
    currency = Column(String, default="INR")
    status = Column(String)  # ALLOWED, BLOCKED, STEP_UP_REQUIRED, PENDING_DELAY
    risk_score = Column(Float, nullable=True)
    risk_decision = Column(String, nullable=True)
    risk_explanation = Column(String, nullable=True)

class RiskScore(Base):
    __tablename__ = "risk_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), unique=True, index=True)
    behavioral_score = Column(Float)
    device_score = Column(Float)
    anomaly_score = Column(Float)
    graph_score = Column(Float)
    total_score = Column(Float)

class GraphEdge(Base):
    __tablename__ = "graph_edges"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)      # e.g., user_id or device_hash
    target = Column(String, index=True)      # e.g., user_id or device_hash or target_account
    edge_type = Column(String)               # USER_DEVICE, USER_TRANSACTION, DEVICE_IP, etc.
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    risk_score = Column(Float)
    severity = Column(String)                # LOW, MEDIUM, HIGH, CRITICAL
    reason = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_resolved = Column(Boolean, default=False)

class DecisionLog(Base):
    __tablename__ = "decision_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), unique=True, index=True)
    decision = Column(String)                # ALLOW, STEP_UP, DELAY, BLOCK
    reason_codes = Column(String)            # Comma-separated list (e.g. "NEW_DEVICE,HIGH_AMOUNT")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class FraudCase(Base):
    __tablename__ = "fraud_cases"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True)
    case_type = Column(String)   # ato, mule, social_engineering, ring
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    outcome = Column(String)     # confirmed, false_positive, under_review
    analyst_notes = Column(String)
    severity = Column(String)    # LOW, MEDIUM, HIGH, CRITICAL
