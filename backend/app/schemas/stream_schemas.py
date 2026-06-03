from pydantic import BaseModel, Field
from typing import Optional


class StreamConfigRequest(BaseModel):
    speed: Optional[float] = Field(None, ge=0.5, le=15.0, description="Seconds between transactions")
    fraud_rate: Optional[float] = Field(None, ge=0.0, le=0.30, description="Fraud injection rate 0-0.30")


class StreamStatusResponse(BaseModel):
    running: bool
    speed: float
    fraud_rate: float
    total_generated: int
    total_fraud_injected: int
    total_blocked: int
    total_allowed: int
    uptime_seconds: float


class ManualTransactionRequest(BaseModel):
    user_id: str = "user_alice"
    amount: float = Field(ge=100.0, le=500000.0)
    target_account: str = "acc_manual_target"
    channel: str = "UPI"
    location: str = "Chennai, IN"
    beneficiary_name: Optional[str] = None


class WebhookTransactionRequest(BaseModel):
    transaction_ref: Optional[str] = None
    user_id: str
    amount: float
    currency: str = "INR"
    channel: str = "UPI"
    target_account: str
    beneficiary_name: Optional[str] = None
    beneficiary_ifsc: Optional[str] = None
    device_hash: str = "webhook_device"
    browser: str = "API"
    os: str = "Server"
    ip_address: str = "0.0.0.0"
    location: str = "Unknown"
