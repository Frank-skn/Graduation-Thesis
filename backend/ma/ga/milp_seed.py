"""
ga/milp_seed.py
===============
Generate an initial chromosome by solving a relaxed MILP sub-problem
using PuLP (CBC solver) — mirrors ss_mb_smi.py logic from ref/.

Single Responsibility: produce a warm-start QOA chromosome for GA.

Reference: hybrid_ga_alns_standalone.tex §2.3 (Algorithm 1, step 1)
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

try:
    import pulp  # type: ignore
    _PULP_AVAILABLE = True
except ImportError:
    _PULP_AVAILABLE = False

from ..core.problem import Problem, QOAChrom, Wh, Pd


def generate_milp_seed(
    problem   : Problem,
    time_limit: int = 15,
) -> Optional[QOAChrom]:
    """
    Solve a simplified MILP to seed GA population.

    The MILP minimises inventory-deviation costs subject to:
      - Capacity equality per period
      - Non-negativity and integrality of q (full cases)
      - Inventory balance (no PLT for simplicity)

    Returns a QOAChrom dict or None if solver fails / PuLP unavailable.
    """
    if not _PULP_AVAILABLE:
        log.warning("PuLP not installed — skipping MILP seed generation.")
        return None

    p = problem
    wh_list = list(p.warehouses)
    T_list  = list(p.periods)
    n_wh    = len(wh_list)

    prob = pulp.LpProblem("MILPSeed", pulp.LpMinimize)

    # Variables: q[wh, t] integer >= 0, r[wh, t] residual 0..CP-1
    q: Dict = {}
    r: Dict = {}
    I: Dict = {}
    s: Dict = {}   # shortage
    o: Dict = {}   # overstock

    for wh in wh_list:
        for t in T_list:
            q[(wh, t)] = pulp.LpVariable(f"q_{wh}_{t}", lowBound=0, cat="Integer")
            r[(wh, t)] = pulp.LpVariable(f"r_{wh}_{t}", lowBound=0, upBound=p.CP - 1, cat="Integer")
            I[(wh, t)] = pulp.LpVariable(f"I_{wh}_{t}", lowBound=None, cat="Continuous")
            s[(wh, t)] = pulp.LpVariable(f"s_{wh}_{t}", lowBound=0, cat="Continuous")
            o[(wh, t)] = pulp.LpVariable(f"o_{wh}_{t}", lowBound=0, cat="Continuous")

    # Objective
    prob += pulp.lpSum(
        p.Co.get((wh, t), 0) * o[(wh, t)]
        + p.Cs.get((wh, t), 0) * s[(wh, t)]
        + p.Cb.get((wh, t), 0) * pulp.lpSum(0)   # simplified: no backorder var
        for wh in wh_list for t in T_list
    )

    # Capacity constraint
    for t in T_list:
        cap = p.CAP[t]
        prob += (
            pulp.lpSum(q[(wh, t)] * p.CP + r[(wh, t)] for wh in wh_list) == cap,
            f"Cap_{t}",
        )

    # Inventory balance (no PLT in seed)
    for wh in wh_list:
        inv_prev = p.BI[wh]
        for t in T_list:
            # OA arrives LT_OA periods later; map backward
            oa_arrival_t = t - p.LT_OA
            if oa_arrival_t in T_list:
                oa_in = q[(wh, oa_arrival_t)] * p.CP + r[(wh, oa_arrival_t)]
            else:
                oa_in = 0
            di = p.delta_I.get((wh, t), 0.0)
            if t == T_list[0]:
                prob += I[(wh, t)] == p.BI[wh] + oa_in + di, f"InvInit_{wh}_{t}"
            else:
                t_prev = T_list[T_list.index(t) - 1]
                prob += I[(wh, t)] == I[(wh, t_prev)] + oa_in + di, f"Inv_{wh}_{t}"

            # Shortage / overstock linearisation
            u_val = p.U.get((wh, t), 1e6)
            l_val = p.L.get((wh, t), 0.0)
            prob += o[(wh, t)] >= I[(wh, t)] - u_val, f"Ov_{wh}_{t}"
            prob += s[(wh, t)] >= l_val - I[(wh, t)], f"Sh_{wh}_{t}"

    # Solve
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit)
    solver.solve(prob)

    status = pulp.LpStatus[prob.status]
    if status not in ("Optimal", "Not Solved"):
        log.warning("MILP seed: solver status %s — returning None", status)
        return None

    chrom: QOAChrom = {}
    for wh in wh_list:
        for t in T_list:
            q_val        = pulp.value(q[(wh, t)])
            r_val        = pulp.value(r[(wh, t)])
            q_val        = int(round(q_val)) if q_val is not None else 0
            r_val        = int(round(r_val)) if r_val is not None else 0
            chrom[(wh, t)] = q_val * p.CP + r_val

    log.info("MILP seed generated; obj=%.2f", pulp.value(prob.objective) or 0)
    return chrom
