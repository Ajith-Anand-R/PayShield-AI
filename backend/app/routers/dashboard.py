"""
Dashboard router — observability, live stream, investigation.

Prefix: /api/dashboard
"""
import asyncio
import json
from typing import List

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..engines.graph import FraudGraphEngine
from ..services.sse import alert_listeners

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Stats & alerts
# ---------------------------------------------------------------------------

@router.get("/stats", summary="Aggregate transaction counters for the dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(models.Transaction).count()
    blocked = db.query(models.Transaction).filter(models.Transaction.status == "BLOCK").count()
    step_up = db.query(models.Transaction).filter(models.Transaction.status == "STEP_UP").count()
    allowed = db.query(models.Transaction).filter(models.Transaction.status == "ALLOW").count()

    return {
        "total_transactions": total,
        "blocked": blocked,
        "step_up": step_up,
        "allowed": allowed,
        "false_positive_rate": round((step_up / max(total, 1)) * 100, 1),
        "block_rate": round((blocked / max(total, 1)) * 100, 1)
    }


@router.get("/alerts", response_model=List[schemas.AlertResponse],
            summary="Return the 50 most-recent alerts")
def get_alerts(db: Session = Depends(get_db)):
    return db.query(models.Alert).order_by(models.Alert.timestamp.desc()).limit(50).all()


@router.get("/alerts/live", summary="SSE stream for live transaction decisions")
async def live_alerts():
    """
    Server-Sent Events stream.  Connect once; receive a JSON envelope for every
    transaction scored in real time.
    """
    queue: asyncio.Queue = asyncio.Queue()
    alert_listeners.append(queue)

    async def event_generator():
        try:
            yield (
                f"data: {json.dumps({'type': 'CONNECTED', 'message': 'Successfully connected to PayShield Live Stream'})}\n\n"
            )
            while True:
                event_data = await queue.get()
                yield f"data: {json.dumps(event_data)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in alert_listeners:
                alert_listeners.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

@router.get("/graph", response_model=schemas.GraphDataResponse,
            summary="Return the current in-memory fraud graph")
def get_graph_data(db: Session = Depends(get_db)):
    return FraudGraphEngine.get_graph_data(db)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@router.get("/metrics/latency", summary="Scoring latency percentiles (p50/p95/p99)")
def get_latency_metrics(db: Session = Depends(get_db)):
    """Calculates p50, p95, p99 latency over the last 1 000 transactions."""
    txs = (
        db.query(models.Transaction.latency_ms)
        .filter(models.Transaction.latency_ms.isnot(None))
        .order_by(models.Transaction.timestamp.desc())
        .limit(1000)
        .all()
    )

    if not txs:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}

    import numpy as np
    latencies = [t[0] for t in txs if t[0] is not None]
    latencies.sort()
    n = len(latencies)

    return {
        "p50": round(float(np.percentile(latencies, 50)), 2),
        "p95": round(float(np.percentile(latencies, 95)), 2),
        "p99": round(float(np.percentile(latencies, 99)), 2),
        "count": n
    }


@router.get("/metrics/model", summary="Active ML model versions and performance metrics")
def get_model_metrics(db: Session = Depends(get_db)):
    active = db.query(models.ModelRegistry).filter(models.ModelRegistry.is_active.is_(True)).all()
    res: dict = {}
    for m in active:
        try:
            metrics = json.loads(m.metrics_json)
        except Exception:
            metrics = {}
        res[m.model_name] = {
            "version": m.version,
            "trained_at": m.trained_at.isoformat() if m.trained_at else None,
            "metrics": metrics
        }
    return res


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

