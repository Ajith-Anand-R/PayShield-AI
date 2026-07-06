from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    id: str
    username: str
    is_fraudster: bool = False

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    created_at: datetime
    class Config:
        from_attributes = True

# Device Schemas
class DeviceBase(BaseModel):
    device_hash: str
    browser: str
    os: str
    ip_address: str
    location: str
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    user_agent: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None

class DeviceCreate(DeviceBase):
    user_id: str

class DeviceResponse(DeviceBase):
    id: int
    user_id: str
    is_trusted: bool
    first_seen: datetime
    last_seen: datetime
    trust_score: float
    class Config:
        from_attributes = True

# Behavior Profile Schemas
class BehaviorBase(BaseModel):
    keystroke_dwell_avg: float
    keystroke_flight_avg: float
    mouse_speed_avg: float
    mouse_jitter_avg: float
    scroll_velocity_avg: float

class BehaviorCapture(BehaviorBase):
    user_id: str

class BehaviorProfileResponse(BehaviorBase):
    id: int
    user_id: str
    updated_at: datetime
    class Config:
        from_attributes = True

# Transaction and Scoring Schemas
class TransactionBase(BaseModel):
    user_id: str
    amount: float
    target_account: str

class DeviceSignal(BaseModel):
    device_hash: str
    browser: str
    os: str
    ip_address: str
    location: str
    screen_resolution: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    user_agent: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None

class BehaviorSignal(BaseModel):
    keystroke_dwell: float
    keystroke_flight: float
    mouse_speed: float
    mouse_jitter: float
    scroll_velocity: float

class TransactionScoreRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    amount: float
    currency: str = "INR"
    channel: str = "UPI"
    target_account: str
    beneficiary_name: Optional[str] = None
    beneficiary_ifsc: Optional[str] = None
    beneficiary_added_at: Optional[datetime] = None
    remarks: Optional[str] = None
    device: DeviceSignal
    behavior: BehaviorSignal

class TransactionResponse(TransactionBase):
    id: str
    timestamp: datetime
    device_hash: str
    location: str
    status: str
    class Config:
        from_attributes = True

class RiskScoreResponse(BaseModel):
    behavioral_score: float
    device_score: float
    geolocation_score: float
    anomaly_score: float
    graph_score: float
    total_score: float

class ReasonCodeDetail(BaseModel):
    code: str
    severity: str
    signal: str
    human_message: str

class DecisionResponse(BaseModel):
    transaction_id: str
    risk_score: float
    decision: str
    reason_codes: List[str]
    reasons_detailed: List[ReasonCodeDetail] = []
    breakdown: RiskScoreResponse
    scam_classification: Optional[str] = None
    scam_explanation: Optional[str] = None
    timestamp: datetime
    latency_ms: Optional[float] = None

# Alert Schemas
class AlertResponse(BaseModel):
    id: int
    transaction_id: str
    user_id: str
    risk_score: float
    severity: str
    reason: str
    timestamp: datetime
    is_resolved: bool
    class Config:
        from_attributes = True

# Graph Visualization Schemas
class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # USER, DEVICE, ACCOUNT
    is_fraudster: bool = False
    is_compromised: bool = False
    is_mule: Optional[bool] = False
    is_hub: Optional[bool] = False
    is_funnel: Optional[bool] = False
    is_circular: Optional[bool] = False
    is_layering: Optional[bool] = False

class GraphEdgeSchema(BaseModel):
    source: str
    target: str
    type: str  # USER_DEVICE, USER_TRANSACTION
    weight: float = 1.0
    is_fraud_path: bool = False

class GraphDataResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdgeSchema]

class SessionStartRequest(BaseModel):
    user_id: str
    device_fingerprint: str
    user_agent: str
    ip_address: str
    timezone: str
    screen_resolution: str

class SessionStartResponse(BaseModel):
    session_id: str
    device_known: bool
    device_trust_score: float
    geo_match: bool
    risk_flags: List[str]

class SimulateEventRequest(BaseModel):
    scenario: str
    user_id: Optional[str] = "user_alice"

class FraudCaseResponse(BaseModel):
    id: str
    user_id: str
    transaction_id: str
    case_type: str
    opened_at: datetime
    closed_at: Optional[datetime]
    outcome: str
    analyst_notes: Optional[str]
    severity: str
    class Config:
        from_attributes = True

# Razorpay Schemas
class RazorpayOrderRequest(BaseModel):
    transaction_id: str
    amount: float

class RazorpayOrderResponse(BaseModel):
    order_id: str
    key_id: Optional[str]
    amount: float
    currency: str = "INR"
    status: str

class RazorpaySuccessRequest(BaseModel):
    transaction_id: str
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str

