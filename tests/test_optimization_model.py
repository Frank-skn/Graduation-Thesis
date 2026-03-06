"""
Test SS-MB-SMI optimization model — PuLP per-item solver.
"""
import pytest
from optimization.models.ss_mb_smi import solve_ss_mb_smi, extract_solution_dicts, ModelSolution
from backend.schemas.optimization import OptimizationInput


def _make_data(**extra):
    """Minimal OptimizationInput for a single product / 2 warehouses / 2 periods."""
    base = dict(
        I=["PROD1"],
        J=["WH1"],
        T=[1, 2],
        BI={("PROD1", "WH1"): 100},
        CP={("PROD1", "WH1"): 50},
        U={("PROD1", "WH1", 1): 200, ("PROD1", "WH1", 2): 200},
        L={("PROD1", "WH1", 1): 50,  ("PROD1", "WH1", 2): 50},
        DI={("PROD1", "WH1", 1): -10, ("PROD1", "WH1", 2): -10},
        CAP={("PROD1", 1): 100, ("PROD1", 2): 100},
        Cb={("PROD1", "WH1", 1): 10.0, ("PROD1", "WH1", 2): 10.0},
        Co={("PROD1", "WH1", 1): 2.0,  ("PROD1", "WH1", 2): 2.0},
        Cs={("PROD1", "WH1", 1): 5.0,  ("PROD1", "WH1", 2): 5.0},
        Cp={("PROD1", "WH1", 1): 50.0, ("PROD1", "WH1", 2): 50.0},
        HV=9999,
    )
    base.update(extra)
    return OptimizationInput(**base)


def test_model_solution_type():
    """solve_ss_mb_smi returns a ModelSolution instance."""
    data = _make_data()
    sol = solve_ss_mb_smi(data, time_limit_per_item=30)
    assert isinstance(sol, ModelSolution)


def test_model_solution_fields():
    """ModelSolution contains all 7 variable dicts."""
    data = _make_data()
    sol = solve_ss_mb_smi(data, time_limit_per_item=30)
    for attr in ("Q_sol", "R_sol", "INV", "BO_sol", "O_sol", "S_sol", "PE_sol"):
        assert hasattr(sol, attr), f"Missing attribute: {attr}"


def test_extract_solution_dicts():
    """extract_solution_dicts returns one row per (i, j, t)."""
    data = _make_data()
    sol = solve_ss_mb_smi(data, time_limit_per_item=30)
    rows = extract_solution_dicts(sol, data)
    # 1 product × 1 warehouse × 2 periods = 2 rows
    assert len(rows) == 2
    for r in rows:
        for key in ("product_id", "warehouse_id", "time_period",
                    "q_case_pack", "r_residual_units", "net_inventory",
                    "backorder_qty", "overstock_qty", "shortage_qty", "penalty_flag"):
            assert key in r, f"Missing key: {key}"


def test_capacity_equality():
    """Total shipment in each period must equal CAP."""
    data = _make_data()
    sol = solve_ss_mb_smi(data, time_limit_per_item=30)
    for t in data.T:
        total = sum(
            sol.Q_sol.get(("PROD1", j, t), 0) * data.CP.get(("PROD1", j), 1)
            + sol.R_sol.get(("PROD1", j, t), 0)
            for j in data.J
        )
        cap = data.CAP.get(("PROD1", t), 0)
        assert abs(total - cap) < 1e-3, f"Cap equality violated at t={t}: {total} != {cap}"

