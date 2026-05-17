"""
core/decoder.py
===============
Chromosome → full solution decoder.

Single Responsibility: simulate inventory and PLT heuristic, produce
a DecodedSolution.

Reference:
  hybrid_ga_alns_standalone.tex §1.5  (Giải mã nhiễm sắc thể)
  hybrid_ga_alns_standalone.tex §1.4  (PLT heuristic, Algorithm 2)
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .objective import DecodedSolution, ObjectiveCalculator
from .problem   import Problem, QOAChrom, Wh, Pd


class Decoder:
    """
    Converts a chromosome (QOA matrix) into a fully evaluated DecodedSolution.
    """

    def __init__(self, problem: Problem, obj_calc: ObjectiveCalculator) -> None:
        self._p    = problem
        self._eval = obj_calc

    # ------------------------------------------------------------------
    def decode(self, chrom: QOAChrom) -> DecodedSolution:
        """
        Full decode pipeline:
          1. Compute q_OA, r_OA from chromosome
          2. Simulate inventory period-by-period
          3. Apply PLT heuristic where valid
          4. Evaluate fitness
        """
        p   = self._p
        sol = DecodedSolution()

        # --- Step 1: case-pack decomposition ---
        for wh in p.warehouses:
            for t in p.periods:
                q_oa_val      = chrom.get((wh, t), 0)
                sol.Q_OA[(wh, t)] = q_oa_val
                q_full        = q_oa_val // p.CP
                r_val         = q_oa_val - p.CP * q_full
                sol.q_OA[(wh, t)] = q_full
                sol.r_OA[(wh, t)] = r_val

        # --- Step 2 & 3: inventory simulation ---
        prev_inv: Dict[Wh, float] = {wh: p.BI[wh] for wh in p.warehouses}

        for t in p.periods:
            # Compute tentative inventory before PLT
            temp_inv: Dict[Wh, float] = {}
            for wh in p.warehouses:
                # OA received: placed LT_OA periods ago
                oa_arrival_t = t - p.LT_OA
                oa_in        = chrom.get((wh, oa_arrival_t), 0) if oa_arrival_t >= p.periods[0] else 0

                # PLT already committed in sol.Q_PLT (previous period decisions)
                plt_in = 0.0
                for src in p.warehouses:
                    if src == wh:
                        continue
                    lt_plt = p.LT_PLT.get((src, wh), 0)
                    plt_t  = t - lt_plt
                    plt_in += sol.Q_PLT.get((src, wh, plt_t), 0.0)

                di     = p.delta_I.get((wh, t), 0.0)
                # PLT outflows from this period (computed below)
                temp_inv[wh] = prev_inv[wh] + oa_in + plt_in + di

            # --- PLT heuristic (only in valid periods) ---
            plt_out: Dict[Wh, float] = {wh: 0.0 for wh in p.warehouses}

            # Check if ANY warehouse can receive PLT at this period
            any_plt = any(t in p.PLT_periods.get(wh, frozenset()) for wh in p.warehouses)
            if any_plt:
                need    = {}
                surplus = {}
                for wh in p.warehouses:
                    l_val = p.L.get((wh, t), 0.0)
                    if temp_inv[wh] < l_val:
                        need[wh]    = l_val - temp_inv[wh]
                    elif temp_inv[wh] > l_val:
                        surplus[wh] = temp_inv[wh] - l_val

                # Sort by magnitude (descending)
                need_whs    = sorted(need,    key=lambda w: -need[w])
                surplus_whs = sorted(surplus, key=lambda w: -surplus[w])

                for src in surplus_whs:
                    avail = surplus[src]
                    for dst in need_whs:
                        if need.get(dst, 0) <= 0:
                            continue
                        if not p.plt_valid(src, dst, t):
                            continue

                        transfer = min(avail, need[dst])
                        # Round down to full case-pack of receiving warehouse
                        k        = int(transfer // p.CP)
                        q_plt    = k * p.CP
                        if q_plt <= 0:
                            continue

                        sol.Q_PLT[(src, dst, t)] =  sol.Q_PLT.get((src, dst, t), 0.0) + q_plt
                        plt_out[src]             += q_plt
                        avail                    -= q_plt
                        need[dst]                 = max(0, need[dst] - q_plt)
                        surplus[src]              = avail

            # --- Finalise inventory ---
            for wh in p.warehouses:
                final_inv      = temp_inv[wh] - plt_out[wh]
                sol.I[(wh, t)] = final_inv

            prev_inv = {wh: sol.I[(wh, t)] for wh in p.warehouses}

        # --- Step 4: fitness ---
        self._eval.compute(sol)
        return sol
