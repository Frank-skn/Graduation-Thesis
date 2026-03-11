"""
Optimization service orchestration — PuLP per-item solver.
Follows Single Responsibility Principle.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any

from backend.schemas.optimization import OptimizationInput, OptimizationOutput
from optimization.models.ss_mb_smi import solve_ss_mb_smi, extract_solution_dicts
from optimization.solvers.solver_strategies import SolverFactory, interpret_solver_status


@dataclass
class OptimizationResult:
    """Container for optimization results."""
    solver_status: str
    solve_time: float
    objective_value: float
    mip_gap: float
    output: OptimizationOutput
    kpis: Dict[str, float]
    is_optimal: bool
    is_feasible: bool
    message: str
    # Extended metrics
    baseline_cost: float = 0.0
    savings: float = 0.0
    savings_pct: float = 0.0
    n_changes: int = 0
    si_mean: float = 0.0
    ss_below_count: int = 0
    # Proportional allocation comparison
    prop_cost: float = 0.0
    savings_vs_prop: float = 0.0
    savings_pct_prop: float = 0.0


def _baseline_cost(data: OptimizationInput) -> float:
    """
    Baseline = do-nothing cost: let inventory roll forward as
        base_inv[i,j,t] = BI[i,j] + DI[i,j,t1] + DI[i,j,t2] + ... + DI[i,j,t]
    (no shipments), evaluate costs at each (i,j,t).
    Mirrors temp.py exactly.
    """
    T_sorted = sorted({t for (_, _, t) in data.DI.keys()})
    IJ_pairs = sorted({(i, j) for (i, j, _) in data.DI.keys()})
    total = 0.0
    for (i, j) in IJ_pairs:
        prev = data.BI.get((i, j), 0.0)
        for t in T_sorted:
            prev += data.DI.get((i, j, t), 0.0)  # cumulative carry-forward
            iv = prev
            ov = max(0.0, iv - data.U.get((i, j, t), 9999.0))
            sh = max(0.0, data.L.get((i, j, t), 0.0) - iv)
            bk = max(0.0, -iv)
            total += (
                data.Co.get((i, j, t), 0.0) * ov
                + data.Cs.get((i, j, t), 0.0) * sh
                + data.Cb.get((i, j, t), 0.0) * bk
            )
    return total


def _proportional_allocation_cost(data: OptimizationInput) -> float:
    """
    Heuristic baseline: phân bổ CAP[i,t] theo tỉ lệ deficit so với floor.

    Mô phỏng cách người quản lý kho thực tế ra quyết định:
    - Ai thiếu nhiều nhất → nhận nhiều nhất
    - Không ai thiếu → chia đều
    - Làm tròn xuống bội số case-pack (CP) để sát thực tế vận hành
    - Phần dư sau làm tròn → ưu tiên cho warehouse thiếu nhất

    Khác biệt với MILP:
    - Myopic: quyết định từng kỳ, không nhìn trước các kỳ sau
    - Không tối ưu toàn cục: có thể tạo overstock khi không ai thiếu
      nhưng CAP vẫn phải phân bổ hết (equality constraint)
    """
    T_sorted = sorted({t for (_, _, t) in data.DI.keys()})
    items = sorted({i for (i, _) in data.CAP.keys()})
    IJ_pairs = sorted({(i, j) for (i, j, _) in data.DI.keys()})

    total_cost = 0.0

    for i in items:
        j_list = sorted({j for (ii, j) in IJ_pairs if ii == i})
        if not j_list:
            continue

        # Theo dõi tồn kho thực tế qua từng kỳ (carry-forward)
        current_inv: Dict[str, float] = {
            j: data.BI.get((i, j), 0.0) for j in j_list
        }

        for t in T_sorted:
            # 1. Cập nhật tồn kho theo biến động cầu (DI)
            for j in j_list:
                current_inv[j] += data.DI.get((i, j, t), 0.0)

            cap = data.CAP.get((i, t), 0.0)

            # 2. Tính deficit: mức thiếu so với floor sau khi đã tính DI
            deficit: Dict[str, float] = {
                j: max(0.0, data.L.get((i, j, t), 0.0) - current_inv[j])
                for j in j_list
            }
            total_deficit = sum(deficit.values())

            # 3. Phân bổ theo tỉ lệ deficit, làm tròn xuống bội số CP
            alloc: Dict[str, float] = {}
            if total_deficit > 0:
                for j in j_list:
                    cp_ij = max(1, int(data.CP.get((i, j), 1)))
                    raw = cap * (deficit[j] / total_deficit)
                    alloc[j] = float(int(raw // cp_ij) * cp_ij)
            else:
                # Không ai thiếu → chia đều theo CP
                n = len(j_list)
                for j in j_list:
                    cp_ij = max(1, int(data.CP.get((i, j), 1)))
                    raw = cap / n
                    alloc[j] = float(int(raw // cp_ij) * cp_ij)

            # 4. Phân bổ phần dư (do làm tròn) cho warehouse thiếu nhất trước
            remainder = cap - sum(alloc.values())
            if remainder > 0:
                j_priority = sorted(
                    j_list,
                    key=lambda j: deficit.get(j, 0.0),
                    reverse=True,
                )
                min_cp = min(max(1, int(data.CP.get((i, j), 1))) for j in j_list)
                for j in j_priority:
                    if remainder < min_cp:
                        break
                    cp_ij = max(1, int(data.CP.get((i, j), 1)))
                    extra = float(int(remainder // cp_ij) * cp_ij)
                    if extra > 0:
                        alloc[j] += extra
                        remainder -= extra

            # 5. Cập nhật tồn kho sau giao hàng và tính chi phí
            for j in j_list:
                current_inv[j] += alloc.get(j, 0.0)
                iv = current_inv[j]
                ov = max(0.0, iv - data.U.get((i, j, t), 9999.0))
                sh = max(0.0, data.L.get((i, j, t), 0.0) - iv)
                bk = max(0.0, -iv)
                total_cost += (
                    data.Co.get((i, j, t), 0.0) * ov
                    + data.Cs.get((i, j, t), 0.0) * sh
                    + data.Cb.get((i, j, t), 0.0) * bk
                )

    return total_cost


class OptimizationService:
    """Service for executing SS-MB-SMI optimisation via PuLP CBC."""

    def __init__(
        self,
        solver: str = "cbc",
        time_limit: int = 300,
        mip_gap: float = 0.01,
    ):
        self.solver_strategy = SolverFactory.create_solver(solver)
        self.time_limit = time_limit
        self.mip_gap = mip_gap

    # ------------------------------------------------------------------
    def solve(self, data: OptimizationInput) -> OptimizationResult:
        """
        Execute the per-item PuLP optimisation and return a rich result.
        """
        n_items = len(data.I)
        print(f"[OptimizationService] Solving {n_items} items via PuLP CBC …")

        # --- Step 1: run solver ---
        model_sol = solve_ss_mb_smi(data, time_limit_per_item=self.time_limit)

        status_info = interpret_solver_status(model_sol.solver_status)

        if not status_info["is_feasible"]:
            return OptimizationResult(
                solver_status=model_sol.solver_status,
                solve_time=model_sol.solve_time_seconds,
                objective_value=0.0,
                mip_gap=self.mip_gap,
                output=OptimizationOutput(results=[]),
                kpis=self._zero_kpis(),
                is_optimal=False,
                is_feasible=False,
                message=status_info["message"],
            )

        # --- Step 2: extract flat result rows ---
        rows = extract_solution_dicts(model_sol, data)

        # --- Step 3: KPIs ---
        kpis = self._calculate_kpis(rows, data)

        # --- Step 4: baseline & savings ---
        baseline = _baseline_cost(data)
        prop_cost = _proportional_allocation_cost(data)
        opt_cost = model_sol.objective_value
        savings  = max(0.0, baseline - opt_cost)
        savings_pct = (savings / baseline * 100) if baseline > 0 else 0.0
        savings_vs_prop = max(0.0, prop_cost - opt_cost)
        savings_pct_prop = (savings_vs_prop / prop_cost * 100) if prop_cost > 0 else 0.0

        # --- Step 5: SI / SS metrics ---
        si_values = []
        ss_below  = 0
        for r in rows:
            i, j, t = r["product_id"], r["warehouse_id"], r["time_period"]
            inv = r["net_inventory"]
            l   = data.L.get((i, j, t), 0.0)
            u   = data.U.get((i, j, t), 9999.0)
            si = inv / max(l, 1.0)
            si_values.append(si)
            if inv < l:
                ss_below += 1

        si_mean = sum(si_values) / len(si_values) if si_values else 0.0

        # n_changes: rows where actual shipment (q*CP + r) > 0 in action periods
        T_sorted = sorted(data.T)
        action_periods = set(T_sorted[:2])  # first 2 periods, mirrors temp.py ACTION_PERIODS
        n_changes = sum(
            1 for r in rows
            if r["time_period"] in action_periods
            and (r["q_case_pack"] * data.CP.get((r["product_id"], r["warehouse_id"]), 1)
                 + r["r_residual_units"]) > 0
        )

        print(
            f"[OptimizationService] Done in {model_sol.solve_time_seconds:.1f}s | "
            f"obj={opt_cost:.2f} | baseline_zero={baseline:.2f} | "
            f"baseline_prop={prop_cost:.2f} | "
            f"savings_vs_zero={savings_pct:.1f}% | "
            f"savings_vs_prop={savings_pct_prop:.1f}% | "
            f"n_changes={n_changes}"
        )

        return OptimizationResult(
            solver_status=model_sol.solver_status,
            solve_time=model_sol.solve_time_seconds,
            objective_value=opt_cost,
            mip_gap=self.mip_gap,
            output=OptimizationOutput(results=rows),
            kpis=kpis,
            is_optimal=status_info["is_optimal"],
            is_feasible=status_info["is_feasible"],
            message=status_info["message"],
            baseline_cost=baseline,
            savings=savings,
            savings_pct=savings_pct,
            n_changes=n_changes,
            si_mean=si_mean,
            ss_below_count=ss_below,
            prop_cost=prop_cost,
            savings_vs_prop=savings_vs_prop,
            savings_pct_prop=savings_pct_prop,
        )

    # ------------------------------------------------------------------
    def _zero_kpis(self) -> Dict[str, float]:
        return {k: 0.0 for k in (
            "total_cost", "total_backorder", "total_overstock",
            "total_shortage", "total_penalty",
            "cost_backorder", "cost_overstock", "cost_shortage", "cost_penalty",
            "service_level", "capacity_utilization",
        )}

    def _calculate_kpis(
        self,
        results: list[Dict[str, Any]],
        data: OptimizationInput,
    ) -> Dict[str, float]:
        """Compute KPI summary from per-row results."""
        total_bo = total_o = total_s = 0.0
        cost_bo = cost_o = cost_s = cost_p = total_c = 0.0
        total_penalty = 0
        periods_ok = 0

        for r in results:
            i, j, t = r["product_id"], r["warehouse_id"], r["time_period"]
            bo = r["backorder_qty"]
            o  = r["overstock_qty"]
            s  = r["shortage_qty"]
            p  = int(r["penalty_flag"])
            cb = data.Cb.get((i, j, t), 0)
            co = data.Co.get((i, j, t), 0)
            cs = data.Cs.get((i, j, t), 0)
            cp = data.Cp.get((i, j, t), 0)
            total_bo += bo
            total_o  += o
            total_s  += s
            total_penalty += p
            cost_bo += cb * bo
            cost_o  += co * o
            cost_s  += cs * s
            cost_p  += cp * p
            total_c += cb * bo + co * o + cs * s + cp * p
            if bo == 0:
                periods_ok += 1

        service_level = (periods_ok / len(results) * 100) if results else 0.0
        total_cap = sum(data.CAP.values()) or 1
        total_used = sum(
            r["q_case_pack"] * data.CP.get((r["product_id"], r["warehouse_id"]), 1) + r["r_residual_units"]
            for r in results
        )
        cap_util = total_used / total_cap * 100

        return {
            "total_cost": total_c,
            "total_backorder": total_bo,
            "total_overstock": total_o,
            "total_shortage": total_s,
            "total_penalty": float(total_penalty),
            "cost_backorder": cost_bo,
            "cost_overstock": cost_o,
            "cost_shortage":  cost_s,
            "cost_penalty":   cost_p,
            "service_level": service_level,
            "capacity_utilization": cap_util,
        }

