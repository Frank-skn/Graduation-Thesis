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

Improvement (v2):
  repair() now allocates OA in full case-pack blocks first, minimising the
  number of warehouses that receive a fractional (non-multiple-of-CP)
  quantity.  Under the old round-proportional scheme every warehouse could
  receive a non-multiple, incurring Penalty_OA for ALL warehouses.
  The new scheme guarantees that at most ONE warehouse per period carries a
  residual, reducing the expected penalty by up to (n_wh - 1) × Cp per period.
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
        Project chromosome onto feasible set while minimising OA case-pack
        penalties:

          1. Clip all values to >= 0.
          2. For each period:
               a. Determine how many full case-pack blocks are available
                  across all warehouses: n_blocks = floor(CAP[t] / CP).
               b. Distribute those blocks proportionally (by the chromosome's
                  raw ratios), rounding each warehouse's block-count down.
               c. Give leftover blocks to the warehouses with the largest
                  fractional deficit (standard largest-remainder method,
                  but operating on block-counts so the result is always
                  a multiple of CP).
               d. The residual units (CAP[t] mod CP) are assigned entirely
                  to the warehouse with the highest chromosome value —
                  concentrating the single inevitable penalty in the most
                  "deserving" warehouse instead of spreading fractional
                  quantities across all warehouses.

        Returns a new dict (does not mutate input).
        """
        p     = self._p
        fixed = dict(chrom)

        for t in p.periods:
            cap  = int(round(p.CAP[t]))
            n_wh = len(p.warehouses)

            # --- Step 1: clip negatives ---
            for wh in p.warehouses:
                fixed[(wh, t)] = max(0, fixed.get((wh, t), 0))

            total = sum(fixed[(wh, t)] for wh in p.warehouses)

            # If everything is zero, distribute evenly so weights are valid
            if total == 0:
                for wh in p.warehouses:
                    fixed[(wh, t)] = 1
                total = n_wh

            # --- Step 2: case-pack block allocation ---
            cps = {wh: max(p.case_pack(wh, t), 1) for wh in p.warehouses}
            
            floored = {}
            for wh in p.warehouses:
                target = (fixed[(wh, t)] / total) * cap
                floored[wh] = int(target // cps[wh])

            remain = cap - sum(floored[wh] * cps[wh] for wh in p.warehouses)
            
            fracs = sorted(
                p.warehouses,
                key=lambda wh: -(((fixed[(wh, t)] / total) * cap - floored[wh] * cps[wh]) / cps[wh])
            )

            for wh in fracs:
                if remain >= cps[wh]:
                    floored[wh] += 1
                    remain -= cps[wh]

            for wh in p.warehouses:
                fixed[(wh, t)] = floored[wh] * cps[wh]

            # --- Step 3: assign residual to the warehouse with highest weight ---
            if remain > 0:
                residual_wh = max(
                    p.warehouses,
                    key=lambda wh: chrom.get((wh, t), 0)
                )
                fixed[(residual_wh, t)] += remain

        return fixed

    def enforce_cap(self, chrom: QOAChrom, rng: random.Random) -> QOAChrom:
        """
        Lightweight fix when a single mutation might have violated CAP.
        Delegates to the full repair which now also minimises OA penalties.
        """
        return self.repair(chrom)
