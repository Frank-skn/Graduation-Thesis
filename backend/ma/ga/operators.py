"""
ga/operators.py
===============
Genetic operators: BLX-α crossover and Swap-Allocation mutation.

Single Responsibility: produce offspring chromosomes from parents.

Reference:
  hybrid_ga_alns_standalone.tex §2.4  BLX-α Crossover (Algorithm 3)
  hybrid_ga_alns_standalone.tex §2.5  Mutation (Algorithm 4)
"""
from __future__ import annotations

import random
from typing import Dict, Tuple

from ..core.constraints import ConstraintHandler
from ..core.problem      import Problem, QOAChrom, Wh, Pd


class GeneticOperators:
    """
    Encapsulates crossover and mutation for the QOA chromosome space.
    """

    def __init__(
        self,
        problem    : Problem,
        constraint : ConstraintHandler,
        p_crossover: float = 0.80,
        p_mutation : float = 0.15,
        rng        : random.Random | None = None,
    ) -> None:
        self._p    = problem
        self._ch   = constraint
        self._pc   = p_crossover
        self._pm   = p_mutation
        self._rng  = rng or random.Random()

    # ------------------------------------------------------------------
    # BLX-α Crossover  (Algorithm 3)
    # ------------------------------------------------------------------

    def crossover(
        self,
        parent1: QOAChrom,
        parent2: QOAChrom,
    ) -> Tuple[QOAChrom, QOAChrom]:
        """
        BLX-α crossover with CeAP normalisation.

        If rand() > p_c, returns copies of parents unchanged.
        """
        if self._rng.random() > self._pc:
            return dict(parent1), dict(parent2)

        p   = self._p
        rng = self._rng
        alpha = rng.uniform(0.3, 0.7)

        child1: QOAChrom = {}
        child2: QOAChrom = {}

        for t in p.periods:
            raw1: Dict[Wh, float] = {}
            raw2: Dict[Wh, float] = {}
            for wh in p.warehouses:
                q1 = parent1.get((wh, t), 0)
                q2 = parent2.get((wh, t), 0)
                raw1[(wh, t)] =       alpha  * q1 + (1 - alpha) * q2
                raw2[(wh, t)] = (1 - alpha)  * q1 +      alpha  * q2

            # Normalise to sum == CAP[t]
            for raw, child in ((raw1, child1), (raw2, child2)):
                total = sum(raw[(wh, t)] for wh in p.warehouses)
                cap   = p.CAP[t]
                if total <= 0:
                    total = 1.0
                scale = cap / total
                int_vals: Dict[Wh, int] = {}
                fracs: Dict[Wh, float]  = {}
                for wh in p.warehouses:
                    v        = raw[(wh, t)] * scale
                    int_vals[wh] = int(v)
                    fracs[wh]    = v - int_vals[wh]

                diff = int(round(cap)) - sum(int_vals.values())
                ordered = sorted(p.warehouses, key=lambda w: -fracs[w])
                for idx in range(max(0, diff)):
                    int_vals[ordered[idx % len(p.warehouses)]] += 1
                for idx in range(max(0, -diff)):
                    int_vals[ordered[-(idx + 1) % len(p.warehouses)]] -= 1

                for wh in p.warehouses:
                    child[(wh, t)] = max(0, int_vals[wh])

        return child1, child2

    # ------------------------------------------------------------------
    # Swap-Allocation Mutation  (Algorithm 4)
    # ------------------------------------------------------------------

    def mutate(self, chrom: QOAChrom) -> QOAChrom:
        """
        Swap-allocation mutation: for each period, with prob p_m,
        transfer δ units between two random warehouses.
        """
        p    = self._p
        rng  = self._rng
        out  = dict(chrom)

        for t in p.periods:
            if rng.random() > self._pm:
                continue
            if len(p.warehouses) < 2:
                continue

            wh1, wh2 = rng.sample(p.warehouses, 2)
            q1        = out.get((wh1, t), 0)
            max_delta = max(1, min(q1, int(0.2 * p.CAP[t])))
            if max_delta <= 0:
                continue
            delta = rng.randint(1, max_delta)

            out[(wh1, t)] = q1 - delta
            out[(wh2, t)] = out.get((wh2, t), 0) + delta

        return out
