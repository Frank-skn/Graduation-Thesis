"""
alns/alns_solver.py
===================
Adaptive Large Neighborhood Search solver (local search component).

Single Responsibility: given a chromosome + decoded solution, run
destroy→repair→evaluate iterations with adaptive operator weights
and SA acceptance.

Reference:
  hybrid_ga_alns_standalone.tex §3 (ALNS), §4.1-4.3 (Hybrid integration)

Operators:
  Destroy:  D1 Random Period, D2 Worst-Cost, D3 Facility-Focused
  Repair:   R1 Greedy Demand, R2 Random Dirichlet, R3 Regret-Based
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

from ..core.constraints import ConstraintHandler
from ..core.decoder      import Decoder
from ..core.objective    import DecodedSolution, ObjectiveCalculator
from ..core.problem      import Problem, QOAChrom, Wh, Pd


# ---------------------------------------------------------------------------
# ALNS Solver
# ---------------------------------------------------------------------------

class ALNSSolver:
    """
    Adaptive LNS with Simulated-Annealing acceptance and weight adaptation.
    """

    # Scoring constants
    _SIGMA = {
        "new_best"  : 3,
        "better"    : 2,
        "accepted"  : 1,
        "rejected"  : 0,
    }

    def __init__(
        self,
        problem       : Problem,
        decoder       : Decoder,
        obj_calc      : ObjectiveCalculator,
        constraint    : ConstraintHandler,
        n_iterations  : int   = 60,
        q_min_ratio   : float = 0.10,
        q_max_ratio   : float = 0.40,
        lambda_rho    : float = 0.15,
        segment_size  : int   = 20,
        sa_accept_prob: float = 0.05,
        sa_cooling    : float = 0.995,
        rng           : random.Random | None = None,
    ) -> None:
        self._p        = problem
        self._dec      = decoder
        self._eval     = obj_calc
        self._ch       = constraint
        self._n_iter   = n_iterations
        self._q_min    = max(1, int(math.ceil(q_min_ratio * len(problem.periods))))
        self._q_max    = max(1, int(math.ceil(q_max_ratio * len(problem.periods))))
        self._lam      = lambda_rho
        self._seg      = segment_size
        self._accept_p = sa_accept_prob
        self._cooling  = sa_cooling
        self._rng      = rng or random.Random()

        # Operator lists
        self._destroys = [self._d1_random, self._d2_worst_cost, self._d3_facility]
        self._repairs  = [self._r1_greedy, self._r2_random,    self._r3_regret]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        chrom : QOAChrom,
        sol   : DecodedSolution,
    ) -> Tuple[DecodedSolution, QOAChrom]:
        """
        Run ALNS local search.

        Returns (best_decoded_solution, best_chromosome).
        """
        p   = self._p
        rng = self._rng

        # Working copies
        x_cur  = dict(chrom)
        x_best = dict(chrom)
        f_cur  = sol.fitness
        f_best = sol.fitness
        s_best = sol

        # Adaptive weights (reset each ALNS call)
        w_d   = [1.0] * len(self._destroys)
        w_r   = [1.0] * len(self._repairs)
        pi_d  = [0.0] * len(self._destroys)
        pi_r  = [0.0] * len(self._repairs)
        n_d   = [0]   * len(self._destroys)
        n_r   = [0]   * len(self._repairs)

        # SA temperature calibration
        delta_init = 0.01 * abs(f_cur) if f_cur != 0 else 1.0
        theta = -delta_init / math.log(self._accept_p) if self._accept_p < 1.0 else 1.0

        for it in range(1, self._n_iter + 1):
            # Select operators
            d_idx = self._weighted_choice(w_d, rng)
            r_idx = self._weighted_choice(w_r, rng)

            q = rng.randint(self._q_min, self._q_max)

            # Destroy
            x_minus, t_minus = self._destroys[d_idx](x_cur, sol)

            # Repair
            x_prime = self._repairs[r_idx](x_minus, t_minus, sol)
            x_prime = self._ch.repair(x_prime)

            # Evaluate
            sol_prime = self._dec.decode(x_prime)
            f_prime   = sol_prime.fitness

            # Score and acceptance
            if f_prime < f_best:
                score  = self._SIGMA["new_best"]
                x_best = dict(x_prime)
                f_best = f_prime
                s_best = sol_prime
            elif f_prime < f_cur:
                score = self._SIGMA["better"]
            elif theta > 0 and rng.random() < math.exp(-(f_prime - f_cur) / theta):
                score = self._SIGMA["accepted"]
            else:
                score = self._SIGMA["rejected"]

            # Accept current?
            if score >= self._SIGMA["accepted"]:
                x_cur = dict(x_prime)
                f_cur = f_prime
                sol   = sol_prime

            # Accumulate scores
            pi_d[d_idx] += score
            pi_r[r_idx] += score
            n_d[d_idx]  += 1
            n_r[r_idx]  += 1

            # Cool down
            theta *= self._cooling

            # Weight update every segment
            if it % self._seg == 0:
                for idx in range(len(self._destroys)):
                    if n_d[idx] > 0:
                        w_d[idx] = (
                            (1 - self._lam) * w_d[idx]
                            + self._lam * (pi_d[idx] / n_d[idx])
                        )
                        w_d[idx] = max(0.01, w_d[idx])
                    pi_d[idx] = 0.0
                    n_d[idx]  = 0
                for idx in range(len(self._repairs)):
                    if n_r[idx] > 0:
                        w_r[idx] = (
                            (1 - self._lam) * w_r[idx]
                            + self._lam * (pi_r[idx] / n_r[idx])
                        )
                        w_r[idx] = max(0.01, w_r[idx])
                    pi_r[idx] = 0.0
                    n_r[idx]  = 0

        return s_best, x_best

    # ------------------------------------------------------------------
    # Destroy operators
    # ------------------------------------------------------------------

    def _d1_random(
        self, x: QOAChrom, sol: DecodedSolution
    ) -> Tuple[QOAChrom, List[Pd]]:
        """D1: Random Period Destroy."""
        p   = self._p
        rng = self._rng
        q   = rng.randint(self._q_min, self._q_max)
        t_minus = rng.sample(list(p.periods), min(q, len(p.periods)))
        x_minus = dict(x)
        for t in t_minus:
            for wh in p.warehouses:
                x_minus[(wh, t)] = 0
        return x_minus, t_minus

    def _d2_worst_cost(
        self, x: QOAChrom, sol: DecodedSolution
    ) -> Tuple[QOAChrom, List[Pd]]:
        """D2: Worst Cost Period Destroy."""
        p   = self._p
        rng = self._rng
        q   = rng.randint(self._q_min, self._q_max)

        # Sum inventory cost per period
        period_cost: Dict[Pd, float] = {}
        for t in p.periods:
            c = 0.0
            for wh in p.warehouses:
                inv   = sol.I.get((wh, t), 0.0)
                u_val = p.U.get((wh, t), 1e9)
                l_val = p.L.get((wh, t), 0.0)
                c += (
                    p.Co.get((wh, t), 0.0) * max(inv - u_val, 0.0)
                    + p.Cs.get((wh, t), 0.0) * max(l_val - inv, 0.0)
                    + p.Cb.get((wh, t), 0.0) * max(-inv, 0.0)
                )
            period_cost[t] = c

        t_minus = sorted(p.periods, key=lambda t: -period_cost[t])[:q]
        x_minus = dict(x)
        for t in t_minus:
            for wh in p.warehouses:
                x_minus[(wh, t)] = 0
        return x_minus, t_minus

    def _d3_facility(
        self, x: QOAChrom, sol: DecodedSolution
    ) -> Tuple[QOAChrom, List[Pd]]:
        """D3: Facility-Focused Destroy — targets the most deviating warehouse."""
        p   = self._p
        rng = self._rng
        q   = rng.randint(self._q_min, self._q_max)

        # Find warehouse with largest total deviation
        dev_wh: Dict[Wh, float] = {}
        for wh in p.warehouses:
            dev = 0.0
            for t in p.periods:
                inv   = sol.I.get((wh, t), 0.0)
                u_val = p.U.get((wh, t), 1e9)
                l_val = p.L.get((wh, t), 0.0)
                dev  += max(inv - u_val, 0.0) + max(l_val - inv, 0.0)
            dev_wh[wh] = dev

        worst_wh = max(dev_wh, key=lambda w: dev_wh[w])

        # Periods with largest shortage for worst_wh
        shortage_per_t = {
            t: max(p.L.get((worst_wh, t), 0.0) - sol.I.get((worst_wh, t), 0.0), 0.0)
            for t in p.periods
        }
        t_minus = sorted(p.periods, key=lambda t: -shortage_per_t[t])[:q]

        x_minus = dict(x)
        for t in t_minus:
            for wh in p.warehouses:
                x_minus[(wh, t)] = 0
        return x_minus, t_minus

    # ------------------------------------------------------------------
    # Repair operators
    # ------------------------------------------------------------------

    def _r1_greedy(
        self, x_minus: QOAChrom, t_minus: List[Pd], sol: DecodedSolution
    ) -> QOAChrom:
        """R1: Greedy Demand-based Repair."""
        p   = self._p
        rng = self._rng
        out = dict(x_minus)
        for t in sorted(t_minus):
            demand: Dict[Wh, float] = {}
            for wh in p.warehouses:
                prev_inv = sol.I.get((wh, t - 1), p.BI.get(wh, 0.0))
                demand[wh] = max(0.0, p.L.get((wh, t), 0.0) - prev_inv)
            total_d = sum(demand.values())
            cap     = p.CAP[t]
            if total_d <= 0:
                for wh in p.warehouses:
                    out[(wh, t)] = int(cap // len(p.warehouses))
            else:
                raw  = {wh: demand[wh] / total_d * cap for wh in p.warehouses}
                ints = {wh: int(v) for wh, v in raw.items()}
                diff = int(round(cap)) - sum(ints.values())
                ordered = sorted(p.warehouses, key=lambda w: -(raw[w] - ints[w]))
                for idx in range(max(0, diff)):
                    ints[ordered[idx % len(p.warehouses)]] += 1
                out.update(ints)
        return out

    def _r2_random(
        self, x_minus: QOAChrom, t_minus: List[Pd], sol: DecodedSolution
    ) -> QOAChrom:
        """R2: Random Dirichlet Repair."""
        from numpy.random import dirichlet as np_dirichlet
        p   = self._p
        rng = self._rng
        out = dict(x_minus)
        for t in t_minus:
            weights = np_dirichlet([1.0] * len(p.warehouses))
            cap     = p.CAP[t]
            ints    = [int(w * cap) for w in weights]
            diff    = int(round(cap)) - sum(ints)
            for idx in range(abs(diff)):
                ints[idx % len(ints)] += 1 if diff > 0 else -1
            for wh, v in zip(p.warehouses, ints):
                out[(wh, t)] = max(0, v)
        return out

    def _r3_regret(
        self, x_minus: QOAChrom, t_minus: List[Pd], sol: DecodedSolution
    ) -> QOAChrom:
        """R3: Regret-based Repair."""
        p   = self._p
        out = dict(x_minus)
        for t in sorted(t_minus):
            regret: Dict[Wh, float] = {}
            for wh in p.warehouses:
                prev_inv = sol.I.get((wh, t - 1), p.BI.get(wh, 0.0))
                regret[wh] = (
                    p.Cs.get((wh, t), 0.0) * max(p.L.get((wh, t), 0.0) - prev_inv, 0.0)
                    + p.Cb.get((wh, t), 0.0) * max(-prev_inv, 0.0)
                )
            total_r = sum(regret.values())
            cap     = p.CAP[t]
            if total_r <= 0:
                for wh in p.warehouses:
                    out[(wh, t)] = int(cap // len(p.warehouses))
            else:
                raw  = {wh: regret[wh] / total_r * cap for wh in p.warehouses}
                ints = {wh: int(v) for wh, v in raw.items()}
                diff = int(round(cap)) - sum(ints.values())
                ordered = sorted(p.warehouses, key=lambda w: -(raw[w] - ints[w]))
                for idx in range(max(0, diff)):
                    ints[ordered[idx % len(p.warehouses)]] += 1
                out.update(ints)
        return out

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _weighted_choice(weights: List[float], rng: random.Random) -> int:
        total = sum(weights)
        r     = rng.uniform(0, total)
        cum   = 0.0
        for idx, w in enumerate(weights):
            cum += w
            if r <= cum:
                return idx
        return len(weights) - 1
