"""
core/objective.py
=================
Pure fitness / objective evaluation.

Single Responsibility: given a decoded solution (QOA matrix, inventory
trajectories, PLT flows), compute the scalar cost value Z.

Reference: math_model.tex — Hàm mục tiêu (Eq. 1–3),
           hybrid_ga_alns_standalone.tex — Hàm tính Fitness (§1.6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from .problem import Problem, Wh, Pd


# ---------------------------------------------------------------------------
# Decoded solution container
# ---------------------------------------------------------------------------

@dataclass
class DecodedSolution:
    """
    Full decoded state for a single-product sub-problem.

    Fields
    ------
    Q_OA   : Dict[(wh, t), int]          total OA allocation (chromosome value)
    q_OA   : Dict[(wh, t), int]          full-case count  = floor(Q_OA / CP)
    r_OA   : Dict[(wh, t), int]          residual units   = Q_OA - CP * q_OA
    Q_PLT  : Dict[(i, j, t), int]        lateral transshipment from i→j at t
    I      : Dict[(wh, t), float]        inventory level at end of period t
    fitness: float                        objective value Z
    """
    Q_OA   : Dict[Tuple[Wh, Pd], int]         = field(default_factory=dict)
    q_OA   : Dict[Tuple[Wh, Pd], int]         = field(default_factory=dict)
    r_OA   : Dict[Tuple[Wh, Pd], int]         = field(default_factory=dict)
    Q_PLT  : Dict[Tuple[Wh, Wh, Pd], float]   = field(default_factory=dict)
    I      : Dict[Tuple[Wh, Pd], float]       = field(default_factory=dict)
    fitness: float                             = float("inf")


# ---------------------------------------------------------------------------
# Objective calculator
# ---------------------------------------------------------------------------

class ObjectiveCalculator:
    """
    Stateless evaluator: computes Z from a DecodedSolution.

    Single Responsibility — knows only the cost formulas.
    """

    def __init__(self, problem: Problem) -> None:
        self._p = problem

    # ------------------------------------------------------------------
    def compute(self, sol: DecodedSolution) -> float:
        """
        Compute and return total cost Z.

        Z = inventory_cost + OA_penalty + PLT_cost

        Also stores result in sol.fitness.
        """
        p     = self._p
        total = 0.0

        for wh in p.warehouses:
            for t in p.periods:
                inv   = sol.I.get((wh, t), 0.0)
                u_val = p.U.get((wh, t), 1e9)
                l_val = p.L.get((wh, t), 0.0)

                # Inventory costs
                total += p.Co.get((wh, t), 0.0) * max(inv - u_val, 0.0)
                total += p.Cs.get((wh, t), 0.0) * max(l_val - inv, 0.0)
                total += p.Cb.get((wh, t), 0.0) * max(-inv, 0.0)

                # OA partial-case penalty
                r_val = sol.r_OA.get((wh, t), 0)
                if r_val > 0:
                    total += p.Cp.get((wh, t), 0.0)

        # PLT costs
        for (i, j, t), q_plt in sol.Q_PLT.items():
            if q_plt <= 0:
                continue
            # Transport cost
            d_ij = p.dist.get((i, j), p.dist.get((j, i), 0.0))
            total += d_ij * p.TC

            # PLT partial-case penalty. Use receiver case-pack at ship period.
            cp_val = p.case_pack(j, t)
            r_plt = q_plt % cp_val
            if r_plt > 0:
                total += p.Cp_plt.get((i, j, t), 0.0)

        sol.fitness = total
        return total

    # ------------------------------------------------------------------
    def period_costs(self, sol: DecodedSolution) -> Dict[Tuple[Wh, Pd], float]:
        """Return per-(wh, t) inventory cost for ALNS destruction targeting."""
        p   = self._p
        out: Dict[Tuple[Wh, Pd], float] = {}
        for wh in p.warehouses:
            for t in p.periods:
                inv   = sol.I.get((wh, t), 0.0)
                u_val = p.U.get((wh, t), 1e9)
                l_val = p.L.get((wh, t), 0.0)
                cost  = (
                    p.Co.get((wh, t), 0.0) * max(inv - u_val, 0.0)
                    + p.Cs.get((wh, t), 0.0) * max(l_val - inv, 0.0)
                    + p.Cb.get((wh, t), 0.0) * max(-inv, 0.0)
                )
                out[(wh, t)] = cost
        return out
