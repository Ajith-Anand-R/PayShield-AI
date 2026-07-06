import pytest
from app.engines.behavioral import BehavioralEngine
from app.engines.device import DeviceTrustEngine
from app.engines.geolocation import GeolocationRiskEngine
from app.engines.anomaly import TransactionAnomalyEngine
from app.engines.graph import FraudGraphEngine
from app.services.fusion import RiskFusionEngine

@pytest.fixture(autouse=True)
def mock_engine_models(request):
    # If the test is testing ML paths, do not mock the real loading
    if request.node.name in ["test_engines_ml_paths", "test_heavy_training"]:
        yield
        return

    # Otherwise, stub _load_model for all engines to ensure they run in heuristic mode
    engines = [
        BehavioralEngine,
        DeviceTrustEngine,
        GeolocationRiskEngine,
        TransactionAnomalyEngine,
        FraudGraphEngine,
        RiskFusionEngine
    ]
    
    orig_loads = {}
    for eng in engines:
        orig_loads[eng] = eng._load_model
        eng._load_model = lambda: None
        eng._model = None
        
    try:
        yield
    finally:
        for eng in engines:
            eng._load_model = orig_loads[eng]
            eng._model = None
