"""
core/constraints.py
===================
Constraint validation and chromosome repair utilities.

Single Responsibility: ensure feasibility of QOA matrices and PLT flows.

Hard constraints enforced here:
  (HC1) sum_i Q_OA[i,t] == CAP[t]    for all t
  (HC2) Q_OA[i,t] >= 0
  (HC3) sum_{j!=i} Q_PLT[i,j,t] <= I[i,t] - L[i,t]  (handled in decoder)

Reference: hybrid_ga_alns_standalone.tex §4.4
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple

from .problem import Problem, QOAChrom, Wh, Pd


class ConstraintHandler:
    """
    Provides chromosome feasibility repair and validation.
    """

    def __init__(self, problem: Problem) -> None:
        self._p = problem

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_feasible(self, chrom: QOAChrom) -> bool:
        """Check HC1 + HC2 for a given chromosome."""
        p = self._p
        for t in p.periods:
            if any(chrom.get((wh, t), 0) < 0 for wh in p.warehouses):
                return False
            total = sum(chrom.get((wh, t), 0) for wh in p.warehouses)
            if abs(total - p.CAP[t]) > 0.5:
                return False
        return True

    def repair(self, chrom: QOAChrom) -> QOAChrom:
        """
        Project chromosome onto feasible set:
          1. Clip all values to >= 0
          2. For each period, renormalise so sum == CAP[t]

        Returns a new dict (does not mutate input).
        """
        p     = self._p
        fixed = dict(chrom)

        for t in p.periods:
            cap   = p.CAP[t]
            n_wh  = len(p.warehouses)

            # Clip negatives
            for wh in p.warehouses:
                fixed[(wh, t)] = max(0, fixed.get((wh, t), 0))

            total = sum(fixed[(wh, t)] for wh in p.warehouses)

            if total == 0:
                # distribute evenly
                base  = int(cap // n_wh)
                fixed = {**fixed, **{(wh, t): base for wh in p.warehouses}}
                total = base * n_wh

            # Round-proportional scaling
            raw_vals = {wh: fixed[(wh, t)] / total * cap for wh in p.warehouses}
            rounded  = {wh: int(v) for wh, v in raw_vals.items()}
            diff     = int(round(cap)) - sum(rounded.values())

            # Distribute leftover units to warehouses with largest fractional parts
            fracs = sorted(
                p.warehouses,
                key=lambda wh: -(raw_vals[wh] - rounded[wh]),
            )
            for idx in range(diff):
                rounded[fracs[idx % n_wh]] += 1

            for wh in p.warehouses:
                fixed[(wh, t)] = rounded[wh]

        return fixed

    def enforce_cap(self, chrom: QOAChrom, rng: random.Random) -> QOAChrom:
        """
        Lightweight fix when a single mutation might have violated CAP.
        Adjusts by ±1 on the warehouse with the largest/smallest allocation.
        """
        return self.repair(chrom)
