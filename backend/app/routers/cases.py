"""
Cases router — fraud case management and analyst feedback loop.

Prefix: /api/cases
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..services.audit import log_case_action

router = APIRouter(prefix="/api/cases", tags=["cases"])

# Module-level counter for labels accumulated since the last retrain trigger.
# Phase 5 will move this to a Redis atomic counter.
_new_labels_count: int = 0


@router.get("/", response_model=List[schemas.FraudCaseResponse],
            summary="List the 20 most-recent fraud cases")
def list_cases(db: Session = Depends(get_db)):
    return (
        db.query(models.FraudCase)
        .order_by(models.FraudCase.opened_at.desc())
        .limit(20)
        .all()
    )


@router.patch("/{case_id}", summary="Update a case outcome and optionally trigger model retraining")
def update_case(
    case_id: str,
    outcome: str,
    notes: str = "",
    db: Session = Depends(get_db),
):
    """
    Set the analyst verdict on a fraud case.

    *outcome* must be one of: ``confirmed``, ``false_positive``, ``pending``.

    When the number of newly labelled cases since the last retrain crosses
    ``settings.RETRAIN_MIN_LABELS``, a background retraining job is triggered.
    """
    global _new_labels_count

    case = db.query(models.FraudCase).filter(models.FraudCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case.outcome = outcome
    case.analyst_notes = notes

    if outcome in ("confirmed", "false_positive"):
        case.closed_at = datetime.now()
        log_case_action(db, case_id=case_id, outcome=outcome, actor="analyst", notes=notes)
        db.commit()

        _new_labels_count += 1
        from ..config import settings
        if _new_labels_count >= settings.RETRAIN_MIN_LABELS:
            _new_labels_count = 0
            from ..main import trigger_background_retrain
            trigger_background_retrain()
    else:
        log_case_action(db, case_id=case_id, outcome=outcome, actor="analyst", notes=notes)
        db.commit()

    return {"status": "updated"}
