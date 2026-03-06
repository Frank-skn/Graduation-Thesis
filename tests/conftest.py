"""
Test configuration
"""
import pytest


@pytest.fixture
def sample_optimization_data():
    """Sample data for testing"""
    from backend.schemas.optimization import OptimizationInput
    
    return OptimizationInput(
        I=["PROD1", "PROD2"],
        J=["WH1", "WH2"],
        T=[1, 2, 3],
        BI={
            ("PROD1", "WH1"): 100,
            ("PROD1", "WH2"): 150,
            ("PROD2", "WH1"): 80,
            ("PROD2", "WH2"): 120
        },
        CP={
            ("PROD1", "WH1"): 50,
            ("PROD1", "WH2"): 50,
            ("PROD2", "WH1"): 40,
            ("PROD2", "WH2"): 40
        },
        U={(i, j, t): 200 for i in ["PROD1", "PROD2"] for j in ["WH1", "WH2"] for t in [1, 2, 3]},
        L={(i, j, t): 50 for i in ["PROD1", "PROD2"] for j in ["WH1", "WH2"] for t in [1, 2, 3]},
        DI={(i, j, t): -10 for i in ["PROD1", "PROD2"] for j in ["WH1", "WH2"] for t in [1, 2, 3]},
        CAP={(i, t): 200 for i in ["PROD1", "PROD2"] for t in [1, 2, 3]},
        Cb={(i, j, t): 10.0 for i in ["PROD1", "PROD2"] for j in ["WH1", "WH2"] for t in [1, 2, 3]},
        Co={(i, j, t): 2.0 for i in ["PROD1", "PROD2"] for j in ["WH1", "WH2"] for t in [1, 2, 3]},
        Cs={(i, j, t): 5.0 for i in ["PROD1", "PROD2"] for j in ["WH1", "WH2"] for t in [1, 2, 3]},
        Cp={(i, j, t): 50.0 for i in ["PROD1", "PROD2"] for j in ["WH1", "WH2"] for t in [1, 2, 3]},
        HV=9999
    )
