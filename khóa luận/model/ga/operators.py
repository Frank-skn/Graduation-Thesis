"""
ga/operators.py
===============
Genetic operators for V6 chromosome:
    Q_OA[warehouse, period] + Q_PLT[source, destination, period]

OA genes are repaired to satisfy capacity equality.  PLT genes are direct
requested transfer quantities; feasibility is enforced by the decoder because
it depends on dynamic inventory.
"""
from __future__ import annotations

import random
from typing import Dict, Tuple

from ..core.constraints import ConstraintHandler
from ..core.problem import Problem, QOAChrom, Wh, qplt_key


class GeneticOperators:
    def __init__(
        self,
        problem: Problem,
        constraint: ConstraintHandler,
        p_crossover: float = 0.80,
        p_mutation: float = 0.15,
        rng: random.Random | None = None,
    ) -> None:
        self._p = problem
        self._ch = constraint
        self._pc = p_crossover
        self._pm = p_mutation
        self._rng = rng or random.Random()

    def crossover(self, parent1: QOAChrom, parent2: QOAChrom) -> Tuple[QOAChrom, QOAChrom]:
        if self._rng.random() > self._pc:
            return dict(parent1), dict(parent2)

        p = self._p
        rng = self._rng
        alpha = rng.uniform(0.25, 0.75)
        child1: QOAChrom = {}
        child2: QOAChrom = {}

        # OA BLX/convex crossover with per-period capacity normalisation.
        for t in p.periods:
            raw1: Dict[Wh, float] = {}
            raw2: Dict[Wh, float] = {}
            for wh in p.warehouses:
                q1 = float(parent1.get((wh, t), 0.0))
                q2 = float(parent2.get((wh, t), 0.0))
                raw1[wh] = alpha * q1 + (1 - alpha) * q2
                raw2[wh] = (1 - alpha) * q1 + alpha * q2

            for raw, child in ((raw1, child1), (raw2, child2)):
                total = sum(max(v, 0.0) for v in raw.values()) or 1.0
                cap = int(round(p.CAP[t]))
                scaled = {wh: max(raw[wh], 0.0) / total * cap for wh in p.warehouses}
                ints = {wh: int(v) for wh, v in scaled.items()}
                diff = cap - sum(ints.values())
                order = sorted(p.warehouses, key=lambda w: -(scaled[w] - ints[w]))
                for k in range(max(0, diff)):
                    ints[order[k % len(order)]] += 1
                for k in range(max(0, -diff)):
                    donor = order[-(k % len(order)) - 1]
                    ints[donor] = max(0, ints[donor] - 1)
                for wh in p.warehouses:
                    child[(wh, t)] = ints[wh]

        # Direct Q_PLT genes: blend requested quantities independently.
        self._crossover_qplt(parent1, parent2, child1, child2, alpha)
        return child1, child2

    def _crossover_qplt(
        self,
        parent1: QOAChrom,
        parent2: QOAChrom,
        child1: QOAChrom,
        child2: QOAChrom,
        alpha: float,
    ) -> None:
        p = self._p
        rng = self._rng
        for t in p.periods:
            for src in p.warehouses:
                for dst in p.warehouses:
                    if src == dst or not p.plt_valid(src, dst, t):
                        continue
                    key = qplt_key(src, dst, t)
                    v1 = float(parent1.get(key, 0.0))
                    v2 = float(parent2.get(key, 0.0))
                    # Blend with a small exploratory perturbation.
                    c1 = alpha * v1 + (1 - alpha) * v2
                    c2 = (1 - alpha) * v1 + alpha * v2
                    if rng.random() < 0.05:
                        cap_proxy = max(1.0, p.CAP.get(t, 1.0))
                        c1 += rng.uniform(-0.05, 0.05) * cap_proxy
                        c2 += rng.uniform(-0.05, 0.05) * cap_proxy
                    child1[key] = max(0.0, c1)
                    child2[key] = max(0.0, c2)

    def mutate(self, chrom: QOAChrom) -> QOAChrom:
        p = self._p
        rng = self._rng
        out = dict(chrom)

        # OA swap-allocation mutation.
        for t in p.periods:
            if rng.random() > self._pm or len(p.warehouses) < 2:
                continue
            wh1, wh2 = rng.sample(p.warehouses, 2)
            q1 = int(out.get((wh1, t), 0))
            max_delta = max(1, min(q1, int(0.20 * p.CAP[t])))
            if max_delta <= 0:
                continue
            delta = rng.randint(1, max_delta)
            out[(wh1, t)] = q1 - delta
            out[(wh2, t)] = out.get((wh2, t), 0) + delta

        # Direct Q_PLT mutation: reset, scale, or nudge route quantities.
        self._mutate_qplt(out)
        return out

    def _mutate_qplt(self, out: QOAChrom) -> None:
        p = self._p
        rng = self._rng
        route_pm = max(0.02, min(0.35, self._pm * 0.75))
        for t in p.periods:
            cap_proxy = max(1.0, p.CAP.get(t, 1.0))
            for src in p.warehouses:
                for dst in p.warehouses:
                    if src == dst or not p.plt_valid(src, dst, t):
                        continue
                    if rng.random() > route_pm:
                        continue
                    key = qplt_key(src, dst, t)
                    cur = float(out.get(key, 0.0))
                    r = rng.random()
                    if r < 0.20:
                        # Reset to zero: important to avoid harmful PLT arcs.
                        new_val = 0.0
                    elif r < 0.45:
                        # Reset to a new requested quantity.
                        new_val = rng.uniform(0.0, 0.40 * cap_proxy)
                    else:
                        # Local multiplicative/additive move.
                        new_val = cur * rng.uniform(0.55, 1.45) + rng.uniform(-0.05, 0.10) * cap_proxy
                    out[key] = max(0.0, new_val)
