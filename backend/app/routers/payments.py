"""
Payments router — Razorpay order creation and payment-success callback.

Prefix: /api/payments
"""
import json
import uuid
import os

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..services.sse import broadcast_alert

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/razorpay/order", response_model=schemas.RazorpayOrderResponse,
             summary="Create a Razorpay payment order for an approved transaction")
def create_razorpay_order(req: schemas.RazorpayOrderRequest, db: Session = Depends(get_db)):
    """
    Creates a Razorpay order for a transaction that has already been approved
    by the PayShield risk engine.  Transactions in BLOCK status are rejected.

    Falls back to a mock order ID when Razorpay credentials are not configured
    (useful for local development).
    """
    import requests as _requests

    tx = db.query(models.Transaction).filter(models.Transaction.id == req.transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if tx.status == "BLOCK" or tx.risk_decision == "BLOCK":
        raise HTTPException(
            status_code=400,
            detail="Transaction blocked by PayShield. Payment not allowed."
        )

    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    amount_in_paise = int(req.amount * 100)

    if key_id and key_secret:
        try:
            url = "https://api.razorpay.com/v1/orders"
            payload = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": f"receipt_{req.transaction_id[:20]}"
            }
            res = _requests.post(url, json=payload, auth=(key_id, key_secret), timeout=10)
            if res.status_code == 200:
                data = res.json()
                return schemas.RazorpayOrderResponse(
                    order_id=data["id"],
                    key_id=key_id,
                    amount=req.amount,
                    currency="INR",
                    status=data.get("status", "created")
                )
            print(f"[Razorpay] API Error {res.status_code}: {res.text}")
        except Exception as exc:
            print(f"[Razorpay] Connection Exception: {exc}")

    # Fallback mock order
    mock_order_id = f"order_mock_{uuid.uuid4().hex[:14]}"
    return schemas.RazorpayOrderResponse(
        order_id=mock_order_id,
        key_id=key_id or "rzp_test_placeholder_key",
        amount=req.amount,
        currency="INR",
        status="created"
    )


@router.post("/razorpay/success", summary="Handle Razorpay payment success callback")
async def razorpay_success(
    req: schemas.RazorpaySuccessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Called by the frontend after a successful Razorpay payment.  Updates the
    transaction status to ALLOW and broadcasts a live SSE event.
    """
    tx = db.query(models.Transaction).filter(models.Transaction.id == req.transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    user = db.query(models.User).filter(models.User.id == tx.user_id).first()

    tx.status = "ALLOW"
    explanation_data: dict = {}
    if tx.risk_explanation:
        try:
            explanation_data = json.loads(tx.risk_explanation)
        except Exception:
            pass

    explanation_data["razorpay_payment_id"] = req.razorpay_payment_id
    explanation_data["razorpay_order_id"] = req.razorpay_order_id
    explanation_data["razorpay_signature"] = req.razorpay_signature
    tx.risk_explanation = json.dumps(explanation_data)
    db.commit()

    event = {
        "type": "TRANSACTION_SCORED",
        "data": {
            "transaction_id": tx.id,
            "user_id": tx.user_id,
            "username": user.username if user else "Unknown",
            "amount": tx.amount,
            "target_account": tx.target_account,
            "decision": "ALLOW",
            "risk_score": tx.risk_score,
            "reason_codes": explanation_data.get("reason_codes", []),
            "breakdown": explanation_data.get("breakdown", {}),
            "remarks": f"{tx.remarks or ''} (Paid: {req.razorpay_payment_id})",
            "scam_classification": tx.scam_classification,
            "scam_explanation": tx.scam_explanation,
            "timestamp": datetime.now().isoformat()
        }
    }
    background_tasks.add_task(broadcast_alert, event)

    return {"status": "success", "payment_id": req.razorpay_payment_id}
