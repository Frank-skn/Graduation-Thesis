"""
ga/milp_seed.py
================
MILP warm-start generator for GA.

This version includes backorder and OA residual-penalty terms in the seed
objective. The previous implementation ignored backorder cost, which could
produce warm starts that were attractive to the seed MILP but poor for the
actual GA objective.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

try:
    import pulp  # type: ignore
    _PULP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PULP_AVAILABLE = False

from ..core.problem import Problem, QOAChrom


def generate_milp_seed(problem: Problem, time_limit: int = 15) -> Optional[QOAChrom]:
    """Solve a simplified no-PLT MILP and return a QOA chromosome."""
    if not _PULP_AVAILABLE:
        log.warning("PuLP not installed — skipping MILP seed generation.")
        return None

    p = problem
    wh_list = list(p.warehouses)
    T_list = list(p.periods)

    prob = pulp.LpProblem("MILPSeed_with_backorder", pulp.LpMinimize)

    q: Dict = {}
    r: Dict = {}
    y: Dict = {}
    I: Dict = {}
    s: Dict = {}
    o: Dict = {}
    b: Dict = {}

    for wh in wh_list:
        for t in T_list:
            cp = p.case_pack(wh, t)
            q[(wh, t)] = pulp.LpVariable(f"q_{wh}_{t}", lowBound=0, cat="Integer")
            r[(wh, t)] = pulp.LpVariable(f"r_{wh}_{t}", lowBound=0, upBound=cp - 1, cat="Integer")
            y[(wh, t)] = pulp.LpVariable(f"y_{wh}_{t}", lowBound=0, upBound=1, cat="Binary")
            I[(wh, t)] = pulp.LpVariable(f"I_{wh}_{t}", lowBound=None, cat="Continuous")
            s[(wh, t)] = pulp.LpVariable(f"s_{wh}_{t}", lowBound=0, cat="Continuous")
            o[(wh, t)] = pulp.LpVariable(f"o_{wh}_{t}", lowBound=0, cat="Continuous")
            b[(wh, t)] = pulp.LpVariable(f"b_{wh}_{t}", lowBound=0, cat="Continuous")

            if cp == 1:
                prob += r[(wh, t)] == 0, f"ResZero_{wh}_{t}"
                prob += y[(wh, t)] == 0, f"YZero_{wh}_{t}"
            else:
                prob += r[(wh, t)] <= (cp - 1) * y[(wh, t)], f"ResLinkUB_{wh}_{t}"
                prob += r[(wh, t)] >= y[(wh, t)], f"ResLinkLB_{wh}_{t}"

    prob += pulp.lpSum(
        p.Co.get((wh, t), 0.0) * o[(wh, t)]
        + p.Cs.get((wh, t), 0.0) * s[(wh, t)]
        + p.Cb.get((wh, t), 0.0) * b[(wh, t)]
        + p.Cp.get((wh, t), 0.0) * y[(wh, t)]
        for wh in wh_list
        for t in T_list
    )

    for t in T_list:
        cap = int(round(p.CAP[t]))
        prob += (
            pulp.lpSum(q[(wh, t)] * p.case_pack(wh, t) + r[(wh, t)] for wh in wh_list) == cap,
            f"Cap_{t}",
        )

    first_t = T_list[0]
    for wh in wh_list:
        for idx, t in enumerate(T_list):
            order_t = t - p.LT_OA[wh] + 1
            if order_t in T_list:
                oa_in = q[(wh, order_t)] * p.case_pack(wh, order_t) + r[(wh, order_t)]
            else:
                oa_in = 0

            prev_inv = p.BI.get(wh, 0.0) if t == first_t else I[(wh, T_list[idx - 1])]
            prob += I[(wh, t)] == prev_inv + oa_in + p.delta_I.get((wh, t), 0.0), f"Inv_{wh}_{t}"

            u_val = p.U.get((wh, t), 1e6)
            l_val = p.L.get((wh, t), 0.0)
            prob += o[(wh, t)] >= I[(wh, t)] - u_val, f"Ov_{wh}_{t}"
            prob += s[(wh, t)] >= l_val - I[(wh, t)], f"Sh_{wh}_{t}"
            prob += b[(wh, t)] >= -I[(wh, t)], f"Bo_{wh}_{t}"

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit)
    solver.solve(prob)

    status = pulp.LpStatus.get(prob.status, str(prob.status))
    if status not in {"Optimal", "Not Solved", "Undefined"}:
        log.warning("MILP seed: solver status %s — returning None", status)
        return None

    chrom: QOAChrom = {}
    missing_values = False
    for wh in wh_list:
        for t in T_list:
            q_val = pulp.value(q[(wh, t)])
            r_val = pulp.value(r[(wh, t)])
            if q_val is None or r_val is None:
                missing_values = True
                q_val = 0
                r_val = 0
            q_int = max(0, int(round(q_val)))
            r_int = max(0, int(round(r_val)))
            chrom[(wh, t)] = q_int * p.case_pack(wh, t) + r_int

    if missing_values:
        log.warning("MILP seed has missing variable values; repaired chromosome will be used.")

    chrom = chrom if chrom else None
    if chrom is None:
        return None

    obj_val = pulp.value(prob.objective)
    log.info("MILP seed generated; status=%s; obj=%.2f", status, obj_val or 0.0)
    return chrom
