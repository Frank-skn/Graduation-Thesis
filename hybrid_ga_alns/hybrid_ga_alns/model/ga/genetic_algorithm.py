"""
ga/genetic_algorithm.py
=======================
Main GA loop with population management, selection, and ALNS integration.

Single Responsibility: orchestrate the GA lifecycle and delegate
crossover/mutation to GeneticOperators and local search to ALNSSolver.

Reference:
  hybrid_ga_alns_standalone.tex §1 (population init), §2 (GA loop),
  §4 (Hybrid integration, Algorithm 9)
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..core.constraints import ConstraintHandler
from ..core.decoder      import Decoder
from ..core.objective    import DecodedSolution, ObjectiveCalculator
from ..core.problem      import Problem, QOAChrom, Wh, Pd
from .operators          import GeneticOperators


# ---------------------------------------------------------------------------
# Individual
# ---------------------------------------------------------------------------

@dataclass
class Individual:
    chrom  : QOAChrom
    fitness: float = float("inf")
    sol    : Optional[DecodedSolution] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# GA
# ---------------------------------------------------------------------------

class GeneticAlgorithm:
    """
    Population-based GA with Lamarckian ALNS local search.

    Parameters are injected; no direct config access here (DIP).
    """

    def __init__(
        self,
        problem       : Problem,
        decoder       : Decoder,
        obj_calc      : ObjectiveCalculator,
        constraint    : ConstraintHandler,
        operators     : GeneticOperators,
        alns_solver   ,                        # ALNSSolver (injected, avoids circular import)
        n_pop         : int   = 50,
        G_max         : int   = 300,
        G_stag        : int   = 60,
        k_tournament  : int   = 3,
        delta_G       : int   = 5,
        top_k_alns    : int   = 10,
        time_limit_s  : float = 300.0,
        milp_seed     : Optional[QOAChrom] = None,
        rng           : random.Random | None = None,
        log_callback  : Optional[Callable[[int, float], None]] = None,
    ) -> None:
        self._p          = problem
        self._dec        = decoder
        self._eval       = obj_calc
        self._ch         = constraint
        self._ops        = operators
        self._alns       = alns_solver
        self._n_pop      = n_pop
        self._G_max      = G_max
        self._G_stag     = G_stag
        self._k_tour     = k_tournament
        self._delta_G    = delta_G
        self._top_k      = top_k_alns
        self._time_limit = time_limit_s
        self._milp_seed  = milp_seed
        self._rng        = rng or random.Random()
        self._log        = log_callback

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> Tuple[QOAChrom, DecodedSolution]:
        """
        Run the full Hybrid GA-ALNS and return (best_chromosome, best_solution).
        """
        t_start = time.perf_counter()

        pop = self._init_population()
        self._evaluate_population(pop)
        pop.sort(key=lambda ind: ind.fitness)

        best      = pop[0]
        no_impr   = 0
        gen       = 0

        while gen < self._G_max and no_impr < self._G_stag:
            # --- Time limit guard ---
            if time.perf_counter() - t_start > self._time_limit:
                break

            gen += 1

            # --- Selection ---
            parents = self._tournament_select(pop)

            # --- Crossover + Mutation → offspring ---
            offspring: List[Individual] = []
            it = iter(parents)
            for p1, p2 in zip(it, it):
                c1, c2 = self._ops.crossover(p1.chrom, p2.chrom)
                c1     = self._ops.mutate(c1)
                c2     = self._ops.mutate(c2)
                c1     = self._ch.repair(c1)
                c2     = self._ch.repair(c2)
                offspring.extend([Individual(c1), Individual(c2)])

            if len(parents) % 2 == 1:
                last = self._ops.mutate(dict(parents[-1].chrom))
                last = self._ch.repair(last)
                offspring.append(Individual(last))

            # --- Decode, optional ALNS, evaluate ---
            use_alns = (gen % self._delta_G == 0) or (no_impr >= self._G_stag // 2)
            for ind in offspring:
                sol = self._dec.decode(ind.chrom)
                if use_alns:
                    sol, improved_chrom = self._alns.run(ind.chrom, sol)
                    ind.chrom  = improved_chrom   # Lamarckian update
                ind.fitness = sol.fitness
                ind.sol     = sol

            # --- μ + λ replacement with elitism ---
            combined = pop + offspring
            combined.sort(key=lambda i: i.fitness)
            # Remove exact duplicates (same chrom)
            seen: List[QOAChrom] = []
            unique: List[Individual] = []
            for ind in combined:
                if not any(ind.chrom == s for s in seen):
                    seen.append(ind.chrom)
                    unique.append(ind)
            pop = unique[:self._n_pop]

            # --- Track best ---
            if pop[0].fitness < best.fitness:
                best    = pop[0]
                no_impr = 0
            else:
                no_impr += 1

            if self._log:
                self._log(gen, best.fitness)

        return best.chrom, best.sol  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Population initialisation  (Algorithm 1)
    # ------------------------------------------------------------------

    def _init_population(self) -> List[Individual]:
        p         = self._p
        n         = self._n_pop
        rng       = self._rng
        pop: List[Individual] = []

        # 1) MILP seed (individual 0)
        if self._milp_seed is not None:
            chrom = self._ch.repair(dict(self._milp_seed))
            pop.append(Individual(chrom))

            # 2) Perturb MILP seed ( ≈ 50% of pop )
            n_milp_perturb = int(0.5 * n)
            while len(pop) < n_milp_perturb:
                perturbed: QOAChrom = {}
                for wh in p.warehouses:
                    for t in p.periods:
                        eps       = rng.uniform(-0.15, 0.15)
                        v         = max(0, int(self._milp_seed.get((wh, t), 0) * (1 + eps)))
                        perturbed[(wh, t)] = v
                perturbed = self._ch.repair(perturbed)
                pop.append(Individual(perturbed))
        else:
            n_milp_perturb = 0

        # 3) Demand-heuristic individuals ( ≈ 30% )
        n_heuristic = max(0, int(0.3 * n) - max(0, n_milp_perturb - 1))
        for _ in range(n_heuristic):
            chrom = self._demand_heuristic_chrom()
            pop.append(Individual(chrom))

        # 4) Remaining: Dirichlet-random
        from numpy.random import dirichlet as np_dirichlet
        while len(pop) < n:
            chrom: QOAChrom = {}
            for t in p.periods:
                weights = np_dirichlet([1.0] * len(p.warehouses))
                cap     = p.CAP[t]
                raw     = [int(w * cap) for w in weights]
                diff    = int(round(cap)) - sum(raw)
                # Distribute residual
                for idx in range(abs(diff)):
                    raw[idx % len(raw)] += 1 if diff > 0 else -1
                for wh, v in zip(p.warehouses, raw):
                    chrom[(wh, t)] = max(0, v)
            chrom = self._ch.repair(chrom)
            pop.append(Individual(chrom))

        return pop

    def _demand_heuristic_chrom(self) -> QOAChrom:
        """Proportional allocation based on shortage need."""
        p     = self._p
        chrom : QOAChrom = {}
        for t in p.periods:
            deltas = {}
            for wh in p.warehouses:
                demand_proxy = max(0.0, p.L.get((wh, t), 0.0) - p.BI.get(wh, 0.0))
                deltas[wh]   = demand_proxy
            total_d = sum(deltas.values())
            cap     = p.CAP[t]
            if total_d <= 0:
                for wh in p.warehouses:
                    chrom[(wh, t)] = int(cap // len(p.warehouses))
            else:
                raw  = {wh: deltas[wh] / total_d * cap for wh in p.warehouses}
                ints = {wh: int(v) for wh, v in raw.items()}
                diff = int(round(cap)) - sum(ints.values())
                ordered = sorted(p.warehouses, key=lambda w: -(raw[w] - ints[w]))
                for idx in range(max(0, diff)):
                    ints[ordered[idx % len(p.warehouses)]] += 1
                chrom.update(ints)
        return self._ch.repair(chrom)

    # ------------------------------------------------------------------
    # Tournament selection  (Algorithm 2)
    # ------------------------------------------------------------------

    def _tournament_select(self, pop: List[Individual]) -> List[Individual]:
        rng      = self._rng
        k        = self._k_tour
        n_select = self._n_pop  # select as many as population size
        selected : List[Individual] = []
        while len(selected) < n_select:
            contestants = rng.choices(pop, k=min(k, len(pop)))
            selected.append(min(contestants, key=lambda ind: ind.fitness))
        return selected

    # ------------------------------------------------------------------
    # Batch evaluation
    # ------------------------------------------------------------------

    def _evaluate_population(self, pop: List[Individual]) -> None:
        for ind in pop:
            if ind.fitness == float("inf"):
                sol         = self._dec.decode(ind.chrom)
                ind.fitness = sol.fitness
                ind.sol     = sol
