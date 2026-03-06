"""
Test optimization model building and solving
"""
import pytest
from optimization.models.ss_mb_smi import build_ss_mb_smi_model, extract_solution
from backend.schemas.optimization import OptimizationInput


def test_model_creation():
    """Test that model can be created with minimal data"""
    data = OptimizationInput(
        I=["PROD1"],
        J=["WH1"],
        T=[1, 2],
        BI={("PROD1", "WH1"): 100},
        CP={("PROD1", "WH1"): 50},
        U={("PROD1", "WH1", 1): 200, ("PROD1", "WH1", 2): 200},
        L={("PROD1", "WH1", 1): 50, ("PROD1", "WH1", 2): 50},
        DI={("PROD1", "WH1", 1): -10, ("PROD1", "WH1", 2): -10},
        CAP={("PROD1", 1): 100, ("PROD1", 2): 100},
        Cb={("PROD1", "WH1", 1): 10.0, ("PROD1", "WH1", 2): 10.0},
        Co={("PROD1", "WH1", 1): 2.0, ("PROD1", "WH1", 2): 2.0},
        Cs={("PROD1", "WH1", 1): 5.0, ("PROD1", "WH1", 2): 5.0},
        Cp={("PROD1", "WH1", 1): 50.0, ("PROD1", "WH1", 2): 50.0},
        HV=9999
    )
    
    model = build_ss_mb_smi_model(data)
    
    assert model is not None
    assert hasattr(model, 'q')
    assert hasattr(model, 'r')
    assert hasattr(model, 'I_inv')
    assert hasattr(model, 'OBJ')


def test_model_constraints():
    """Test that all constraints are created"""
    data = OptimizationInput(
        I=["PROD1"],
        J=["WH1"],
        T=[1],
        BI={("PROD1", "WH1"): 100},
        CP={("PROD1", "WH1"): 50},
        U={("PROD1", "WH1", 1): 200},
        L={("PROD1", "WH1", 1): 50},
        DI={("PROD1", "WH1", 1): -10},
        CAP={("PROD1", 1): 100},
        Cb={("PROD1", "WH1", 1): 10.0},
        Co={("PROD1", "WH1", 1): 2.0},
        Cs={("PROD1", "WH1", 1): 5.0},
        Cp={("PROD1", "WH1", 1): 50.0},
        HV=9999
    )
    
    model = build_ss_mb_smi_model(data)
    
    assert hasattr(model, 'InventoryInit')
    assert hasattr(model, 'CapacityConstraint')
    assert hasattr(model, 'BackorderConstraint')
    assert hasattr(model, 'OverstockConstraint')
    assert hasattr(model, 'ShortageConstraint')
    assert hasattr(model, 'ResidualUpper')
    assert hasattr(model, 'ResidualLower')
