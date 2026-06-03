from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import json
import asyncio
import threading
from datetime import datetime, timedelta
from typing import List

from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..engines.behavioral import BehavioralEngine
from ..engines.device import DeviceTrustEngine
from ..engines.anomaly import TransactionAnomalyEngine
from ..engines.graph import FraudGraphEngine
from ..services.fusion import RiskFusionEngine
from ..schemas.stream_schemas import StreamConfigRequest, StreamStatusResponse, ManualTransactionRequest, WebhookTransactionRequest
from ..services.stream_generator import stream_generator

router = APIRouter(prefix="/api")

# Live alert listeners (in-memory pub/sub)
alert_listeners = []
seed_lock = threading.Lock()

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

@router.post("/auth/login", response_model=schemas.UserResponse)
def login(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_data.id).first()
    if not db_user:
        db_user = models.User(
            id=user_data.id,
            username=user_data.username,
            is_fraudster=user_data.is_fraudster
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
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
            is_trusted=True
        )
        db.add(db_device)
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

def retrain_anomaly_model_bg():
    """
    Background anomaly engine training runner that manages its own database session,
    ensuring thread safety and session closure independent of FastAPI's request lifecycle.
    """
    from ..database import SessionLocal
    bg_db = SessionLocal()
    try:
        TransactionAnomalyEngine.train_model(bg_db)
    except Exception as e:
        print(f"[PayShield] Background anomaly retraining failed: {e}")
    finally:
        bg_db.close()

@router.post("/transaction/score", response_model=schemas.DecisionResponse)
async def score_transaction(
    req: schemas.TransactionScoreRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
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
        channel=req.channel,
        currency=req.currency,
        status="PENDING"
    )
    db.add(db_tx)
    
    # 2. Run behavioral trust check
    behavioral_score = BehavioralEngine.calculate_risk(db, req.user_id, req.behavior)
    
    # 3. Run device fingerprint trust check
    device_score = DeviceTrustEngine.calculate_risk(db, req.user_id, req.device)
    
    # 4. Run transaction anomaly model
    anomaly_score, anomaly_signals = TransactionAnomalyEngine.calculate_risk(
        db,
        req.user_id,
        req.amount,
        req.device.location,
        beneficiary_age_hours=beneficiary_age_hours,
        new_beneficiary=new_beneficiary
    )
    
    # 5. Run graph ring analysis
    graph_score = FraudGraphEngine.calculate_risk(db, req.user_id, req.device.device_hash, req.target_account)
    
    # Bundle sub-scores
    scores = schemas.RiskScoreResponse(
        behavioral_score=behavioral_score,
        device_score=device_score,
        anomaly_score=anomaly_score,
        graph_score=graph_score,
        total_score=0.0
    )
    
    # 6. Risk fusion and final decision (commits both db_tx and new sub-score records together)
    decision_resp = RiskFusionEngine.fuse_and_decide(db, transaction_id, req.user_id, req, scores, anomaly_signals)
    
    # 7. Update Transaction Record with decision mapping and finalize DB state
    status_map = {
        "ALLOW": "ALLOWED",
        "BLOCK": "BLOCKED",
        "STEP_UP": "STEP_UP_REQUIRED",
        "DELAY": "PENDING_DELAY"
    }
    tx_status = status_map.get(decision_resp.decision, "ALLOWED")
    db_tx.status = tx_status
    db_tx.risk_score = decision_resp.risk_score
    db_tx.risk_decision = decision_resp.decision
    db_tx.risk_explanation = json.dumps({
        "reason_codes": decision_resp.reason_codes,
        "breakdown": decision_resp.breakdown.model_dump()
    })
    if db_beneficiary:
        db_beneficiary.txn_count = (db_beneficiary.txn_count or 0) + 1
        db_beneficiary.total_sent = (db_beneficiary.total_sent or 0.0) + req.amount
    db.commit()
    
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
            "timestamp": datetime.now().isoformat()
        }
    }
    
    # Broadcast in background
    background_tasks.add_task(broadcast_alert, event)
    
    # Trigger Isolation Forest retraining if the transaction was ALLOWED
    # to slowly adapt to drift, utilizing a safe background DB session
    if tx_status == "ALLOWED":
        background_tasks.add_task(retrain_anomaly_model_bg)
        
    return decision_resp

