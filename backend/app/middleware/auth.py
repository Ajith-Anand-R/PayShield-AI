"""
API-key authentication dependency.

Usage (in a router):
    from ..middleware.auth import require_api_key

    @router.post("/transaction/score")
    async def score(req: ..., client: models.ApiClient = Depends(require_api_key)):
        ...

When settings.AUTH_ENABLED is False, the dependency is a no-op (returns None).
This lets developers disable auth during local UI work by setting AUTH_ENABLED=false
in their .env.
"""
import hashlib
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import models


def _hash_key(raw_key: str) -> str:
    """SHA-256 hex-digest of a raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    db: Session = Depends(get_db),
) -> models.ApiClient | None:
    """
    FastAPI dependency that validates the X-API-Key header.

    - If AUTH_ENABLED is False → skips validation and returns None.
    - If AUTH_ENABLED is True and header is missing / unknown / inactive → raises 401.
    - Returns the matched ApiClient on success.
    """
    if not settings.AUTH_ENABLED:
        return None

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header. Obtain a key from the PayShield admin.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_hash = _hash_key(x_api_key)
    client = (
        db.query(models.ApiClient)
        .filter(models.ApiClient.api_key_hash == key_hash, models.ApiClient.is_active.is_(True))
        .first()
    )

    if not client:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return client


# Convenience alias — avoids importing `Depends` in every router file.
ApiKeyDep = Annotated[models.ApiClient | None, Depends(require_api_key)]


def seed_default_dev_client(db: Session) -> None:
    """
    Idempotently create the 'default-dev' ApiClient row on first boot.

    Called from the FastAPI lifespan so the app works out-of-the-box with
    settings.DEFAULT_DEV_API_KEY.  Does nothing if a client already exists.
    """
    if db.query(models.ApiClient).count() > 0:
        return  # already seeded

    import uuid
    dev_key = settings.DEFAULT_DEV_API_KEY
    dev_client = models.ApiClient(
        id=str(uuid.uuid4()),
        name="default-dev",
        api_key_hash=_hash_key(dev_key),
        is_active=True,
        rate_limit_per_min=settings.DEFAULT_RATE_LIMIT,
    )
    db.add(dev_client)
    db.commit()
    print(
        f"[PayShield Auth] Seeded default-dev API client. "
        f"Use header: X-API-Key: {dev_key}"
    )
