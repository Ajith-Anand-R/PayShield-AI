"""
Scoring router — transaction risk scoring pipeline.

Prefix: /api/scoring  (new modular path).
The legacy /api/* paths remain alive via routes/api.py during the migration
window so the frontend is not broken.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel
import uuid
import json
import time

from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..schemas.stream_schemas import ManualTransactionRequest, WebhookTransactionRequest
from ..engines.behavioral import BehavioralEngine
from ..engines.device import DeviceTrustEngine
from ..engines.anomaly import TransactionAnomalyEngine
from ..engines.graph import FraudGraphEngine
from ..services.fusion import RiskFusionEngine
from ..services.sse import broadcast_alert
from ..services.audit import log_decision
from ..middleware.auth import ApiKeyDep

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


# ---------------------------------------------------------------------------
# Idempotency helper
# ---------------------------------------------------------------------------
# In-memory store for idempotency keys → cached response.
# Phase 5 will migrate this to Redis with a configurable TTL.
_idempotency_cache: dict[str, dict] = {}


def _get_cached(key: str | None) -> dict | None:
    """Return a previously cached response for *key*, or None."""
    if key and key in _idempotency_cache:
        return _idempotency_cache[key]
    return None


def _cache_response(key: str | None, resp: dict) -> None:
    if key:
        _idempotency_cache[key] = resp


# ---------------------------------------------------------------------------
# Core scoring handler (shared by /transaction/score, /transaction/submit,
# /webhook/ingest, /transactions/create, /risk/evaluate)
# ---------------------------------------------------------------------------
def _run_scoring_pipeline(
    req: schemas.TransactionScoreRequest,
    background_tasks: BackgroundTasks,
    db: Session,
    *,
    idempotency_key: str | None = None,
) -> schemas.DecisionResponse:
    """
    Execute the full risk-scoring pipeline and return a DecisionResponse.

    Idempotency: if *idempotency_key* is provided and matches a cached entry,
    the previous result is returned immediately without re-processing.
    """
    cached = _get_cached(idempotency_key)
    if cached:
        return schemas.DecisionResponse(**cached)

    start_time = time.perf_counter()

    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    transaction_id = str(uuid.uuid4())

    # --- Beneficiary resolution ---
    beneficiary_age_hours: float | None = None
    new_beneficiary = False
    beneficiary_id: str | None = None

    if req.beneficiary_added_at:
        from datetime import timezone
        added_at = req.beneficiary_added_at
        if added_at.tzinfo is None:
            added_at = added_at.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - added_at).total_seconds() / 3600
        beneficiary_age_hours = age
        new_beneficiary = age < 24

    db_beneficiary = None
    if req.beneficiary_name or req.beneficiary_ifsc or req.target_account:
        db_beneficiary = db.query(models.Beneficiary).filter(
            models.Beneficiary.user_id == req.user_id,
            models.Beneficiary.account_number == req.target_account
        ).first()

        if not db_beneficiary:
            db_beneficiary = models.Beneficiary(
                id=str(uuid.uuid4()),
                user_id=req.user_id,
                account_number=req.target_account,
                ifsc=req.beneficiary_ifsc or "",
                name=req.beneficiary_name or "Unknown"
            )
            if req.beneficiary_added_at:
                db_beneficiary.first_added = req.beneficiary_added_at
            db.add(db_beneficiary)
        else:
            if req.beneficiary_ifsc:
                db_beneficiary.ifsc = req.beneficiary_ifsc
            if req.beneficiary_name:
                db_beneficiary.name = req.beneficiary_name

        beneficiary_id = db_beneficiary.id
        if beneficiary_age_hours is None and db_beneficiary.first_added:
            from datetime import timezone
            added_at = db_beneficiary.first_added
            if added_at.tzinfo is None:
                added_at = added_at.replace(tzinfo=timezone.utc)
            beneficiary_age_hours = (datetime.now(timezone.utc) - added_at).total_seconds() / 3600
            new_beneficiary = beneficiary_age_hours < 24

    from ..services.redis_client import increment_txn_count
    current_velocity = increment_txn_count(req.user_id)  # noqa: F841 (side-effect)

    # --- Persist Transaction (PENDING) before sub-scores to satisfy FK integrity ---
    db_tx = models.Transaction(
        id=transaction_id,
        user_id=req.user_id,
        session_id=req.session_id,
        beneficiary_id=beneficiary_id,
        amount=req.amount,
        target_account=req.target_account,
        device_hash=req.device.device_hash,
        location=req.device.location,
        latitude=req.device.latitude,
        longitude=req.device.longitude,
        city=req.device.city,
        region=req.device.region,
        country=req.device.country,
        channel=req.channel,
        currency=req.currency,
        status="PENDING"
    )
    db.add(db_tx)

    # --- Engine sub-scores ---
    behavioral_score = BehavioralEngine.calculate_risk(db, req.user_id, req.behavior)
    device_score = DeviceTrustEngine.calculate_risk(db, req.user_id, req.device)

    from ..engines.geolocation import GeolocationRiskEngine
    geolocation_score = GeolocationRiskEngine.calculate_risk(db, req.user_id, req.device)

    anomaly_score, anomaly_signals = TransactionAnomalyEngine.calculate_risk(
        db,
        req.user_id,
        req.amount,
        req.device.location,
        beneficiary_age_hours=beneficiary_age_hours,
        new_beneficiary=new_beneficiary,
        latitude=req.device.latitude,
        longitude=req.device.longitude
    )

    graph_score, graph_signals = FraudGraphEngine.calculate_risk(
        db, req.user_id, req.device.device_hash, req.target_account
    )

    from ..services.scam_detector import ScamDetectorService
    scam_analysis = ScamDetectorService.analyze_remarks(req.remarks)

    scores = schemas.RiskScoreResponse(
        behavioral_score=behavioral_score,
        device_score=device_score,
        geolocation_score=geolocation_score,
        anomaly_score=anomaly_score,
        graph_score=graph_score,
        total_score=0.0
    )

    # --- Fusion & final decision ---
    decision_resp = RiskFusionEngine.fuse_and_decide(
        db, transaction_id, req.user_id, req, scores,
        anomaly_signals, scam_analysis, graph_signals
    )

    # --- Finalise Transaction row ---
    db_tx.status = decision_resp.decision
    db_tx.risk_score = decision_resp.risk_score
    db_tx.risk_decision = decision_resp.decision
    db_tx.remarks = req.remarks
    db_tx.scam_classification = scam_analysis["classification"]
    db_tx.scam_explanation = scam_analysis["explanation"]
    db_tx.risk_explanation = json.dumps({
        "reason_codes": decision_resp.reason_codes,
        "breakdown": decision_resp.breakdown.model_dump(),
        "scam": scam_analysis
    })

    latency_ms = (time.perf_counter() - start_time) * 1000.0
    db_tx.latency_ms = latency_ms
    decision_resp.latency_ms = latency_ms

    if db_beneficiary:
        db_beneficiary.txn_count = (db_beneficiary.txn_count or 0) + 1
        db_beneficiary.total_sent = (db_beneficiary.total_sent or 0.0) + req.amount

    db.commit()

    # --- Incremental graph update ---
    try:
        target_is_user = (
            db.query(models.User)
            .filter(models.User.id == req.target_account)
            .first() is not None
        )
        FraudGraphEngine.register_transaction(
            user_id=req.user_id,
            device_hash=req.device.device_hash,
            browser=req.device.browser,
            os=req.device.os,
            target_account=req.target_account,
            target_is_user=target_is_user
        )
    except Exception as ge:
        print(f"[PayShield] Error registering transaction to graph: {ge}")

    # --- SSE broadcast ---
    event = {
        "type": "TRANSACTION_SCORED",
        "data": {
            "transaction_id": transaction_id,
            "user_id": req.user_id,
            "username": user.username,
            "amount": req.amount,
            "target_account": req.target_account,
            "decision": decision_resp.decision,
            "risk_score": decision_resp.risk_score,
            "reason_codes": decision_resp.reason_codes,
            "breakdown": decision_resp.breakdown.model_dump(),
            "device": req.device.model_dump(),
            "remarks": req.remarks,
            "scam_classification": scam_analysis.get("classification") if scam_analysis else None,
            "scam_explanation": scam_analysis.get("explanation") if scam_analysis else None,
            "timestamp": datetime.now().isoformat(),
            "latency_ms": latency_ms
        }
    }
    background_tasks.add_task(broadcast_alert, event)

    # Cache for idempotency
    _cache_response(idempotency_key, decision_resp.model_dump())

    # Structured audit trail
    log_decision(
        db,
        transaction_id=transaction_id,
        decision=decision_resp.decision,
        actor="system",  # replaced by client.name when auth is enabled
        extra={"risk_score": decision_resp.risk_score, "latency_ms": latency_ms},
    )
    db.commit()  # commit the AuditLog row

    return decision_resp


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class ScamAnalyzeRequest(BaseModel):
    remarks: str


@router.post("/transaction/score", response_model=schemas.DecisionResponse,
             summary="Score a transaction through the full risk pipeline")
def score_transaction(
    req: schemas.TransactionScoreRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    client: ApiKeyDep = None,
    idempotency_key: str | None = None,
):
    """
    Primary scoring endpoint.

    Pass `X-API-Key` header with a valid key (required when AUTH_ENABLED=true).
    Pass an `Idempotency-Key` query param to guarantee at-most-once processing
    for retried requests.
    """
    return _run_scoring_pipeline(req, background_tasks, db, idempotency_key=idempotency_key)


@router.post("/transaction/submit", response_model=schemas.DecisionResponse,
             summary="Submit a simplified manual transaction from the UI")
def submit_manual_transaction(
    req: ManualTransactionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Accept a simplified manual transaction from the UI and route through the scoring pipeline."""
    from ..schemas.schemas import TransactionScoreRequest, DeviceSignal, BehaviorSignal

    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {req.user_id} not found. Seed the database first.")

    device = db.query(models.Device).filter(models.Device.user_id == req.user_id).first()
    behavior = db.query(models.BehaviorProfile).filter(models.BehaviorProfile.user_id == req.user_id).first()

    score_req = TransactionScoreRequest(
        user_id=req.user_id,
        amount=req.amount,
        currency="INR",
        channel=req.channel,
        target_account=req.target_account,
        beneficiary_name=req.beneficiary_name or "Manual Entry",
        beneficiary_added_at=datetime.now() - timedelta(days=30),
        device=DeviceSignal(
            device_hash=device.device_hash if device else "manual_device",
            browser=device.browser if device else "Chrome",
            os=device.os if device else "Windows",
            ip_address=device.ip_address if device else "127.0.0.1",
            location=req.location
        ),
        behavior=BehaviorSignal(
            keystroke_dwell=behavior.keystroke_dwell_avg if behavior else 0.10,
            keystroke_flight=behavior.keystroke_flight_avg if behavior else 0.15,
            mouse_speed=behavior.mouse_speed_avg if behavior else 250.0,
            mouse_jitter=behavior.mouse_jitter_avg if behavior else 12.0,
            scroll_velocity=behavior.scroll_velocity_avg if behavior else 80.0
        )
    )
    return _run_scoring_pipeline(score_req, background_tasks, db)


