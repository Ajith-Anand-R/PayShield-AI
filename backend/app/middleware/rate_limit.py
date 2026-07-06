"""
Rate-limiting setup using slowapi.

A single `Limiter` instance is shared across the app.  The key function
uses the X-API-Key header value (when present) so rate limits are
per-client rather than per-IP — important when many users sit behind
the same NAT.

Usage (in main.py):
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from .middleware.rate_limit import limiter

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Usage (in a route — optional, for endpoint-specific overrides):
    from .middleware.rate_limit import limiter
    from slowapi import Request

    @router.post("/transaction/score")
    @limiter.limit("60/minute")
    async def score(request: Request, ...):
        ...

The global default limit is read from settings.DEFAULT_RATE_LIMIT.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..config import settings


def _key_func(request) -> str:  # type: ignore[no-untyped-def]
    """
    Rate-limit key: prefer the X-API-Key header so limits are per-client;
    fall back to the remote IP for unauthenticated callers.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_key_func,
    default_limits=[f"{settings.DEFAULT_RATE_LIMIT}/minute"],
    # Storage backend: use Redis when available, in-memory otherwise.
    # slowapi reads the SLOWAPI_STORAGE_URI env var automatically when set,
    # but we keep it simple here and let the default in-memory store serve.
    # Phase 7 can wire settings.REDIS_URL here for distributed rate limiting.
)
