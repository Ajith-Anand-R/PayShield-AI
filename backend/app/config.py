class Settings:
    PROJECT_NAME: str = "PayShield Risk Engine"
    DATABASE_URL: str = "postgresql://user:pass@localhost:5432/payshield"
    
    # Risk Fusion Weights
    # Total Risk = 0.20 * Behavioral + 0.25 * Device + 0.35 * Anomaly + 0.20 * Graph
    WEIGHT_BEHAVIORAL: float = 0.20
    WEIGHT_DEVICE: float = 0.25
    WEIGHT_ANOMALY: float = 0.35
    WEIGHT_GRAPH: float = 0.20
    
    # Decision Thresholds
    THRESH_ALLOW: float = 30.0
    THRESH_STEP_UP: float = 55.0
    THRESH_DELAY: float = 75.0

settings = Settings()
