from contextlib import asynccontextmanager
import asyncio
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .database import engine, Base, SessionLocal
from .config import settings
from .routes.api import router
from .routers import identity, scoring, dashboard, cases, payments, health
from .middleware.rate_limit import limiter
from .engines.anomaly import TransactionAnomalyEngine
from .engines.graph import FraudGraphEngine
from .models import models

# Create database tables
Base.metadata.create_all(bind=engine)


async def periodic_graph_sync():
    """Periodically syncs graph from DB to prevent drift (every 5 minutes)."""
    while True:
        try:
            await asyncio.sleep(300)
            from .database import SessionLocal
            db = SessionLocal()
            try:
                from .engines.graph import FraudGraphEngine
                FraudGraphEngine.sync_graph_from_db(db)
                print("[PayShield] Periodic fraud graph sync complete.")
            except Exception as e:
                print(f"[PayShield] Error in periodic graph sync: {e}")
            finally:
                db.close()
        except asyncio.CancelledError:
            break

# Initialize BackgroundScheduler
scheduler = BackgroundScheduler()

def retrain_job():
    """Triggered by scheduler to retrain ML models and hot-reload singletons in memory."""
    from .database import SessionLocal
    from .engines.training import train_all_engines, hot_reload_all_models
    db = SessionLocal()
    try:
        print("[PayShield Scheduler] Starting background retraining...")
        train_all_engines(db)
        hot_reload_all_models()
        print("[PayShield Scheduler] Background retraining complete and models reloaded.")
    except Exception as e:
        print(f"[PayShield Scheduler] Error during background retraining: {e}")
    finally:
        db.close()

def trigger_background_retrain():
    """Triggers retraining in the scheduler background thread immediately."""
    try:
        scheduler.add_job(
            retrain_job,
            trigger='date',
            run_date=datetime.now(),
            id='immediate_retrain',
            name='Immediate Retrain',
            replace_existing=True
        )
        print("[PayShield Scheduler] Asynchronous background retrain triggered.")
    except Exception as e:
        print(f"[PayShield Scheduler] Failed to trigger background retrain: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages startup and shutdown lifecycle."""
    print("[PayShield] Starting up...")

    # Train ML and sync graph on boot
    db = SessionLocal()
    try:
        from .engines.training import train_all_engines, hot_reload_all_models
        train_all_engines(db)
        hot_reload_all_models()
        print("[PayShield] All ML decision engines and fusion model trained and ready.")
        FraudGraphEngine.load_graph()
        FraudGraphEngine.sync_graph_from_db(db)
        print("[PayShield] Fraud graph synced.")
    except Exception as e:
        print(f"[PayShield] Engine init error: {e}")
    finally:
        db.close()

    # Seed the default-dev API client if the api_clients table is empty
    if settings.AUTH_ENABLED:
        db = SessionLocal()
        try:
            from .middleware.auth import seed_default_dev_client
            seed_default_dev_client(db)
        except Exception as e:
            print(f"[PayShield] Auth seed error: {e}")
        finally:
            db.close()

    # Start periodic graph sync task in background
    sync_task = asyncio.create_task(periodic_graph_sync())

    # Start APScheduler
    try:
        scheduler.add_job(
            retrain_job,
            trigger='interval',
            hours=settings.RETRAIN_INTERVAL_HOURS,
            id='periodic_retrain',
            name='Periodic Retrain',
            replace_existing=True
        )
        scheduler.start()
        print(f"[PayShield Startup] Scheduler started. Periodic retraining every {settings.RETRAIN_INTERVAL_HOURS} hours.")
    except Exception as se:
        print(f"[PayShield Startup] Failed to start scheduler: {se}")

    yield  # App is running

    # Shutdown APScheduler
    try:
        scheduler.shutdown()
        print("[PayShield Shutdown] Scheduler stopped.")
    except Exception:
        pass

    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass

    print("[PayShield] Shut down complete.")


app = FastAPI(
    title="PayShield: Real-Time Payment Authorization Risk Middleware",
    description="Fuses Behavioral DNA, Device Trust, ML Anomaly, and Graph intelligence to stop fraud.",
    version="2.0.0",
    lifespan=lifespan
)

# ── Rate limiting ────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health probes (no auth) ───────────────────────────────────────────────────
app.include_router(health.router)

# ── Legacy monolith — kept alive so frontend paths don't break ────────────────
app.include_router(router)

# ── Phase-4 modular routers ───────────────────────────────────────────────────
app.include_router(identity.router)
app.include_router(scoring.router)
app.include_router(dashboard.router)
app.include_router(cases.router)
app.include_router(payments.router)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "PayShield Risk Middleware",
        "version": "2.0.0 — Production Mode",
        "auth_enabled": settings.AUTH_ENABLED,
        "thresholds": {
            "allow": settings.THRESH_ALLOW,
            "step_up": settings.THRESH_STEP_UP,
            "delay": settings.THRESH_DELAY
        }
    }