@router.post("/webhook/ingest", response_model=schemas.DecisionResponse,
             summary="Accept transactions from external systems")
def webhook_ingest(
    req: WebhookTransactionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Accept transactions from external systems (bank core, payment switch)."""
    from ..schemas.schemas import TransactionScoreRequest, DeviceSignal, BehaviorSignal

    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        user = models.User(id=req.user_id, username=f"{req.user_id}_webhook", is_fraudster=False)
        db.add(user)
        db.commit()

    behavior = db.query(models.BehaviorProfile).filter(models.BehaviorProfile.user_id == req.user_id).first()

    score_req = TransactionScoreRequest(
        user_id=req.user_id,
        amount=req.amount,
        currency=req.currency,
        channel=req.channel,
        target_account=req.target_account,
        beneficiary_name=req.beneficiary_name,
        beneficiary_ifsc=req.beneficiary_ifsc,
        device=DeviceSignal(
            device_hash=req.device_hash,
            browser=req.browser,
            os=req.os,
            ip_address=req.ip_address,
            location=req.location
        ),
        behavior=BehaviorSignal(
            keystroke_dwell=behavior.keystroke_dwell_avg if behavior else 0.10,
            keystroke_flight=behavior.keystroke_flight_avg if behavior else 0.15,
            mouse_speed=behavior.mouse_speed_avg if behavior else 250.0,
            mouse_jitter=behavior.mouse_jitter_avg if behavior else 12.0,
            scroll_velocity=behavior.scroll_velocity_avg if behavior else 80.0
        )
    )
    return _run_scoring_pipeline(score_req, background_tasks, db)


@router.post("/scam/analyze", summary="Analyse free-text remarks for scam patterns")
def scam_analyze(req: ScamAnalyzeRequest):
    """Run scam-text heuristics (and optionally Gemini) against transaction remarks."""
    from ..services.scam_detector import ScamDetectorService
    return ScamDetectorService.analyze_remarks(req.remarks)
