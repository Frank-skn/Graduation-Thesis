"""
SS-MB-SMI Optimization Model — PuLP per-item decomposition.

Mirrors D:/KLTN/temp.py exactly:
- Per-item sub-problems solved independently with CBC
- Capacity constraint is EQUALITY (== CAP[i,t]) per the paper
- Variables: q (int>=0), r (0..CP-1 int), I (continuous),
             bo/o/s (continuous>=0), p (binary)
- Objective: min Σ(Co·o + Cs·s + Cb·bo + Cp·p)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import pulp

from backend.schemas.optimization import OptimizationInput

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HV_DEFAULT = 9999.0
MAX_SOLVE_SECONDS_DEFAULT = 30


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ModelSolution:
    """Full solution across all items."""

    Q_sol:  Dict[Tuple, int]   = field(default_factory=dict)
    R_sol:  Dict[Tuple, int]   = field(default_factory=dict)
    INV:    Dict[Tuple, float] = field(default_factory=dict)
    BO_sol: Dict[Tuple, float] = field(default_factory=dict)
    O_sol:  Dict[Tuple, float] = field(default_factory=dict)
    S_sol:  Dict[Tuple, float] = field(default_factory=dict)
    PE_sol: Dict[Tuple, int]   = field(default_factory=dict)

    objective_value:     float = 0.0
    solve_time_seconds:  float = 0.0
    solver_status:       str   = "Optimal"
    n_infeasible:        int   = 0
    n_failed:            int   = 0



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(v) -> float:
    """Safely extract PuLP variable value."""
    val = pulp.value(v)
    return 0.0 if val is None else float(val)


# ---------------------------------------------------------------------------
# Per-item sub-problem
# ---------------------------------------------------------------------------

def _solve_item(
    item: str,
    j_list: List[str],
    T: List[int],
    BI: Dict,
    DI: Dict,
    U: Dict,
    L: Dict,
    CAP: Dict,
    CP: Dict,
    Co: Dict,
    Cs: Dict,
    Cb: Dict,
    Cp_cost: Dict,
    HV: float,
    time_limit: int,
) -> dict:
    """
    Solve the SS-MB-SMI sub-problem for a single item.

    Returns a dict with Q_sol, R_sol, INV, BO_sol, O_sol, S_sol, PE_sol,
    obj_val, status keys.
    """
    ijt_list = [(item, j, t) for j in j_list for t in T]

    sub = pulp.LpProblem(f"SS_{item}", pulp.LpMinimize)

    # --- Variables ---
    q = pulp.LpVariable.dicts("q", ijt_list, lowBound=0, cat="Integer")

    r: Dict = {}
    for i_, j_, t_ in ijt_list:
        cp_ij = max(1, int(CP.get((i_, j_), 1)))
        r[(i_, j_, t_)] = pulp.LpVariable(
            f"r_{i_}_{j_}_{t_}", lowBound=0, upBound=cp_ij - 1, cat="Integer"
        )

    Iv  = pulp.LpVariable.dicts("I",  ijt_list, lowBound=None, cat="Continuous")
    bo  = pulp.LpVariable.dicts("bo", ijt_list, lowBound=0,    cat="Continuous")
    o   = pulp.LpVariable.dicts("o",  ijt_list, lowBound=0,    cat="Continuous")
    s   = pulp.LpVariable.dicts("s",  ijt_list, lowBound=0,    cat="Continuous")
    p   = pulp.LpVariable.dicts("p",  ijt_list, cat="Binary")

    # --- Objective ---
    obj_expr = pulp.lpSum(
        Co.get(k, 0) * o[k]
        + Cs.get(k, 0) * s[k]
        + Cb.get(k, 0) * bo[k]
        + Cp_cost.get(k, 0) * p[k]
        for k in ijt_list
    )
    # Guard: ensure it is an LpAffineExpression when all costs are zero
    if not isinstance(obj_expr, pulp.LpAffineExpression):
        obj_expr = obj_expr + 0.0 * q[ijt_list[0]]
    sub += obj_expr, "Total_Cost"

    # --- Constraints ---
    t0 = T[0]
    for j_ in j_list:
        cp_ij = max(1, int(CP.get((item, j_), 1)))

        # C2 – inventory balance t = t0
        sub += (
            Iv[(item, j_, t0)]
            == BI.get((item, j_), 0)
            + DI.get((item, j_, t0), 0)
            + q[(item, j_, t0)] * cp_ij
            + r[(item, j_, t0)],
            f"InvInit_{j_}",
        )

        # C3 – inventory balance t > t0
        for k in range(1, len(T)):
            tc, tp = T[k], T[k - 1]
            sub += (
                Iv[(item, j_, tc)]
                == Iv[(item, j_, tp)]
                + DI.get((item, j_, tc), 0)
                + q[(item, j_, tc)] * cp_ij
                + r[(item, j_, tc)],
                f"InvFlow_{j_}_{tc}",
            )

    # C4 – capacity equality per paper Eq.4
    for t_ in T:
        sub += (
            pulp.lpSum(
                q[(item, j_, t_)] * max(1, int(CP.get((item, j_), 1)))
                + r[(item, j_, t_)]
                for j_ in j_list
            )
            == CAP.get((item, t_), 0),
            f"Cap_{t_}",
        )

    # C5-C9 – deviation & penalty linearisations
    for j_ in j_list:
        for t_ in T:
            k = (item, j_, t_)
            hv = float(HV)
            sub += bo[k] >= -Iv[k],                             f"BO_{j_}_{t_}"
            sub += o[k]  >= Iv[k] - U.get(k, hv),              f"O_{j_}_{t_}"
            sub += s[k]  >= L.get(k, 0) - Iv[k],               f"S_{j_}_{t_}"
            sub += r[k]  <= hv * p[k],                          f"RU_{j_}_{t_}"
            sub += r[k]  >= hv * (p[k] - 1) + 1,               f"RL_{j_}_{t_}"

    # --- Solve ---
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit)
    solver.solve(sub)

    status = pulp.LpStatus[sub.status]

    out: dict = {
        "status": status,
        "obj_val": _safe(sub.objective),
        "Q_sol": {}, "R_sol": {}, "INV": {},
        "BO_sol": {}, "O_sol": {}, "S_sol": {}, "PE_sol": {},
    }
    if status in ("Optimal", "Not Solved"):
        for k in ijt_list:
            out["Q_sol"][k]  = int(round(_safe(q[k])))
            out["R_sol"][k]  = int(round(_safe(r[k])))
            out["INV"][k]    = _safe(Iv[k])
            out["BO_sol"][k] = _safe(bo[k])
            out["O_sol"][k]  = _safe(o[k])
            out["S_sol"][k]  = _safe(s[k])
            out["PE_sol"][k] = int(round(_safe(p[k])))
    return out


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def solve_ss_mb_smi(
    data: "OptimizationInput",
    time_limit_per_item: int = MAX_SOLVE_SECONDS_DEFAULT,
) -> "ModelSolution":
    """
    Solve SS-MB-SMI via per-item PuLP sub-problems (mirrors temp.py).

    Each item is solved independently; results are accumulated in ModelSolution.
    """
    T = sorted(data.T)

    # Build J_by_i: which warehouses carry item i
    J_by_i: Dict[str, List[str]] = {}
    for (i, j, _) in data.DI.keys():
        J_by_i.setdefault(i, [])
        if j not in J_by_i[i]:
            J_by_i[i].append(j)

    sol = ModelSolution()
    t_start = time.time()

    for item in data.I:
        j_list = sorted(J_by_i.get(item, []))
        if not j_list:
            continue

        result = _solve_item(
            item=item,
            j_list=j_list,
            T=T,
            BI=data.BI,
            DI=data.DI,
            U=data.U,
            L=data.L,
            CAP=data.CAP,
            CP=data.CP,
            Co=data.Co,
            Cs=data.Cs,
            Cb=data.Cb,
            Cp_cost=data.Cp,
            HV=getattr(data, "HV", HV_DEFAULT),
            time_limit=time_limit_per_item,
        )

        status = result["status"]
        if status not in ("Optimal",):
            if status == "Infeasible":
                sol.n_infeasible += 1
            else:
                sol.n_failed += 1

        sol.objective_value += result["obj_val"]
        sol.Q_sol.update(result["Q_sol"])
        sol.R_sol.update(result["R_sol"])
        sol.INV.update(result["INV"])
        sol.BO_sol.update(result["BO_sol"])
        sol.O_sol.update(result["O_sol"])
        sol.S_sol.update(result["S_sol"])
        sol.PE_sol.update(result["PE_sol"])

    sol.solve_time_seconds = time.time() - t_start
    if sol.n_infeasible == 0 and sol.n_failed == 0:
        sol.solver_status = "Optimal"
    elif sol.n_infeasible > 0:
        sol.solver_status = "Infeasible"
    else:
        sol.solver_status = "Failed"

    return sol


# ---------------------------------------------------------------------------
# Solution extraction helper
# ---------------------------------------------------------------------------

def extract_solution_dicts(
    model_sol: "ModelSolution",
    data: "OptimizationInput",
) -> List[dict]:
    """
    Flatten ModelSolution into a list of row-dicts for DB persistence.

    Each row: {product_id, warehouse_id, box_id, time_period,
               q_case_pack, r_residual_units, net_inventory,
               backorder_qty, overstock_qty, shortage_qty, penalty_flag}
    """
    rows: List[dict] = []
    for (i, j, t), q_val in model_sol.Q_sol.items():
        rows.append(
            {
                "product_id": i,
                "warehouse_id": j,
                "box_id": CP_to_box_id(data.CP.get((i, j), 1)),
                "time_period": t,
                "q_case_pack": q_val,
                "r_residual_units": model_sol.R_sol.get((i, j, t), 0),
                "net_inventory": model_sol.INV.get((i, j, t), 0.0),
                "backorder_qty": model_sol.BO_sol.get((i, j, t), 0.0),
                "overstock_qty": model_sol.O_sol.get((i, j, t), 0.0),
                "shortage_qty": model_sol.S_sol.get((i, j, t), 0.0),
                "penalty_flag": bool(model_sol.PE_sol.get((i, j, t), 0)),
            }
        )
    return rows


def CP_to_box_id(cp_value: int) -> int:
    """Map CP value to a box_id integer (simple identity mapping)."""
    return int(cp_value) if cp_value else 1
