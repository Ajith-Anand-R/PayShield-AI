"""
Health and readiness probes.

GET /health  — liveness:  always returns 200 {"status": "ok"}
GET /ready   — readiness: checks DB, Redis, and ML model; returns 200 when
               all subsystems are up, 503 when any fail.

These endpoints are intentionally NOT behind API-key auth so that
load-balancers, k8s probes, and Docker healthchecks can reach them
without credentials.
"""
from fastapi import APIRouter, Response
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health() -> dict:
    """Always returns 200 while the Python process is alive."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
def ready(response: Response) -> dict:
    """
    Returns 200 with a per-component status map when all subsystems are up.
    Returns 503 when any required subsystem is unavailable.
    """
    status: dict[str, str] = {}
    all_ok = True

    # ── Database ────────────────────────────────────────────────────────────
    try:
        from ..database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        status["database"] = "ok"
    except Exception as exc:
        status["database"] = f"error: {exc}"
        all_ok = False

    # ── Redis ───────────────────────────────────────────────────────────────
    try:
        from ..services.redis_client import get_redis
        r = get_redis()
        # MemoryRedis has no ping() — treat its presence as healthy.
        if hasattr(r, "ping"):
            r.ping()
        status["redis"] = "ok"
    except Exception as exc:
        status["redis"] = f"error: {exc}"
        all_ok = False

    # ── ML anomaly model ────────────────────────────────────────────────────
    try:
        from ..engines.anomaly import TransactionAnomalyEngine
        if TransactionAnomalyEngine._model is None:
            status["ml_model"] = "not_loaded"
            all_ok = False
        else:
            status["ml_model"] = "ok"
    except Exception as exc:
        status["ml_model"] = f"error: {exc}"
        all_ok = False

    if not all_ok:
        response.status_code = 503

    return {"status": "ready" if all_ok else "degraded", "components": status}