@router.get("/user/{user_id}/profile", summary="Summarised profile for a user")
def get_user_profile(user_id: str, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == user_id)
        .order_by(models.Transaction.timestamp.desc())
        .limit(50)
        .all()
    )
    devices = db.query(models.Device).filter(models.Device.user_id == user_id).all()
    behavior = (
        db.query(models.BehaviorProfile)
        .filter(models.BehaviorProfile.user_id == user_id)
        .first()
    )

    amounts = [t.amount for t in transactions if t.status == "ALLOW"]
    avg_amount = sum(amounts) / len(amounts) if amounts else 0

    return {
        "user": {"id": user.id, "username": user.username},
        "stats": {
            "total_transactions": len(transactions),
            "avg_amount": round(avg_amount, 2),
            "blocked_count": sum(1 for t in transactions if t.status == "BLOCK"),
            "step_up_count": sum(1 for t in transactions if t.status == "STEP_UP")
        },
        "devices": [{"hash": d.device_hash, "os": d.os, "trusted": d.is_trusted} for d in devices],
        "behavior_baseline": {
            "keystroke_dwell": behavior.keystroke_dwell_avg if behavior else None,
            "mouse_speed": behavior.mouse_speed_avg if behavior else None
        },
        "recent_transactions": [
            {
                "id": t.id, "amount": t.amount, "status": t.status,
                "timestamp": t.timestamp.isoformat(), "target": t.target_account
            }
            for t in transactions[:10]
        ]
    }


# ---------------------------------------------------------------------------
# Investigation
# ---------------------------------------------------------------------------

@router.get("/investigation/{transaction_id}",
            summary="Full forensic investigation view for a single transaction")
def get_transaction_investigation(transaction_id: str, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    tx = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    user = db.query(models.User).filter(models.User.id == tx.user_id).first()
    devices = db.query(models.Device).filter(models.Device.user_id == tx.user_id).all()
    history = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == tx.user_id)
        .order_by(models.Transaction.timestamp.asc())
        .all()
    )

    timeline: list[dict] = []
    if user:
        timeline.append({
            "event": "USER_REGISTERED",
            "title": "User Registered",
            "description": f"Account created for {user.username}",
            "timestamp": user.created_at.isoformat() if user.created_at else None
        })

    for d in devices:
        timeline.append({
            "event": "DEVICE_REGISTERED",
            "title": f"Device Linked ({d.os})",
            "description": f"Fingerprint: {d.device_hash[:8]}... from {d.city or 'Unknown'}, {d.country or 'Unknown'}",
            "timestamp": d.first_seen.isoformat() if d.first_seen else None
        })

    for t in history:
        timeline.append({
            "event": "TRANSACTION_SUBMITTED",
            "title": f"Transaction {t.status}",
            "description": f"₹{t.amount} to {t.target_account} (Score: {t.risk_score or 0.0})",
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "id": t.id,
            "is_current": t.id == transaction_id
        })

    timeline = [e for e in timeline if e["timestamp"] is not None]
    timeline.sort(key=lambda x: x["timestamp"])

    location_hops = [
        {
            "city": t.city or "Unknown",
            "country": t.country or "Unknown",
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "lat": t.latitude,
            "lng": t.longitude
        }
        for t in history
        if t.city or t.country
    ]

    profile = (
        db.query(models.BehaviorProfile)
        .filter(models.BehaviorProfile.user_id == tx.user_id)
        .first()
    )

    explanation_data: dict = {}
    if tx.risk_explanation:
        try:
            explanation_data = json.loads(tx.risk_explanation)
        except Exception:
            pass

    return {
        "transaction": {
            "id": tx.id,
            "user_id": tx.user_id,
            "username": user.username if user else "Unknown",
            "amount": tx.amount,
            "target_account": tx.target_account,
            "status": tx.status,
            "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
            "risk_score": tx.risk_score,
            "risk_decision": tx.risk_decision,
            "remarks": tx.remarks,
            "scam_classification": tx.scam_classification,
            "scam_explanation": tx.scam_explanation,
            "reason_codes": explanation_data.get("reason_codes", []),
            "breakdown": explanation_data.get("breakdown", {})
        },
        "timeline": timeline,
        "location_hops": location_hops,
        "biometrics": {
            "baseline": {
                "keystroke_dwell": profile.keystroke_dwell_avg if profile else 0.0,
                "keystroke_flight": profile.keystroke_flight_avg if profile else 0.0,
                "mouse_speed": profile.mouse_speed_avg if profile else 0.0,
                "mouse_jitter": profile.mouse_jitter_avg if profile else 0.0,
                "scroll_velocity": profile.scroll_velocity_avg if profile else 0.0
            },
            "current": explanation_data.get("breakdown", {})
        }
    }
