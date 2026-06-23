"""
alns/alns_solver.py
===================
Adaptive Large Neighborhood Search (ALNS) local search for QOA chromosomes.

Optimised version:
  - Repair operators are lead-time-aware: order period t is evaluated against
    arrival period t + LT_OA - 1.
  - Worst-period destroy maps high inventory cost at period tau back to the
    OA order period that can affect tau.
  - Regret repair uses weighted shortage/backorder risk instead of plain
    shortage at the same period.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple

from ..core.constraints import ConstraintHandler
from ..core.decoder import Decoder
from ..core.objective import DecodedSolution, ObjectiveCalculator
from ..core.problem import Problem, QOAChrom, Wh, Pd, qplt_key


class ALNSSolver:
    """Adaptive LNS with simulated-annealing acceptance."""

    _SIGMA = {
        "new_best": 3,
        "better": 2,
        "accepted": 1,
        "rejected": 0,
    }

    def __init__(
        self,
        problem: Problem,
        decoder: Decoder,
        obj_calc: ObjectiveCalculator,
        constraint: ConstraintHandler,
        n_iterations: int = 60,
        q_min_ratio: float = 0.10,
        q_max_ratio: float = 0.40,
        lambda_rho: float = 0.15,
        segment_size: int = 20,
        sa_accept_prob: float = 0.05,
        sa_cooling: float = 0.995,
        rng: random.Random | None = None,
    ) -> None:
        self._p = problem
        self._dec = decoder
        self._eval = obj_calc
        self._ch = constraint
        self._n_iter = max(1, int(n_iterations))
        self._q_min = max(1, int(math.ceil(q_min_ratio * len(problem.periods))))
        self._q_max = max(self._q_min, int(math.ceil(q_max_ratio * len(problem.periods))))
        self._lam = lambda_rho
        self._seg = max(1, int(segment_size))
        self._accept_p = min(max(sa_accept_prob, 1e-9), 0.999999)
        self._cooling = sa_cooling
        self._rng = rng or random.Random()

        self._destroys = [self._d1_random, self._d2_worst_cost, self._d3_facility]
        self._repairs = [self._r1_greedy, self._r2_random, self._r3_regret]

        self.reset_weights()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset_weights(self) -> None:
        n_d = len(self._destroys)
        n_r = len(self._repairs)
        self._w_d = [1.0] * n_d
        self._w_r = [1.0] * n_r
        self._pi_d = [0.0] * n_d
        self._pi_r = [0.0] * n_r
        self._n_d = [0] * n_d
        self._n_r = [0] * n_r

    def run(self, chrom: QOAChrom, sol: DecodedSolution) -> Tuple[DecodedSolution, QOAChrom]:
        x_cur = dict(chrom)
        x_best = dict(chrom)
        f_cur = sol.fitness
        f_best = sol.fitness
        s_best = sol

        delta_init = 0.01 * abs(f_cur) if f_cur != 0 else 1.0
        theta = -delta_init / math.log(self._accept_p)

        for it in range(1, self._n_iter + 1):
            d_idx = self._weighted_choice(self._w_d, self._rng)
            r_idx = self._weighted_choice(self._w_r, self._rng)

            x_minus, t_minus = self._destroys[d_idx](x_cur, sol)
            x_prime = self._repairs[r_idx](x_minus, t_minus, sol)
            x_prime = self._ch.repair(x_prime)
            # V5: repair Q_PLT quantity genes for the affected order periods.
            # This remains solver-free; it only biases future greedy PLT routing.
            x_prime = self._repair_plt_quantities(x_prime, t_minus, sol)

            sol_prime = self._dec.decode(x_prime)
            f_prime = sol_prime.fitness

            if f_prime < f_best:
                score = self._SIGMA["new_best"]
                x_best = dict(x_prime)
                f_best = f_prime
                s_best = sol_prime
            elif f_prime < f_cur:
                score = self._SIGMA["better"]
            elif theta > 0 and self._rng.random() < math.exp(-(f_prime - f_cur) / max(theta, 1e-12)):
                score = self._SIGMA["accepted"]
            else:
                score = self._SIGMA["rejected"]

            if score >= self._SIGMA["accepted"]:
                x_cur = dict(x_prime)
                f_cur = f_prime
                sol = sol_prime

            self._pi_d[d_idx] += score
            self._pi_r[r_idx] += score
            self._n_d[d_idx] += 1
            self._n_r[r_idx] += 1

            theta *= self._cooling

            if it % self._seg == 0:
                self._update_weights()

        return s_best, x_best

    # ------------------------------------------------------------------
    # Destroy operators
    # ------------------------------------------------------------------

    def _d1_random(self, x: QOAChrom, sol: DecodedSolution) -> Tuple[QOAChrom, List[Pd]]:
        q = self._rng.randint(self._q_min, self._q_max)
        t_minus = self._rng.sample(list(self._p.periods), min(q, len(self._p.periods)))
        return self._zero_periods(x, t_minus), t_minus

    def _d2_worst_cost(self, x: QOAChrom, sol: DecodedSolution) -> Tuple[QOAChrom, List[Pd]]:
        """Destroy order periods that can affect high-cost arrival periods."""
        p = self._p
        q = self._rng.randint(self._q_min, self._q_max)

        order_cost = {t: 0.0 for t in p.periods}
        for wh in p.warehouses:
            for arrival_t in p.periods:
                inv = sol.I.get((wh, arrival_t), 0.0)
                period_cost = self._inventory_cost(wh, arrival_t, inv)
                order_t = arrival_t - p.LT_OA[wh] + 1
                if order_t in order_cost:
                    order_cost[order_t] += period_cost

        t_minus = sorted(p.periods, key=lambda t: -order_cost[t])[:q]
        return self._zero_periods(x, t_minus), t_minus

    def _d3_facility(self, x: QOAChrom, sol: DecodedSolution) -> Tuple[QOAChrom, List[Pd]]:
        """Target order periods feeding the most costly warehouse."""
        p = self._p
        q = self._rng.randint(self._q_min, self._q_max)

        wh_cost: Dict[Wh, float] = {}
        for wh in p.warehouses:
            wh_cost[wh] = sum(
                self._inventory_cost(wh, t, sol.I.get((wh, t), 0.0))
                for t in p.periods
            )
        worst_wh = max(wh_cost, key=lambda w: wh_cost[w])

        order_cost = {t: 0.0 for t in p.periods}
        for arrival_t in p.periods:
            order_t = arrival_t - p.LT_OA[worst_wh] + 1
            if order_t in order_cost:
                inv = sol.I.get((worst_wh, arrival_t), 0.0)
                order_cost[order_t] += self._inventory_cost(worst_wh, arrival_t, inv)

        t_minus = sorted(p.periods, key=lambda t: -order_cost[t])[:q]
        return self._zero_periods(x, t_minus), t_minus

    # ------------------------------------------------------------------
    # Repair operators
    # ------------------------------------------------------------------

    def _r1_greedy(self, x_minus: QOAChrom, t_minus: List[Pd], sol: DecodedSolution) -> QOAChrom:
        """Lead-time-aware greedy repair."""
        out = dict(x_minus)
        for order_t in sorted(t_minus):
            scores = self._arrival_risk_scores(order_t, sol, regret_power=1.0)
            self._allocate_period(out, order_t, scores)
        return out

    def _r2_random(self, x_minus: QOAChrom, t_minus: List[Pd], sol: DecodedSolution) -> QOAChrom:
        """Random repair biased slightly by arrival-period risk."""
        out = dict(x_minus)
        for order_t in t_minus:
            risk = self._arrival_risk_scores(order_t, sol, regret_power=1.0)
            scores = {
                wh: self._rng.expovariate(1.0) * (1.0 + max(risk.get(wh, 0.0), 0.0))
                for wh in self._p.warehouses
            }
            self._allocate_period(out, order_t, scores)
        return out

    def _r3_regret(self, x_minus: QOAChrom, t_minus: List[Pd], sol: DecodedSolution) -> QOAChrom:
        """Lead-time-aware regret repair with stronger focus on severe risk."""
        out = dict(x_minus)
        for order_t in sorted(t_minus):
            scores = self._arrival_risk_scores(order_t, sol, regret_power=1.5)
            self._allocate_period(out, order_t, scores)
        return out

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _zero_periods(self, x: QOAChrom, periods: List[Pd]) -> QOAChrom:
        x_minus = dict(x)
        for t in periods:
            for wh in self._p.warehouses:
                x_minus[(wh, t)] = 0
        return x_minus

    def _inventory_cost(self, wh: Wh, t: Pd, inv: float) -> float:
        p = self._p
        return (
            p.Co.get((wh, t), 0.0) * max(inv - p.U.get((wh, t), 1e9), 0.0)
            + p.Cs.get((wh, t), 0.0) * max(p.L.get((wh, t), 0.0) - inv, 0.0)
            + p.Cb.get((wh, t), 0.0) * max(-inv, 0.0)
        )

    def _arrival_risk_scores(self, order_t: Pd, sol: DecodedSolution, regret_power: float) -> Dict[Wh, float]:
        p = self._p
        scores: Dict[Wh, float] = {}
        last_t = p.periods[-1]

        for wh in p.warehouses:
            arrival_t = order_t + p.LT_OA[wh] - 1
            if arrival_t > last_t:
                scores[wh] = 0.0
                continue

            prev_t = arrival_t - 1
            prev_inv = sol.I.get((wh, prev_t), p.BI.get(wh, 0.0))
            projected = prev_inv + p.delta_I.get((wh, arrival_t), 0.0)

            floor = p.L.get((wh, arrival_t), 0.0)
            shortage = max(floor - projected, 0.0)
            backorder = max(-projected, 0.0)
            overstock = max(projected - p.U.get((wh, arrival_t), 1e9), 0.0)

            risk = (
                p.Cs.get((wh, arrival_t), 0.0) * shortage
                + p.Cb.get((wh, arrival_t), 0.0) * backorder
                - 0.25 * p.Co.get((wh, arrival_t), 0.0) * overstock
            )
            scores[wh] = max(risk, 0.0) ** regret_power

        return scores

    def _allocate_period(self, out: QOAChrom, t: Pd, scores: Dict[Wh, float]) -> None:
        p = self._p
        cap = int(round(p.CAP[t]))
        total = sum(max(v, 0.0) for v in scores.values())

        if total <= 0:
            base = cap // len(p.warehouses)
            rem = cap - base * len(p.warehouses)
            for idx, wh in enumerate(p.warehouses):
                out[(wh, t)] = base + (1 if idx < rem else 0)
            return

        raw = {wh: max(scores[wh], 0.0) / total * cap for wh in p.warehouses}
        ints = {wh: int(v) for wh, v in raw.items()}
        diff = cap - sum(ints.values())
        ordered = sorted(p.warehouses, key=lambda w: -(raw[w] - ints[w]))
        for idx in range(max(0, diff)):
            ints[ordered[idx % len(ordered)]] += 1
        for wh in p.warehouses:
            out[(wh, t)] = max(0, ints[wh])


    def _repair_plt_quantities(self, x: QOAChrom, t_minus: List[Pd], sol: DecodedSolution) -> QOAChrom:
        """Repair direct Q_PLT quantity genes around altered OA periods using cost signals."""
        p = self._p
        out = dict(x)
        for ship_t in t_minus:
            if ship_t not in p.periods:
                continue
            cap_proxy = max(1.0, p.CAP.get(ship_t, 1.0))
            for src in p.warehouses:
                src_inv = sol.I.get((src, ship_t), p.BI.get(src, 0.0))
                src_cost = self._inventory_cost(src, ship_t, src_inv)
                src_surplus = max(src_inv - p.L.get((src, ship_t), 0.0), 0.0)

                for dst in p.warehouses:
                    if src == dst or not p.plt_valid(src, dst, ship_t):
                        continue
                    lt = p.LT_PLT.get((src, dst))
                    if lt is None:
                        continue
                    arr_t = ship_t + lt
                    if arr_t not in p.periods:
                        continue

                    dst_inv = sol.I.get((dst, arr_t), p.BI.get(dst, 0.0))
                    floor = p.L.get((dst, arr_t), 0.0)
                    dst_short = max(floor - dst_inv, 0.0)
                    dst_back = max(-dst_inv, 0.0)
                    dst_risk = (
                        p.Cs.get((dst, arr_t), 0.0) * dst_short
                        + p.Cb.get((dst, arr_t), 0.0) * dst_back
                    )
                    key = qplt_key(src, dst, ship_t)
                    cur = max(0.0, float(out.get(key, 0.0)))

                    if dst_risk > 0 and src_surplus > 0 and src_cost <= 1e-9:
                        # Request a meaningful quantity on promising route.
                        target = min(src_surplus, max(dst_short, dst_back, 0.10 * cap_proxy))
                        cur = max(cur, target)
                    elif dst_risk > 0 and src_surplus > 0:
                        target = min(src_surplus, max(dst_short, dst_back, 0.05 * cap_proxy))
                        cur = max(cur, 0.5 * target)
                    elif src_cost > 0:
                        # Source is risky; reduce outbound request.
                        cur = 0.5 * cur
                    else:
                        cur = 0.95 * cur

                    out[key] = max(0.0, cur)
        return out

    def _update_weights(self) -> None:
        for idx in range(len(self._destroys)):
            if self._n_d[idx] > 0:
                self._w_d[idx] = (1 - self._lam) * self._w_d[idx] + self._lam * (
                    self._pi_d[idx] / self._n_d[idx]
                )
                self._w_d[idx] = max(0.01, self._w_d[idx])
            self._pi_d[idx] = 0.0
            self._n_d[idx] = 0

        for idx in range(len(self._repairs)):
            if self._n_r[idx] > 0:
                self._w_r[idx] = (1 - self._lam) * self._w_r[idx] + self._lam * (
                    self._pi_r[idx] / self._n_r[idx]
                )
                self._w_r[idx] = max(0.01, self._w_r[idx])
            self._pi_r[idx] = 0.0
            self._n_r[idx] = 0

    @staticmethod
    def _weighted_choice(weights: List[float], rng: random.Random) -> int:
        total = sum(weights)
        if total <= 0:
            return rng.randrange(len(weights))
        r = rng.uniform(0, total)
        cum = 0.0
        for idx, w in enumerate(weights):
            cum += w
            if r <= cum:
                return idx
        return len(weights) - 1
