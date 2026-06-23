"""
core/decoder.py
===============
Chromosome -> decoded solution.

V6 optimisation:
  - Chromosome explicitly contains both Q_OA and Q_PLT quantity genes.
  - OA arrival follows business indexing: order_t = arrival_t - LT_OA + 1.
  - PLT feasibility is enforced by the decoder using dynamic inventory:
        out(src,t) <= [I_pre(src,t) - L(src,t)]^+
  - Requested PLT quantities are filtered by objective-based positive saving.
  - No MILP/Gurobi is used; this is still a pure heuristic decoder.
"""
from __future__ import annotations

from typing import Dict, Tuple

from .objective import DecodedSolution, ObjectiveCalculator
from .problem import Problem, QOAChrom, Wh, Pd, qplt_key


class Decoder:
    """Converts a Q_OA + Q_PLT chromosome into inventory trajectories and fitness."""

    def __init__(self, problem: Problem, obj_calc: ObjectiveCalculator) -> None:
        self._p = problem
        self._eval = obj_calc

    def decode(self, chrom: QOAChrom) -> DecodedSolution:
        p = self._p
        sol = DecodedSolution()

        # Decode OA packing structure.
        for wh in p.warehouses:
            for t in p.periods:
                q_oa_val = int(round(chrom.get((wh, t), 0)))
                cp_val = p.case_pack(wh, t)
                q_full = q_oa_val // cp_val
                r_val = q_oa_val - cp_val * q_full
                sol.Q_OA[(wh, t)] = q_oa_val
                sol.q_OA[(wh, t)] = q_full
                sol.r_OA[(wh, t)] = r_val

        prev_inv: Dict[Wh, float] = {wh: p.BI[wh] for wh in p.warehouses}

        for t in p.periods:
            temp_inv: Dict[Wh, float] = {}

            # Inventory before outgoing PLT at period t.
            for wh in p.warehouses:
                order_t = t - p.LT_OA[wh] + 1
                oa_in = sol.Q_OA.get((wh, order_t), 0) if order_t in p.periods else 0

                plt_in = 0.0
                for src in p.warehouses:
                    if src == wh:
                        continue
                    lt_plt = p.LT_PLT.get((src, wh))
                    if lt_plt is None:
                        continue
                    ship_t = t - lt_plt
                    plt_in += sol.Q_PLT.get((src, wh, ship_t), 0.0)

                temp_inv[wh] = prev_inv[wh] + oa_in + plt_in + p.delta_I.get((wh, t), 0.0)

            plt_out: Dict[Wh, float] = {wh: 0.0 for wh in p.warehouses}
            self._apply_direct_qplt(t, temp_inv, plt_out, chrom, sol)

            for wh in p.warehouses:
                sol.I[(wh, t)] = temp_inv[wh] - plt_out[wh]

            prev_inv = {wh: sol.I[(wh, t)] for wh in p.warehouses}

        self._eval.compute(sol)
        return sol

    # ------------------------------------------------------------------
    # Direct PLT decoder
    # ------------------------------------------------------------------

    def _apply_direct_qplt(
        self,
        t: Pd,
        temp_inv: Dict[Wh, float],
        plt_out: Dict[Wh, float],
        chrom: QOAChrom,
        sol: DecodedSolution,
    ) -> None:
        """Decode direct Q_PLT genes using feasibility and cost-saving filters."""
        p = self._p
        last_t = p.periods[-1]

        # Dynamic stock available to send from each source at period t.
        surplus: Dict[Wh, float] = {
            wh: max(temp_inv[wh] - p.L.get((wh, t), 0.0), 0.0)
            for wh in p.warehouses
        }

        # Repeated insertion allows several PLT arcs in the same period while
        # respecting the decreasing source surplus.
        while True:
            best: Tuple[float, Wh, Wh, float] | None = None

            for src in p.warehouses:
                if surplus.get(src, 0.0) <= 1e-9:
                    continue
                src_current_inv = temp_inv[src] - plt_out[src]

                for dst in p.warehouses:
                    if src == dst or not p.plt_valid(src, dst, t):
                        continue
                    lt = p.LT_PLT.get((src, dst))
                    if lt is None:
                        continue
                    arr_t = t + lt
                    if arr_t > last_t:
                        continue

                    desired = self._desired_qplt(chrom, src, dst, t)
                    if desired <= 1e-9:
                        continue

                    future_need = self._future_need(dst, t, arr_t, temp_inv[dst], chrom, sol)
                    if future_need <= 1e-9:
                        continue

                    max_q = min(float(desired), surplus[src], future_need)
                    q_candidates = self._quantity_candidates(max_q, p.case_pack(dst, t), desired)
                    if not q_candidates:
                        continue

                    for q in q_candidates:
                        saving = self._plt_saving(
                            src=src,
                            dst=dst,
                            ship_t=t,
                            arr_t=arr_t,
                            q=q,
                            src_current_inv=src_current_inv,
                            dst_current_inv=temp_inv[dst],
                            chrom=chrom,
                            sol=sol,
                        )
                        if saving <= 1e-9:
                            continue

                        # Direct Q_PLT gene is the main decision. Rank by true
                        # saving with a small preference for quantities close to
                        # the gene value.
                        closeness = 1.0 / (1.0 + abs(float(desired) - q) / max(q, 1.0))
                        score = saving * (0.75 + 0.25 * closeness)
                        if best is None or score > best[0]:
                            best = (score, src, dst, q)

            if best is None:
                break

            _, src, dst, q = best
            sol.Q_PLT[(src, dst, t)] = sol.Q_PLT.get((src, dst, t), 0.0) + q
            plt_out[src] += q
            surplus[src] = max(surplus[src] - q, 0.0)

    def _desired_qplt(self, chrom: QOAChrom, src: Wh, dst: Wh, t: Pd) -> float:
        """Return non-negative requested PLT quantity gene."""
        try:
            return max(0.0, float(chrom.get(qplt_key(src, dst, t), 0.0)))
        except Exception:
            return 0.0

    def _quantity_candidates(self, max_q: float, cp: int, desired: float) -> Tuple[float, ...]:
        """Candidate quantities around the direct Q_PLT gene and full-case blocks."""
        if max_q <= 1e-9:
            return tuple()
        cp = max(1, int(cp))
        candidates = {max(1.0, min(max_q, float(round(desired))))}

        max_cases = int(max_q // cp)
        desired_cases = int(max(0.0, desired) // cp)
        for c in {
            1,
            2,
            4,
            max(1, desired_cases),
            max(1, desired_cases // 2),
            min(max_cases, desired_cases + 1),
            max(1, max_cases // 2),
            max_cases,
        }:
            if 1 <= c <= max_cases:
                candidates.add(float(c * cp))

        # Also try residual quantities when the gene explicitly asks for them.
        if desired > 0:
            candidates.add(float(min(max_q, max(1, int(round(desired))))))
            candidates.add(float(min(max_q, max(1, int(round(0.5 * desired))))))

        return tuple(sorted(q for q in candidates if 0 < q <= max_q + 1e-9))

    def _future_need(
        self,
        wh: Wh,
        current_t: Pd,
        start_t: Pd,
        current_inv: float,
        chrom: QOAChrom,
        sol: DecodedSolution,
    ) -> float:
        """Maximum shortage/backorder quantity from start_t to the horizon."""
        p = self._p
        last_t = p.periods[-1]
        need = 0.0
        for tau in range(start_t, last_t + 1):
            before = self._project_inventory(wh, current_t, tau, current_inv, chrom, sol)
            need = max(need, p.L.get((wh, tau), 0.0) - before, -before, 0.0)
        return need

    def _plt_saving(
        self,
        src: Wh,
        dst: Wh,
        ship_t: Pd,
        arr_t: Pd,
        q: float,
        src_current_inv: float,
        dst_current_inv: float,
        chrom: QOAChrom,
        sol: DecodedSolution,
    ) -> float:
        """Net PLT saving over the remaining horizon."""
        p = self._p

        dst_delta_cost = self._path_delta_cost(dst, ship_t, arr_t, dst_current_inv, q, chrom, sol)
        destination_benefit = -dst_delta_cost

        src_delta_cost = self._path_delta_cost(src, ship_t, ship_t, src_current_inv, -q, chrom, sol)
        source_opportunity_cost = src_delta_cost

        route_already_used = sol.Q_PLT.get((src, dst, ship_t), 0.0) > 0
        transport = 0.0 if route_already_used else p.dist.get((src, dst), p.dist.get((dst, src), 0.0)) * p.TC

        cp_dst = p.case_pack(dst, ship_t)
        residual_penalty = p.Cp_plt.get((src, dst, ship_t), 0.0) if q % cp_dst > 0 else 0.0

        return destination_benefit - source_opportunity_cost - transport - residual_penalty

    def _path_delta_cost(
        self,
        wh: Wh,
        current_t: Pd,
        start_t: Pd,
        current_inv: float,
        delta: float,
        chrom: QOAChrom,
        sol: DecodedSolution,
    ) -> float:
        """Sum of after-before inventory cost from start_t to horizon."""
        p = self._p
        total = 0.0
        for tau in range(start_t, p.periods[-1] + 1):
            before = self._project_inventory(wh, current_t, tau, current_inv, chrom, sol)
            after = before + delta
            total += self._inventory_cost(wh, tau, after) - self._inventory_cost(wh, tau, before)
        return total

    def _inventory_cost(self, wh: Wh, t: Pd, inv: float) -> float:
        p = self._p
        return (
            p.Co.get((wh, t), 0.0) * max(inv - p.U.get((wh, t), 1e9), 0.0)
            + p.Cs.get((wh, t), 0.0) * max(p.L.get((wh, t), 0.0) - inv, 0.0)
            + p.Cb.get((wh, t), 0.0) * max(-inv, 0.0)
        )

    def _project_inventory(
        self,
        wh: Wh,
        current_t: Pd,
        target_t: Pd,
        current_inv: float,
        chrom: QOAChrom,
        sol: DecodedSolution,
    ) -> float:
        """Crude projection from current_t to target_t, using known OA and accepted PLT arrivals."""
        p = self._p
        inv = current_inv
        if target_t <= current_t:
            return inv
        for tau in range(current_t + 1, target_t + 1):
            inv += p.delta_I.get((wh, tau), 0.0)
            order_t = tau - p.LT_OA[wh] + 1
            if order_t in p.periods:
                inv += chrom.get((wh, order_t), 0.0)
            for src in p.warehouses:
                if src == wh:
                    continue
                lt = p.LT_PLT.get((src, wh))
                if lt is None:
                    continue
                ship_t = tau - lt
                inv += sol.Q_PLT.get((src, wh, ship_t), 0.0)
        return inv