@router.post("/simulate/event")
async def simulate_event(req: schemas.SimulateEventRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Injects a pre-configured scenario payload directly into the scoring pipeline.
    This is what the frontend demo buttons call.
    """
    SCENARIO_PAYLOADS = {
        "normal": {
            "user_id": "user_alice",
            "amount": 5000.0,
            "currency": "INR",
            "channel": "UPI",
            "target_account": "acc_usual_vendor",
            "beneficiary_name": "Regular Vendor",
            "beneficiary_added_at": (datetime.now() - timedelta(days=90)).isoformat(),
            "device": {
                "device_hash": "device_alice_macbook",
                "browser": "Chrome", "os": "macOS",
                "ip_address": "192.168.1.50",
                "location": "Chennai, IN"
            },
            "behavior": {
                "keystroke_dwell": 0.10, "keystroke_flight": 0.15,
                "mouse_speed": 250.0, "mouse_jitter": 12.0, "scroll_velocity": 80.0
            }
        },
        "ato": {
            "user_id": "user_alice",
            "amount": 95000.0,
            "currency": "INR",
            "channel": "IMPS",
            "target_account": "acc_raj_traders",
            "beneficiary_name": "Raj Traders",
            "beneficiary_added_at": (datetime.now() - timedelta(minutes=4)).isoformat(),
            "device": {
                "device_hash": "device_attacker_nigeria",
                "browser": "Firefox", "os": "Windows",
                "ip_address": "41.203.0.1",
                "location": "Lagos, NG"
            },
            "behavior": {
                "keystroke_dwell": 0.01, "keystroke_flight": 0.01,
                "mouse_speed": 0.0, "mouse_jitter": 0.0, "scroll_velocity": 0.0
            }
        },
        "fraud_ring": {
            "user_id": "user_ring_member",
            "amount": 25000.0,
            "currency": "INR",
            "channel": "NEFT",
            "target_account": "acc_mule_account_1",
            "beneficiary_name": "Mule Outlet",
            "beneficiary_added_at": (datetime.now() - timedelta(hours=2)).isoformat(),
            "device": {
                "device_hash": "device_compromised_root",
                "browser": "Opera", "os": "Linux",
                "ip_address": "203.0.113.12",
                "location": "Unknown"
            },
            "behavior": {
                "keystroke_dwell": 0.08, "keystroke_flight": 0.12,
                "mouse_speed": 180.0, "mouse_jitter": 8.0, "scroll_velocity": 60.0
            }
        },
        "sim_swap": {
            "user_id": "user_bob",
            "amount": 45000.0,
            "currency": "INR",
            "channel": "UPI",
            "target_account": "acc_new_payee_bob",
            "beneficiary_name": "Unknown Payee",
            "beneficiary_added_at": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "device": {
                "device_hash": "device_bob_new_phone",
                "browser": "Chrome", "os": "Android",
                "ip_address": "10.0.0.1",
                "location": "Mumbai, IN"
            },
            "behavior": {
                "keystroke_dwell": 0.09, "keystroke_flight": 0.14,
                "mouse_speed": 220.0, "mouse_jitter": 5.0, "scroll_velocity": 75.0
            }
        }
    }
    
    payload_data = SCENARIO_PAYLOADS.get(req.scenario)
    if not payload_data:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")
    
    if req.user_id:
        payload_data["user_id"] = req.user_id
    
    score_req = schemas.TransactionScoreRequest(**payload_data)
    return await score_transaction(score_req, background_tasks, db)

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
    
    amounts = [t.amount for t in transactions if t.status == "ALLOWED"]
    avg_amount = sum(amounts) / len(amounts) if amounts else 0
    
    return {
        "user": {"id": user.id, "username": user.username},
        "stats": {
            "total_transactions": len(transactions),
            "avg_amount": round(avg_amount, 2),
            "blocked_count": sum(1 for t in transactions if t.status == "BLOCKED"),
            "step_up_count": sum(1 for t in transactions if t.status == "STEP_UP_REQUIRED")
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
    return {"status": "updated"}

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(models.Transaction).count()
    blocked = db.query(models.Transaction).filter(models.Transaction.status == "BLOCKED").count()
    step_up = db.query(models.Transaction).filter(models.Transaction.status == "STEP_UP_REQUIRED").count()
    allowed = db.query(models.Transaction).filter(models.Transaction.status == "ALLOWED").count()
    
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

@router.post("/simulation/seed")
def seed_simulation(db: Session = Depends(get_db)):
    """
    Seeds database with user baselines, normal transaction history to train ML,
    and sets up the graph entities and connections.
    """
    if not seed_lock.acquire(blocking=False):
        return {"message": "Seed already in progress"}

    try:
        # 1. Clear database tables
        db.query(models.Alert).delete(synchronize_session=False)
        db.query(models.DecisionLog).delete(synchronize_session=False)
        db.query(models.RiskScore).delete(synchronize_session=False)
        db.query(models.Transaction).delete(synchronize_session=False)
        db.query(models.FraudCase).delete(synchronize_session=False)
        db.query(models.GraphEdge).delete(synchronize_session=False)
        db.query(models.Beneficiary).delete(synchronize_session=False)
        db.query(models.Session).delete(synchronize_session=False)
        db.query(models.BehaviorProfile).delete(synchronize_session=False)
        db.query(models.Device).delete(synchronize_session=False)
        db.query(models.User).delete(synchronize_session=False)
        db.commit()

        # 2. Add Users
        alice = models.User(id="user_alice", username="alice_chennai", is_fraudster=False)
        bob = models.User(id="user_bob", username="bob_mumbai", is_fraudster=False)
        mallory = models.User(id="user_mallory", username="mallory_fraud", is_fraudster=True)
        mule = models.User(id="user_mule", username="mule_account", is_fraudster=False)
        ring_users = ["user_ring_a", "user_ring_b", "user_ring_c", "user_ring_d", "user_ring_member"]
        sender_users = ["user_sender_1", "user_sender_2"]
        
        for u in [alice, bob, mallory, mule]:
            db.add(u)
        for uid in ring_users + sender_users:
            db.add(models.User(id=uid, username=f"{uid}_acct", is_fraudster=False))
        
        db.commit()

        # 3. Seed Alice's Behavioral Baseline
        # Standard dwell time: ~0.10s, flight: ~0.15s, mouse speed: ~250px/s, scroll speed: ~80px/s
        alice_behavior = models.BehaviorProfile(
            user_id="user_alice",
            keystroke_dwell_avg=0.10,
            keystroke_flight_avg=0.15,
            mouse_speed_avg=250.0,
            mouse_jitter_avg=12.0,
            scroll_velocity_avg=80.0
        )
        db.add(alice_behavior)
        
        bob_behavior = models.BehaviorProfile(
            user_id="user_bob",
            keystroke_dwell_avg=0.12,
            keystroke_flight_avg=0.18,
            mouse_speed_avg=200.0,
            mouse_jitter_avg=10.0,
            scroll_velocity_avg=70.0
        )
        db.add(bob_behavior)
        
        db.commit()

        # 4. Seed Alice and Bob's Trusted Devices
        alice_device = models.Device(
            user_id="user_alice",
            device_hash="device_alice_macbook",
            browser="Chrome",
            os="macOS",
            ip_address="192.168.1.50",
            location="Chennai, IN",
            is_trusted=True
        )
        db.add(alice_device)
        
        bob_device = models.Device(
            user_id="user_bob",
            device_hash="device_bob_windows",
            browser="Firefox",
            os="Windows",
            ip_address="192.168.1.75",
            location="Mumbai, IN",
            is_trusted=True
        )
        db.add(bob_device)
        
        for uid in ring_users:
            db.add(models.Device(
                user_id=uid,
                device_hash="device_compromised_root",
                browser="Chrome",
                os="Android",
                ip_address="203.0.113.50",
                location="Unknown",
                is_trusted=False
            ))
        
        mallory_device = models.Device(
            user_id="user_mallory",
            device_hash="device_compromised_root",
            browser="Opera",
            os="Linux",
            ip_address="203.0.113.12",
            location="Unknown",
            is_trusted=False
        )
        db.add(mallory_device)
        
        db.commit()

        # 5. Seed Historical Normal Transactions (To train ML Anomaly Engine)
        # Alice has 50 normal INR transactions
        base_time = datetime.now() - timedelta(days=30)
        for i in range(50):
            timestamp = base_time + timedelta(hours=i * 12)
            tx = models.Transaction(
                id=f"tx_alice_seed_{i}",
                user_id="user_alice",
                amount=7500.0 + (i % 5) * 500.0,
                timestamp=timestamp,
                target_account=f"acc_vendor_{i % 3}",
                device_hash="device_alice_macbook",
                location="Chennai, IN",
                channel="UPI",
                currency="INR",
                status="ALLOWED"
            )
            db.add(tx)
            
            score = models.RiskScore(
                transaction_id=tx.id,
                behavioral_score=5.0,
                device_score=0.0,
                anomaly_score=10.0,
                graph_score=0.0,
                total_score=4.5
            )
            db.add(score)
            
        db.commit()
        
        # 6. Seed Mallory's connection to Fraud ring in the graph
        mallory_tx = models.Transaction(
            id="tx_mallory_fraudulent",
            user_id="user_mallory",
            amount=5000.0,
            target_account="acc_mule_account_1",
            device_hash="device_compromised_root",
            location="Unknown",
            channel="NEFT",
            currency="INR",
            status="BLOCKED"
        )
        db.add(mallory_tx)
        
        # 7. Mule account activity (many inbound, single outbound)
        inbound_senders = ring_users[:4] + ["user_bob", "user_sender_1", "user_sender_2"]
        for idx, sender in enumerate(inbound_senders):
            db.add(models.Transaction(
                id=f"tx_mule_in_{idx}",
                user_id=sender,
                amount=1200.0 + idx * 150.0,
                target_account="user_mule",
                device_hash=f"device_{sender}_phone",
                location="Delhi, IN",
                channel="UPI",
                currency="INR",
                status="ALLOWED"
            ))
        
        db.add(models.Transaction(
            id="tx_mule_out_1",
            user_id="user_mule",
            amount=120000.0,
            target_account="acc_cashout_1",
            device_hash="device_mule_terminal",
            location="Delhi, IN",
            channel="IMPS",
            currency="INR",
            status="ALLOWED"
        ))
        
        db.commit()
        
        # Train anomaly forest model on startup seed
        TransactionAnomalyEngine.train_model(db)
        # Sync graph
        FraudGraphEngine.sync_graph_from_db(db)

        return {"message": "Database seeded and engines prepared successfully"}
    finally:
        seed_lock.release()


# ============================================================
# REAL-TIME STREAM CONTROL ENDPOINTS
# ============================================================

async def _internal_score(tx_req):
    """Internal scoring function for the stream generator."""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        # Ensure user exists
        user = db.query(models.User).filter(models.User.id == tx_req.user_id).first()
        if not user:
            user = models.User(id=tx_req.user_id, username=f"{tx_req.user_id}_auto", is_fraudster=False)
            db.add(user)
            db.commit()
            db.refresh(user)

        # Reuse the core scoring logic
        transaction_id = str(uuid.uuid4())

        beneficiary_age_hours = None
        new_beneficiary = False
        beneficiary_id = None
        if tx_req.beneficiary_added_at:
            from datetime import timezone
            added_at = tx_req.beneficiary_added_at
            if added_at.tzinfo is None:
                added_at = added_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - added_at).total_seconds() / 3600
            beneficiary_age_hours = age
            new_beneficiary = age < 24

        db_beneficiary = None
        if tx_req.beneficiary_name or tx_req.target_account:
            db_beneficiary = db.query(models.Beneficiary).filter(
                models.Beneficiary.user_id == tx_req.user_id,
                models.Beneficiary.account_number == tx_req.target_account
            ).first()

            if not db_beneficiary:
                db_beneficiary = models.Beneficiary(
                    id=str(uuid.uuid4()),
                    user_id=tx_req.user_id,
                    account_number=tx_req.target_account,
                    ifsc=getattr(tx_req, 'beneficiary_ifsc', '') or '',
                    name=tx_req.beneficiary_name or 'Unknown'
                )
                if tx_req.beneficiary_added_at:
                    db_beneficiary.first_added = tx_req.beneficiary_added_at
                db.add(db_beneficiary)

            beneficiary_id = db_beneficiary.id

        from ..services.redis_client import increment_txn_count
        increment_txn_count(tx_req.user_id)

        db_tx = models.Transaction(
            id=transaction_id,
            user_id=tx_req.user_id,
            session_id=tx_req.session_id,
            beneficiary_id=beneficiary_id,
            amount=tx_req.amount,
            target_account=tx_req.target_account,
            device_hash=tx_req.device.device_hash,
            location=tx_req.device.location,
            channel=tx_req.channel,
            currency=tx_req.currency,
            status='PENDING'
        )
        db.add(db_tx)

        behavioral_score = BehavioralEngine.calculate_risk(db, tx_req.user_id, tx_req.behavior)
        device_score = DeviceTrustEngine.calculate_risk(db, tx_req.user_id, tx_req.device)
        anomaly_score, anomaly_signals = TransactionAnomalyEngine.calculate_risk(
            db, tx_req.user_id, tx_req.amount, tx_req.device.location,
            beneficiary_age_hours=beneficiary_age_hours, new_beneficiary=new_beneficiary
        )
        graph_score = FraudGraphEngine.calculate_risk(db, tx_req.user_id, tx_req.device.device_hash, tx_req.target_account)

        from ..schemas.schemas import RiskScoreResponse
        scores = RiskScoreResponse(
            behavioral_score=behavioral_score, device_score=device_score,
            anomaly_score=anomaly_score, graph_score=graph_score, total_score=0.0
        )

        decision_resp = RiskFusionEngine.fuse_and_decide(db, transaction_id, tx_req.user_id, tx_req, scores, anomaly_signals)

        status_map = {"ALLOW": "ALLOWED", "BLOCK": "BLOCKED", "STEP_UP": "STEP_UP_REQUIRED", "DELAY": "PENDING_DELAY"}
        db_tx.status = status_map.get(decision_resp.decision, 'ALLOWED')
        db_tx.risk_score = decision_resp.risk_score
        db_tx.risk_decision = decision_resp.decision
        db_tx.risk_explanation = json.dumps({
            'reason_codes': decision_resp.reason_codes,
            'breakdown': decision_resp.breakdown.model_dump()
        })
        if db_beneficiary:
            db_beneficiary.txn_count = (db_beneficiary.txn_count or 0) + 1
            db_beneficiary.total_sent = (db_beneficiary.total_sent or 0.0) + tx_req.amount
        db.commit()

        # Broadcast SSE event
        event = {
            'type': 'TRANSACTION_SCORED',
            'data': {
                'transaction_id': transaction_id,
                'user_id': tx_req.user_id,
                'username': user.username,
                'amount': tx_req.amount,
                'target_account': tx_req.target_account,
                'decision': decision_resp.decision,
                'risk_score': decision_resp.risk_score,
                'reason_codes': decision_resp.reason_codes,
                'breakdown': decision_resp.breakdown.model_dump(),
                'device': tx_req.device.model_dump(),
                'timestamp': datetime.now().isoformat()
            }
        }
        await broadcast_alert(event)

        # Background retrain for allowed transactions
        if db_tx.status == 'ALLOWED':
            threading.Thread(target=retrain_anomaly_model_bg, daemon=True).start()

        return decision_resp
    except Exception as e:
        print(f'[PayShield Stream] Internal scoring error: {e}')
        db.rollback()
        return None
    finally:
        db.close()


@router.post('/stream/start')
async def start_stream():
    if stream_generator.running:
        return {'message': 'Stream already running', 'status': 'running'}
    stream_generator.start(_internal_score)
    return {'message': 'Transaction stream started', 'status': 'running'}


@router.post('/stream/stop')
async def stop_stream():
    stream_generator.stop()
    return {'message': 'Transaction stream stopped', 'status': 'stopped'}


@router.get('/stream/status', response_model=StreamStatusResponse)
async def get_stream_status():
    return stream_generator.get_status()


@router.patch('/stream/config')
async def update_stream_config(config: StreamConfigRequest):
    if config.speed is not None:
        stream_generator.speed = config.speed
    if config.fraud_rate is not None:
        stream_generator.fraud_rate = config.fraud_rate
    return {'message': 'Stream configuration updated', 'speed': stream_generator.speed, 'fraud_rate': stream_generator.fraud_rate}


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
