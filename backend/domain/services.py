"""
Optimization service orchestration — Hybrid GA-ALNS (MA) solver.
Follows Single Responsibility Principle.

MA replaces the previous PuLP/CBC MILP solver.
At this integration phase, MA runs on bundled test data cases.
Real-data CSV adapter will be wired in a later phase.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

from backend.schemas.optimization import OptimizationInput, OptimizationOutput
from backend.domain.ma_solver import MASolver


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
    """Service for executing SS-MB-SMI optimisation via Hybrid GA-ALNS (MA)."""

    def __init__(
        self,
        solver: str = "ma",
        time_limit: int = 300,
        mip_gap: float = 0.01,
    ):
        self.solver     = solver
        self.time_limit = time_limit
        self.mip_gap    = mip_gap

    # ------------------------------------------------------------------
    def solve(
        self,
        data: OptimizationInput,
        data_dir: str | None = None,
        product_ids: list | None = None,
    ) -> OptimizationResult:
        """
        Execute Hybrid GA-ALNS on DSS real data (or test cases fallback).
        """
        print(f"[OptimizationService] Running MA (Hybrid GA-ALNS) solver …")

        # --- Step 1: run MA solver ---
        ma = MASolver()
        if data_dir:
            ma_result = ma.solve_from_dss_data(data_dir, product_ids=product_ids)
        else:
            ma_result = ma.solve_all()

        rows     = ma_result["rows"]
        opt_cost = ma_result["fitness"]
        elapsed  = ma_result["elapsed_s"]
        status   = ma_result["status"]

        if status == "error" or not rows:
            return OptimizationResult(
                solver_status="error",
                solve_time=elapsed,
                objective_value=0.0,
                mip_gap=self.mip_gap,
                output=OptimizationOutput(results=[]),
                kpis=self._zero_kpis(),
                is_optimal=False,
                is_feasible=False,
                message="MA solver failed on all cases. Check logs for details.",
            )

        # --- Step 2: KPIs from MA rows (using data costs where available) ---
        kpis = self._calculate_kpis_from_rows(rows)

        # --- Step 3: baseline & savings from OptimizationInput data ---
        baseline  = _baseline_cost(data)
        prop_cost = _proportional_allocation_cost(data)
        savings   = max(0.0, baseline - opt_cost)
        savings_pct      = (savings / baseline * 100) if baseline > 0 else 0.0
        savings_vs_prop  = max(0.0, prop_cost - opt_cost)
        savings_pct_prop = (savings_vs_prop / prop_cost * 100) if prop_cost > 0 else 0.0

        # --- Step 4: SI / SS metrics ---
        si_values: list = []
        ss_below  = 0
        for r in rows:
            inv = r["net_inventory"]
            sh  = r["shortage_qty"]
            si_values.append(max(0.0, inv))
            if sh > 0:
                ss_below += 1

        si_mean = sum(si_values) / len(si_values) if si_values else 0.0

        # n_changes: rows with non-zero allocation in first 2 periods
        action_periods = {1, 2}
        n_changes = sum(
            1 for r in rows
            if r["time_period"] in action_periods
            and (r["q_case_pack"] + r["r_residual_units"]) > 0
        )

        solver_status = "optimal" if status == "ok" else "feasible"
        print(
            f"[OptimizationService] MA done in {elapsed:.1f}s | "
            f"fitness={opt_cost:.2f} | status={status} | "
            f"n_cases={len(ma_result['details'])} | n_changes={n_changes}"
        )

        return OptimizationResult(
            solver_status    = solver_status,
            solve_time       = elapsed,
            objective_value  = opt_cost,
            mip_gap          = 0.0,
            output           = OptimizationOutput(results=rows),
            kpis             = kpis,
            is_optimal       = (status == "ok"),
            is_feasible      = True,
            message          = f"MA completed ({status}): {len(rows)} rows from {len(ma_result['details'])} cases",
            baseline_cost    = baseline,
            savings          = savings,
            savings_pct      = savings_pct,
            n_changes        = n_changes,
            si_mean          = si_mean,
            ss_below_count   = ss_below,
            prop_cost        = prop_cost,
            savings_vs_prop  = savings_vs_prop,
            savings_pct_prop = savings_pct_prop,
        )

    # ------------------------------------------------------------------
    def _zero_kpis(self) -> Dict[str, float]:
        return {k: 0.0 for k in (
            "total_cost", "total_backorder", "total_overstock",
            "total_shortage", "total_penalty",
            "cost_backorder", "cost_overstock", "cost_shortage", "cost_penalty",
            "service_level", "capacity_utilization",
        )}

    def _calculate_kpis_from_rows(
        self,
        results: list,
    ) -> Dict[str, float]:
        """Compute KPI summary from MA row dicts (no external cost data needed)."""
        total_bo = total_o = total_s = 0.0
        total_penalty = 0
        periods_ok = 0

        for r in results:
            bo = float(r.get("backorder_qty", 0))
            o  = float(r.get("overstock_qty", 0))
            s  = float(r.get("shortage_qty", 0))
            p  = int(bool(r.get("penalty_flag", False)))
            total_bo      += bo
            total_o       += o
            total_s       += s
            total_penalty += p
            if bo == 0:
                periods_ok += 1

        service_level = (periods_ok / len(results) * 100) if results else 0.0
        total_used = sum(
            r.get("q_case_pack", 0) + r.get("r_residual_units", 0)
            for r in results
        )
        # capacity_utilization: ratio of allocated units vs total inventory processed
        total_inv = sum(abs(r.get("net_inventory", 0)) for r in results) or 1.0
        cap_util  = min(100.0, total_used / total_inv * 100)

        return {
            "total_cost"          : 0.0,   # MA fitness covers all costs; set 0 to avoid double-count
            "total_backorder"     : total_bo,
            "total_overstock"     : total_o,
            "total_shortage"      : total_s,
            "total_penalty"       : float(total_penalty),
            "cost_backorder"      : 0.0,
            "cost_overstock"      : 0.0,
            "cost_shortage"       : 0.0,
            "cost_penalty"        : 0.0,
            "service_level"       : service_level,
            "capacity_utilization": cap_util,
        }

