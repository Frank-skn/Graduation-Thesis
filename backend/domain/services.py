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
from backend.domain.greedy_heuristic import compute_greedy_baseline_cost


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
    # Inventory cost extracted from MA rows (for fair comparison with baseline/prop)
    ma_inv_cost: float = 0.0
    # PLT transfer rows (product_id, from_warehouse_id, to_warehouse_id, time_period, qty)
    plt_rows: list = None


def _baseline_cost(data: OptimizationInput) -> float:
    """
    Baseline = Greedy Operational Heuristic cost.
    
    Mô phỏng cách vận hành thực tế:
    1. Cập nhật tồn kho theo cầu (DI)
    2. Điều chuyển PLT từ warehouse dư sang thiếu (nếu có)
    3. Phân bổ OA từ nguồn cung theo mức thiếu hụt dự kiến
    4. Tính chi phí: Co×overstock + Cs×shortage + Cb×backorder
    
    Khác biệt với do-nothing cũ:
    - Có OA allocation thông minh (không do-nothing)
    - Có khả năng PLT transfer
    - Chính xác hơn với thực tế vận hành
    """
    return compute_greedy_baseline_cost(data, lt_oa=8, tc=1.2)


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
        scenario_overrides: dict | None = None,
    ) -> OptimizationResult:
        """
        Execute Hybrid GA-ALNS on DSS real data (or test cases fallback).

        scenario_overrides: dict factor cho What-if/Sensitivity (ví dụ {"DI": 1.2}).
            Áp lên input của Problem, không đụng thuật toán MA.
        """
        print(f"[OptimizationService] Running MA (Hybrid GA-ALNS) solver …")

        # --- Step 1: run MA solver ---
        # Pass the per-product time limit (seconds) from the API/B0 form so it
        # actually caps each product's GA runtime (otherwise config.json's
        # time_limit_seconds is used, which is meant only as a safety ceiling).
        ma = MASolver(time_limit_s=float(self.time_limit) if self.time_limit else None)
        if data_dir:
            ma_result = ma.solve_from_dss_data(
                data_dir,
                product_ids=product_ids,
                scenario_overrides=scenario_overrides,
            )
        else:
            ma_result = ma.solve_all()

        rows     = ma_result["rows"]
        plt_rows = ma_result.get("plt_rows", [])
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
                plt_rows=[],
            )

        # --- Step 2: KPIs + inventory cost breakdown từ CSV ---
        if data_dir:
            from backend.domain.ma_adapter import CSVDataLoader
            from backend.domain.operational_baseline import (
                compute_operational_baseline_from_csv,
            )
            _loader   = CSVDataLoader(data_dir)
            # Baseline "hiện trạng" (Greedy Operational Heuristic — có PLT, đầy đủ
            # thành phần chi phí như hàm mục tiêu). Đây là Z_current mà luận văn
            # dùng để so sánh mức cải thiện với MA. Giới hạn cùng tập SP với MA
            # để so sánh apples-to-apples trong test/product_limit mode.
            baseline  = compute_operational_baseline_from_csv(
                _loader, overrides=scenario_overrides, product_ids=product_ids
            )
            # Proportional allocation baseline is DEPRECATED — không còn dùng.
            prop_cost = 0.0
            # Cơ cấu chi phí từ MA rows — dùng cho breakdown hiển thị theo thành
            # phần (backorder/overstock/shortage/penalty/transport). ma_inv_cost
            # (Co/Cs/Cb thuần) KHÔNG dùng để tính savings nữa.
            ma_inv_cost, cost_breakdown = self._compute_inv_cost_from_rows(rows, _loader, plt_rows)
        else:
            _loader       = None
            baseline      = _baseline_cost(data)
            prop_cost     = 0.0  # deprecated, see note above
            ma_inv_cost   = opt_cost
            cost_breakdown = {}

        # Tổng năng lực cung ứng (CAP) để tính mức sử dụng năng lực đúng khái niệm
        total_cap = 0.0
        if _loader is not None:
            try:
                cap_df = _loader.capacity
                if product_ids:
                    cap_df = cap_df[cap_df["product_id"].isin(product_ids)]
                total_cap = float(cap_df["capacity"].sum())
            except Exception:
                total_cap = 0.0

        kpis = self._calculate_kpis_from_rows(rows, opt_cost=opt_cost, cost_breakdown=cost_breakdown, total_capacity=total_cap)

        # Mức cải thiện so với hiện trạng (khớp luận văn, công thức 2.1):
        #   Improvement = (Z_current − Z_MA) / Z_current
        # Cả baseline (hiện trạng) và opt_cost (MA fitness) đều là TỔNG chi phí
        # đầy đủ (Co/Cs/Cb + phạt OA + phạt PLT + vận chuyển) → so sánh cùng bản chất.
        savings          = max(0.0, baseline - opt_cost)
        savings_pct      = (savings / baseline * 100) if baseline > 0 else 0.0
        savings_vs_prop  = max(0.0, prop_cost - opt_cost)
        savings_pct_prop = (savings_vs_prop / prop_cost * 100) if prop_cost > 0 else 0.0

        # --- Step 4: SI / SS metrics ---
        # SI (Safety Index) = tồn kho thực tế / ngưỡng sàn L thực tế. SI >= 1: an toàn.
        # (Trước đây si_values chỉ lưu max(0, inv) — tồn kho trung bình, KHÔNG phải
        # chỉ số an toàn — đã sửa để chia đúng cho L, khớp công thức dùng ở
        # GET /results/{run_id}/si-ss.)
        L_map: dict = {}
        if _loader is not None:
            for _, _row in _loader.inv_flow.iterrows():
                _key = (str(_row["product_id"]), str(_row["warehouse_id"]), int(_row["time_period"]))
                L_map[_key] = float(_row["inventory_floor"])
        else:
            L_map = data.L

        si_values: list = []
        ss_below  = 0
        for r in rows:
            inv = r["net_inventory"]
            sh  = r["shortage_qty"]
            l_val = float(L_map.get((r["product_id"], r["warehouse_id"], r["time_period"]), 0.0))
            si_values.append(1.0 if l_val <= 0 else inv / l_val)
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
            ma_inv_cost      = ma_inv_cost,
            plt_rows         = plt_rows,
        )

    # ------------------------------------------------------------------
    def _compute_inv_cost_from_rows(self, rows: list, loader, plt_rows: list = None) -> tuple:
        """
        Tính cơ cấu chi phí từ MA rows để HIỂN THỊ theo thành phần.
        Trả về (total_inv_cost, cost_breakdown_dict).

        - cost_backorder/overstock/shortage: từ Co/Cs/Cb × số lượng.
        - cost_penalty: phạt vi phạm quy cách đóng gói (OA + PLT) — mỗi dòng có
          phần lẻ (penalty_flag) hoặc PLT lẻ bị tính 1 lần Cp.
        - cost_transport: chi phí điều chuyển ngang PLT (khoảng cách × TC).
        total_inv (Co/Cs/Cb thuần) vẫn dùng để so sánh với baseline cùng đơn vị.
        """
        # Index unit cost từ loader
        co_map: Dict = {}
        cs_map: Dict = {}
        cb_map: Dict = {}
        cp_map: Dict = {}
        for _, row in loader.unit_cost.iterrows():
            key = (str(row["warehouse_id"]), int(row["time_period"]))
            co_map[key] = float(row["overstock_cost"])
            cs_map[key] = float(row["shortage_cost"])
            cb_map[key] = float(row["backlog_cost"])
            cp_map[key] = float(row.get("penalty_cost", 2000.0))

        # Case-pack (pack_multiple) theo sản phẩm — để phát hiện PLT lẻ
        cp_pack_map: Dict = {}
        try:
            for _, row in loader.packing.iterrows():
                cp_pack_map[str(row["product_id"])] = int(row["pack_multiple"])
        except Exception:
            cp_pack_map = {}

        total_inv = 0.0
        cost_bo = cost_ov = cost_sh = cost_pen = 0.0

        for r in rows:
            key = (r["warehouse_id"], r["time_period"])
            bo = float(r.get("backorder_qty", 0))
            ov = float(r.get("overstock_qty", 0))
            sh = float(r.get("shortage_qty", 0))
            cost_bo += cb_map.get(key, 1500.0) * bo
            cost_ov += co_map.get(key, 0.1)   * ov
            cost_sh += cs_map.get(key, 0.5)   * sh
            # Phạt đóng gói OA: mỗi dòng có phần lẻ (penalty_flag) chịu 1 lần Cp
            if r.get("penalty_flag"):
                cost_pen += cp_map.get(key, 2000.0)

        # Chi phí điều chuyển ngang PLT (transport = khoảng cách × TC).
        # Phạt PLT lẻ (khi qty không chia hết case-pack kho nhận) gộp vào cost_pen
        # vì cùng bản chất "phạt vi phạm quy cách đóng gói".
        cost_transport = 0.0
        if plt_rows:
            try:
                from backend.domain.ma_adapter import WH_TO_STATE
                dm = loader.distance_matrix
                tc = float(loader.TC)
            except Exception:
                dm, tc = None, 1.2
            # Case-pack theo product/warehouse để phát hiện PLT lẻ
            for pr in plt_rows:
                qty = float(pr.get("qty", 0))
                if qty <= 0:
                    continue
                frm = str(pr.get("from_warehouse_id"))
                to  = str(pr.get("to_warehouse_id"))
                if dm is not None:
                    si = WH_TO_STATE.get(frm)
                    sj = WH_TO_STATE.get(to)
                    if si and sj and si in dm.index and sj in dm.columns:
                        cost_transport += float(dm.loc[si, sj]) * tc
                # Phạt PLT lẻ: dùng penalty_cost của kho nhận tại kỳ đó
                t_pr = int(pr.get("time_period", 0))
                cp_pack = cp_pack_map.get(str(pr.get("product_id"))) if cp_pack_map else None
                if cp_pack and cp_pack > 0 and (int(round(qty)) % cp_pack) > 0:
                    cost_pen += cp_map.get((to, t_pr), 2000.0)

        total_inv = cost_bo + cost_ov + cost_sh
        breakdown = {
            "cost_backorder": cost_bo,
            "cost_overstock": cost_ov,
            "cost_shortage" : cost_sh,
            "cost_penalty"  : cost_pen,
            "cost_transport": cost_transport,
        }
        return total_inv, breakdown

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
        opt_cost: float = 0.0,
        cost_breakdown: Dict = {},
        total_capacity: float = 0.0,
    ) -> Dict[str, float]:
        """Compute KPI summary from MA row dicts."""
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
        # Mức sử dụng năng lực = tổng lượng đã phân bổ (OA) / tổng năng lực cung ứng (CAP).
        # Trước đây dùng mẫu số |net_inventory| (sai khái niệm) → đã sửa dùng CAP.
        total_used = sum(
            r.get("q_case_pack", 0) + r.get("r_residual_units", 0)
            for r in results
        )
        if total_capacity and total_capacity > 0:
            cap_util = min(100.0, total_used / total_capacity * 100)
        else:
            cap_util = 0.0

        return {
            "total_cost"          : opt_cost,
            "total_backorder"     : total_bo,
            "total_overstock"     : total_o,
            "total_shortage"      : total_s,
            "total_penalty"       : float(total_penalty),
            "cost_backorder"      : cost_breakdown.get("cost_backorder", 0.0),
            "cost_overstock"      : cost_breakdown.get("cost_overstock", 0.0),
            "cost_shortage"       : cost_breakdown.get("cost_shortage",  0.0),
            "cost_penalty"        : cost_breakdown.get("cost_penalty",   0.0),
            "cost_transport"      : cost_breakdown.get("cost_transport", 0.0),
            "service_level"       : service_level,
            "capacity_utilization": cap_util,
        }

