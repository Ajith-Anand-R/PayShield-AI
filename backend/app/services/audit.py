"""
Structured audit logging and AuditLog DB writes.

Two concerns are merged here intentionally:
  1. Python stdlib JSON logging — every audit event is also emitted as a
     structured JSON log line so it's queryable in log-aggregation tools
     (Loki, CloudWatch, Datadog, etc.).
  2. AuditLog DB rows — written for regulatory reporting (every scoring
     decision and every analyst case action must be traceable).

Usage:
    from ..services.audit import log_decision, log_case_action, get_logger

    # In scoring pipeline:
    log_decision(db, transaction_id="txn-123", decision="BLOCK", actor="api-client-name")

    # In cases router:
    log_case_action(db, case_id="case-456", outcome="confirmed", actor="analyst-007")

    # Arbitrary structured log:
    logger = get_logger(__name__)
    logger.info("event", extra={"transaction_id": "...", "latency_ms": 12.3})
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import models


# ---------------------------------------------------------------------------
# JSON log formatter
# ---------------------------------------------------------------------------

class _JsonFormatter(logging.Formatter):
    """Emit every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via `extra={...}`
        for key, val in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "module", "msecs", "message", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "taskName",
            ):
                payload[key] = val
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger that emits JSON-formatted lines to stdout.

    The logger is idempotent — calling it multiple times with the same *name*
    returns the same instance without adding duplicate handlers.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# Module-level logger used by this module's own helpers.
_logger = get_logger("payshield.audit")


# ---------------------------------------------------------------------------
# DB audit writers
# ---------------------------------------------------------------------------

def log_decision(
    db: Session,
    *,
    transaction_id: str,
    decision: str,
    actor: str = "system",
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Write an AuditLog row for a risk decision and emit a JSON log line.

    :param db:             Active SQLAlchemy session (caller owns commit).
    :param transaction_id: UUID of the scored transaction.
    :param decision:       One of ALLOW / STEP_UP / REVIEW / BLOCK.
    :param actor:          ApiClient.name or "system" for background jobs.
    :param extra:          Optional dict merged into the detail_json field.
    """
    detail = {"decision": decision, **(extra or {})}
    row = models.AuditLog(
        actor=actor,
        action="SCORE_DECISION",
        entity="transaction",
        entity_id=transaction_id,
        detail_json=json.dumps(detail, default=str),
    )
    db.add(row)
    # Note: the caller is responsible for db.commit() so this is batched
    # with the transaction row commit — no extra round-trip.

    _logger.info(
        "score_decision",
        extra={
            "transaction_id": transaction_id,
            "decision": decision,
            "actor": actor,
            **(extra or {}),
        },
    )


def log_case_action(
    db: Session,
    *,
    case_id: str,
    outcome: str,
    actor: str = "analyst",
    notes: str = "",
) -> None:
    """
    Write an AuditLog row for an analyst case action and emit a JSON log line.

    :param db:      Active SQLAlchemy session (caller owns commit).
    :param case_id: UUID of the fraud case.
    :param outcome: confirmed / false_positive / pending / etc.
    :param actor:   Analyst identifier (ApiClient.name or username if available).
    :param notes:   Analyst notes (trimmed to 500 chars).
    """
    detail = {"outcome": outcome, "notes": notes[:500]}
    row = models.AuditLog(
        actor=actor,
        action="CASE_UPDATED",
        entity="fraud_case",
        entity_id=case_id,
        detail_json=json.dumps(detail, default=str),
    )
    db.add(row)

    _logger.info(
        "case_updated",
        extra={
            "case_id": case_id,
            "outcome": outcome,
            "actor": actor,
        },
    )
