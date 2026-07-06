"""
Application settings — loaded from environment variables and an optional .env file.

Usage:
    from .config import settings
    settings.DATABASE_URL   # → value from env or default
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"          # silently ignore unknown env vars
    )

    # -----------------------------------------------------------------------
    # Service identity
    # -----------------------------------------------------------------------
    PROJECT_NAME: str = "PayShield Risk Engine"

    # -----------------------------------------------------------------------
    # Database
    # -----------------------------------------------------------------------
    # Defaults to SQLite so the app runs zero-config on a dev workstation.
    # Override with:  DATABASE_URL=postgresql://user:pass@host:5432/payshield
    DATABASE_URL: str = "sqlite:///./payshield.db"

    # -----------------------------------------------------------------------
    # Redis
    # -----------------------------------------------------------------------
    # "memory" → pure in-process fallback (no Redis needed for dev/tests)
    REDIS_URL: str = "memory"

    # -----------------------------------------------------------------------
    # CORS
    # -----------------------------------------------------------------------
    # Comma-separated list of allowed origins.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # -----------------------------------------------------------------------
    # API-key auth
    # -----------------------------------------------------------------------
    # Set to "false" to disable API-key checking (e.g. during local UI dev).
    AUTH_ENABLED: bool = True
    # Key used by the auto-seeded "default-dev" ApiClient on first boot.
    DEFAULT_DEV_API_KEY: str = "dev-secret"
    # Global fallback rate limit (requests / minute) for unauthenticated or
    # unknown clients (only relevant when AUTH_ENABLED=False).
    DEFAULT_RATE_LIMIT: int = 60

    # -----------------------------------------------------------------------
    # External services
    # -----------------------------------------------------------------------
    GEMINI_API_KEY: str = ""
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # -----------------------------------------------------------------------
    # Risk Fusion Weights
    # Total Risk = Σ weight_i * score_i   (weights should sum to 1.0)
    # -----------------------------------------------------------------------
    WEIGHT_BEHAVIORAL: float = 0.15
    WEIGHT_DEVICE: float = 0.20
    WEIGHT_GEOLOCATION: float = 0.15
    WEIGHT_ANOMALY: float = 0.30
    WEIGHT_GRAPH: float = 0.20

    # -----------------------------------------------------------------------
    # Decision Thresholds  (0–100 scale)
    # -----------------------------------------------------------------------
    THRESH_ALLOW: float = 30.0
    THRESH_STEP_UP: float = 55.0
    THRESH_REVIEW: float = 80.0
    THRESH_DELAY: float = 80.0

    # -----------------------------------------------------------------------
    # Geolocation
    # -----------------------------------------------------------------------
    MAX_TRAVEL_SPEED_KMH: float = 800.0
    GEOLOC_NEW_LOCATION_RISK: float = 15.0
    GEOLOC_IMPOSSIBLE_TRAVEL_RISK: float = 60.0
    GEOLOC_CITY_CHANGE_RISK: float = 10.0
    GEOLOC_COUNTRY_CHANGE_RISK: float = 35.0

    # -----------------------------------------------------------------------
    # Background retraining
    # -----------------------------------------------------------------------
    RETRAIN_INTERVAL_HOURS: int = 12
    RETRAIN_MIN_LABELS: int = 5


settings = Settings()
