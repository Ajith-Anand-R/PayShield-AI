from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import json
import asyncio
import threading
from datetime import datetime, timedelta
from typing import List
import time

from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..engines.behavioral import BehavioralEngine
from ..engines.device import DeviceTrustEngine
from ..engines.anomaly import TransactionAnomalyEngine
from ..engines.graph import FraudGraphEngine
from ..services.fusion import RiskFusionEngine
from ..schemas.stream_schemas import ManualTransactionRequest, WebhookTransactionRequest

router = APIRouter(prefix="/api")

# Live alert listeners (in-memory pub/sub)
alert_listeners = []

async def broadcast_alert(alert_data: dict):
    """
    Broadcasts a new event/alert to all connected SSE clients.
    """
    closed_listeners = []
    for queue in alert_listeners:
        try:
            await queue.put(alert_data)
        except Exception:
            closed_listeners.append(queue)
            
    for q in closed_listeners:
        if q in alert_listeners:
            alert_listeners.remove(q)

@router.post("/auth/register", response_model=schemas.UserResponse)
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_data.id).first()
    if db_user:
        raise HTTPException(status_code=400, detail="User already registered")
    db_user = models.User(
        id=user_data.id,
        username=user_data.username,
        is_fraudster=user_data.is_fraudster
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/auth/login", response_model=schemas.UserResponse)
def login(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_data.id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.post("/device/register", response_model=schemas.DeviceResponse)
def register_device(device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    # Check if device already registered
    db_device = db.query(models.Device).filter(
        models.Device.user_id == device.user_id,
        models.Device.device_hash == device.device_hash
    ).first()
    
    if not db_device:
        db_device = models.Device(
            user_id=device.user_id,
            device_hash=device.device_hash,
            browser=device.browser,
            os=device.os,
            ip_address=device.ip_address,
            location=device.location,
            screen_resolution=device.screen_resolution,
            timezone=device.timezone,
            language=device.language,
            user_agent=device.user_agent,
            latitude=device.latitude,
            longitude=device.longitude,
            city=device.city,
            region=device.region,
            country=device.country,
            is_trusted=True,
            trust_score=1.0
        )
        db.add(db_device)
        db.commit()
        db.refresh(db_device)
    else:
        db_device.last_seen = datetime.now()
        db_device.ip_address = device.ip_address
        db_device.location = device.location
        db_device.screen_resolution = device.screen_resolution
        db_device.timezone = device.timezone
        db_device.language = device.language
        db_device.user_agent = device.user_agent
        db_device.latitude = device.latitude
        db_device.longitude = device.longitude
        db_device.city = device.city
        db_device.region = device.region
        db_device.country = device.country
        db.commit()
        db.refresh(db_device)
    return db_device

@router.post("/behavior/capture", response_model=schemas.BehaviorProfileResponse)
def capture_behavior(behavior: schemas.BehaviorCapture, db: Session = Depends(get_db)):
    profile = db.query(models.BehaviorProfile).filter(models.BehaviorProfile.user_id == behavior.user_id).first()
    if not profile:
        profile = models.BehaviorProfile(
            user_id=behavior.user_id,
            keystroke_dwell_avg=behavior.keystroke_dwell_avg,
            keystroke_flight_avg=behavior.keystroke_flight_avg,
            mouse_speed_avg=behavior.mouse_speed_avg,
            mouse_jitter_avg=behavior.mouse_jitter_avg,
            scroll_velocity_avg=behavior.scroll_velocity_avg
        )
        db.add(profile)
    else:
        profile.keystroke_dwell_avg = behavior.keystroke_dwell_avg
        profile.keystroke_flight_avg = behavior.keystroke_flight_avg
        profile.mouse_speed_avg = behavior.mouse_speed_avg
        profile.mouse_jitter_avg = behavior.mouse_jitter_avg
        profile.scroll_velocity_avg = behavior.scroll_velocity_avg
    db.commit()
    db.refresh(profile)
    return profile

@router.post("/session/start", response_model=schemas.SessionStartResponse)
def start_session(req: schemas.SessionStartRequest, db: Session = Depends(get_db)):
    session_id = str(uuid.uuid4())
    risk_flags = []
    
    device = db.query(models.Device).filter(
        models.Device.user_id == req.user_id,
        models.Device.device_hash == req.device_fingerprint
    ).first()
    
    device_known = device is not None and device.is_trusted
    if not device_known:
        risk_flags.append("new_device")
    
    from ..services.redis_client import get_last_ip, set_last_ip
    last_ip = get_last_ip(req.user_id)
    geo_match = True
    if last_ip and last_ip.split(".")[:2] != req.ip_address.split(".")[:2]:
        geo_match = False
        risk_flags.append("ip_change")
    
    db_session = models.Session(
        id=session_id,
        user_id=req.user_id,
        device_id=device.id if device else None,
        ip_address=req.ip_address,
        started_at=datetime.now()
    )
    db.add(db_session)
    db.commit()
    set_last_ip(req.user_id, req.ip_address)
    
    return schemas.SessionStartResponse(
        session_id=session_id,
        device_known=device_known,
        device_trust_score=1.0 if device_known else 0.2,
        geo_match=geo_match,
        risk_flags=risk_flags
    )

@router.post("/transaction/score", response_model=schemas.DecisionResponse)
async def score_transaction(
    req: schemas.TransactionScoreRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    start_time = time.perf_counter()
    # Verify user exists
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    transaction_id = str(uuid.uuid4())
    
    beneficiary_age_hours = None
    new_beneficiary = False
    beneficiary_id = None
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
    current_velocity = increment_txn_count(req.user_id)
    
    # 1. Instantiate and add Transaction record first to satisfy foreign key (FK) referential integrity
    # for RiskScore, DecisionLog, and Alert. Sets initial status to PENDING.
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
    
    # 2. Run behavioral trust check
    behavioral_score = BehavioralEngine.calculate_risk(db, req.user_id, req.behavior)
    
    # 3. Run device fingerprint trust check
    device_score = DeviceTrustEngine.calculate_risk(db, req.user_id, req.device)
    
    # Geolocation risk check
    from ..engines.geolocation import GeolocationRiskEngine
    geolocation_score = GeolocationRiskEngine.calculate_risk(db, req.user_id, req.device)
    
    # 4. Run transaction anomaly model
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
    
    # 5. Run graph ring analysis
    graph_score, graph_signals = FraudGraphEngine.calculate_risk(db, req.user_id, req.device.device_hash, req.target_account)
    
    # Run scam text analysis using Gemini or local heuristics
    from ..services.scam_detector import ScamDetectorService
    scam_analysis = ScamDetectorService.analyze_remarks(req.remarks)

    # Bundle sub-scores
    scores = schemas.RiskScoreResponse(
        behavioral_score=behavioral_score,
        device_score=device_score,
        geolocation_score=geolocation_score,
        anomaly_score=anomaly_score,
        graph_score=graph_score,
        total_score=0.0
    )
    
    # 6. Risk fusion and final decision (commits both db_tx and new sub-score records together)
    decision_resp = RiskFusionEngine.fuse_and_decide(db, transaction_id, req.user_id, req, scores, anomaly_signals, scam_analysis, graph_signals)
    
    # 7. Update Transaction Record with decision verbatim and finalize DB state
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
    
    # Update graph incrementally
    try:
        target_is_user = db.query(models.User).filter(models.User.id == req.target_account).first() is not None
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

    # Build live dashboard notification event
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
    
    # Broadcast in background
    background_tasks.add_task(broadcast_alert, event)
        
    return decision_resp



@router.get("/metrics/latency")
def get_latency_metrics(db: Session = Depends(get_db)):
    """
    Calculates p50, p95, p99 latency over the last 1,000 transactions.
    """
    txs = db.query(models.Transaction.latency_ms)\
        .filter(models.Transaction.latency_ms.isnot(None))\
        .order_by(models.Transaction.timestamp.desc())\
        .limit(1000).all()
        
    if not txs:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
        
    latencies = [t[0] for t in txs]
    latencies.sort()
    
    n = len(latencies)
    p50 = latencies[int(n * 0.50)]
    p95 = latencies[int(n * 0.95)]
    p99 = latencies[int(n * 0.99)]
    
    return {
        "p50": round(p50, 2),
        "p95": round(p95, 2),
        "p99": round(p99, 2),
        "count": n
    }

@router.get("/graph/data", response_model=schemas.GraphDataResponse)
def get_graph_data(db: Session = Depends(get_db)):
    return FraudGraphEngine.get_graph_data(db)

@router.get("/user/{user_id}/profile")
def get_user_profile(user_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == user_id
    ).order_by(models.Transaction.timestamp.desc()).limit(50).all()
    
    devices = db.query(models.Device).filter(models.Device.user_id == user_id).all()
    behavior = db.query(models.BehaviorProfile).filter(models.BehaviorProfile.user_id == user_id).first()
    
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
            } for t in transactions[:10]
        ]
    }

@router.get("/cases", response_model=List[schemas.FraudCaseResponse])
def get_fraud_cases(db: Session = Depends(get_db)):
    return db.query(models.FraudCase).order_by(models.FraudCase.opened_at.desc()).limit(20).all()

# Counter for new labeled cases since last retrain
NEW_LABELS_COUNT = 0

@router.patch("/cases/{case_id}")
def update_case(case_id: str, outcome: str, notes: str = "", db: Session = Depends(get_db)):
    case = db.query(models.FraudCase).filter(models.FraudCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.outcome = outcome
    case.analyst_notes = notes
    if outcome in ["confirmed", "false_positive"]:
        case.closed_at = datetime.now()
        db.commit()
        
        # Increment global counter and check threshold
        global NEW_LABELS_COUNT
        NEW_LABELS_COUNT += 1
        from ..config import settings
        if NEW_LABELS_COUNT >= settings.RETRAIN_MIN_LABELS:
            NEW_LABELS_COUNT = 0
            from ..main import trigger_background_retrain
            trigger_background_retrain()
    else:
        db.commit()
    return {"status": "updated"}

@router.get("/dashboard/stats")
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

@router.get("/alerts/live")
async def live_alerts():
    """
    Server-Sent Events (SSE) streaming endpoint for live transaction decisions and alerts.
    """
    queue = asyncio.Queue()
    alert_listeners.append(queue)
    
    async def event_generator():
        try:
            # Yield initial connection confirmation event
            yield f"data: {json.dumps({'type': 'CONNECTED', 'message': 'Successfully connected to PayShield Live Stream'})}\n\n"
            
            while True:
                event_data = await queue.get()
                yield f"data: {json.dumps(event_data)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in alert_listeners:
                alert_listeners.remove(queue)
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/alerts/history", response_model=List[schemas.AlertResponse])
def get_alerts_history(db: Session = Depends(get_db)):
    alerts = db.query(models.Alert).order_by(models.Alert.timestamp.desc()).limit(50).all()
    return alerts




@router.post('/transaction/submit')
async def submit_manual_transaction(req: ManualTransactionRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Accept a simplified manual transaction from the UI and route through the scoring pipeline."""
    # Build a full TransactionScoreRequest from the simplified input
    from ..schemas.schemas import TransactionScoreRequest, DeviceSignal, BehaviorSignal

    # Look up user's existing device and behavior, or use defaults
    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f'User {req.user_id} not found. Seed the database first.')

    device = db.query(models.Device).filter(models.Device.user_id == req.user_id).first()
    behavior = db.query(models.BehaviorProfile).filter(models.BehaviorProfile.user_id == req.user_id).first()

    score_req = TransactionScoreRequest(
        user_id=req.user_id,
        amount=req.amount,
        currency='INR',
        channel=req.channel,
        target_account=req.target_account,
        beneficiary_name=req.beneficiary_name or 'Manual Entry',
        beneficiary_added_at=datetime.now() - timedelta(days=30),
        device=DeviceSignal(
            device_hash=device.device_hash if device else 'manual_device',
            browser=device.browser if device else 'Chrome',
            os=device.os if device else 'Windows',
            ip_address=device.ip_address if device else '127.0.0.1',
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
    return await score_transaction(score_req, background_tasks, db)


@router.post('/webhook/ingest')
async def webhook_ingest(req: WebhookTransactionRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Accept transactions from external systems (bank core, payment switch)."""
    from ..schemas.schemas import TransactionScoreRequest, DeviceSignal, BehaviorSignal

    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        user = models.User(id=req.user_id, username=f'{req.user_id}_webhook', is_fraudster=False)
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
    return await score_transaction(score_req, background_tasks, db)

from pydantic import BaseModel

class ScamAnalyzeRequest(BaseModel):
    remarks: str

@router.post("/transactions/create", response_model=schemas.DecisionResponse)
async def transactions_create(
    req: schemas.TransactionScoreRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    return await score_transaction(req, background_tasks, db)

@router.post("/risk/evaluate", response_model=schemas.DecisionResponse)
async def risk_evaluate(
    req: schemas.TransactionScoreRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    return await score_transaction(req, background_tasks, db)

@router.post("/behavior/collect", response_model=schemas.BehaviorProfileResponse)
def behavior_collect(behavior: schemas.BehaviorCapture, db: Session = Depends(get_db)):
    return capture_behavior(behavior, db)

@router.post("/scam/analyze")
def scam_analyze(req: ScamAnalyzeRequest):
    from ..services.scam_detector import ScamDetectorService
    analysis = ScamDetectorService.analyze_remarks(req.remarks)
    return analysis

@router.get("/dashboard/alerts", response_model=List[schemas.AlertResponse])
def get_dashboard_alerts(db: Session = Depends(get_db)):
    return get_alerts_history(db)

@router.get("/dashboard/live")
async def get_dashboard_live():
    return await live_alerts()

@router.get("/investigation/{transaction_id}")
def get_transaction_investigation(transaction_id: str, db: Session = Depends(get_db)):
    tx = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    user = db.query(models.User).filter(models.User.id == tx.user_id).first()
    devices = db.query(models.Device).filter(models.Device.user_id == tx.user_id).all()
    history = db.query(models.Transaction).filter(
        models.Transaction.user_id == tx.user_id
    ).order_by(models.Transaction.timestamp.asc()).all()
    
    timeline = []
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
        
    timeline = [evt for evt in timeline if evt["timestamp"] is not None]
    timeline.sort(key=lambda x: x["timestamp"])
    
    location_hops = []
    for t in history:
        if t.city or t.country:
            location_hops.append({
                "city": t.city or "Unknown",
                "country": t.country or "Unknown",
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "lat": t.latitude,
                "lng": t.longitude
            })
            
    profile = db.query(models.BehaviorProfile).filter(models.BehaviorProfile.user_id == tx.user_id).first()
    
    explanation_data = {}
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


@router.post("/razorpay/order", response_model=schemas.RazorpayOrderResponse)
def create_razorpay_order(req: schemas.RazorpayOrderRequest, db: Session = Depends(get_db)):
    import os
    import requests
    
    tx = db.query(models.Transaction).filter(models.Transaction.id == req.transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if tx.status == "BLOCK" or tx.risk_decision == "BLOCK":
        raise HTTPException(status_code=400, detail="Transaction blocked by PayShield. Payment not allowed.")
        
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    
    amount_in_paise = int(req.amount * 100)
    
    if key_id and key_secret:
        try:
            # Call real Razorpay API in Test Mode (using keys provided by user)
            url = "https://api.razorpay.com/v1/orders"
            payload = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": f"receipt_{req.transaction_id[:20]}"
            }
            res = requests.post(url, json=payload, auth=(key_id, key_secret), timeout=10)
            if res.status_code == 200:
                data = res.json()
                return schemas.RazorpayOrderResponse(
                    order_id=data["id"],
                    key_id=key_id,
                    amount=req.amount,
                    currency="INR",
                    status=data.get("status", "created")
                )
            else:
                # Fall back if API returns an error
                print(f"[Razorpay] API Error {res.status_code}: {res.text}")
        except Exception as e:
            print(f"[Razorpay] Connection Exception: {e}")
            
    # Fallback / Mock order if key not set or API failed
    mock_order_id = f"order_mock_{uuid.uuid4().hex[:14]}"
    return schemas.RazorpayOrderResponse(
        order_id=mock_order_id,
        key_id=key_id or "rzp_test_placeholder_key",
        amount=req.amount,
        currency="INR",
        status="created"
    )

@router.post("/razorpay/success")
async def razorpay_success(req: schemas.RazorpaySuccessRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    tx = db.query(models.Transaction).filter(models.Transaction.id == req.transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    user = db.query(models.User).filter(models.User.id == tx.user_id).first()
    
    # Update status to ALLOW and store payment details in risk_explanation JSON
    tx.status = "ALLOW"
    explanation_data = {}
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
    
    # Broadcast TRANSACTION_PAID / transaction success event to live SSE feed
    event = {
        "type": "TRANSACTION_SCORED",  # keep same event type so frontend LiveFeed receives it
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


@router.get("/model/metrics")
def get_model_metrics(db: Session = Depends(get_db)):
    active_models = db.query(models.ModelRegistry).filter(models.ModelRegistry.is_active == True).all()
    res = {}
    for m in active_models:
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


@router.get("/metrics/latency")
def get_latency_ms_metrics(db: Session = Depends(get_db)):
    txs = db.query(models.Transaction.latency_ms).filter(
        models.Transaction.latency_ms != None
    ).order_by(models.Transaction.timestamp.desc()).limit(100).all()
    
    latencies = [t[0] for t in txs if t[0] is not None]
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "count": 0}
        
    import numpy as np
    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    p99 = float(np.percentile(latencies, 99))
    return {
        "p50": round(p50, 2),
        "p95": round(p95, 2),
        "p99": round(p99, 2),
        "count": len(latencies)
    }


