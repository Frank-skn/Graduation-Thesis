"""
backend/domain/operational_baseline.py
========================================
Baseline "hiện trạng" (Greedy Operational Heuristic).

Mô phỏng cách doanh nghiệp ĐANG vận hành thực tế — KHÔNG phải "do-nothing":
  1. Cập nhật tồn kho theo từng giai đoạn.
  2. Điều chuyển ngang PLT từ kho dư sang kho thiếu (nhìn trước lead time).
  3. Phân bổ OA từ nguồn cung trung tâm theo mức thiếu hụt dự kiến.
  4. Tính tổng chi phí vận hành (tồn kho + phạt OA + phạt PLT + vận chuyển).

Đây là con số "hiện trạng" (Z_current) mà luận văn dùng để so sánh với MA
(mức cải thiện = (Z_current − Z_MA) / Z_current). Thuật toán do Hậu phát triển
(heuristic_baseline.py gốc); module này port lại phần solver, tái dùng Problem
và CSVDataLoader của ma_adapter để tránh trùng lặp loader.

LƯU Ý: KHÔNG đụng MA/GA/ALNS. Chỉ tính chi phí baseline tất định.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.domain.ma_adapter import (
    CSVDataLoader, apply_overrides_to_problem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(mapping: Dict, key: Any, default: float = 0.0) -> float:
    try:
        return float(mapping.get(key, default))
    except Exception:
        return float(default)


def _lt_oa(problem, wh: str) -> int:
    """
    Lấy OA lead-time cho warehouse wh.

    Problem của ma_adapter dùng LT_OA dạng Dict[wh, int] (model v6 per-warehouse),
    còn heuristic gốc của Hậu dùng LT_OA dạng int (đồng nhất). Hàm này xử lý cả 2.
    """
    lt = getattr(problem, "LT_OA", 0)
    if isinstance(lt, dict):
        return int(lt.get(wh, next(iter(lt.values()), 0)))
    return int(lt)


def _case_pack(problem, wh: str, t: int) -> int:
    cp = getattr(problem, "CP", 1)
    if isinstance(cp, dict):
        value = cp.get((wh, t)) or cp.get(wh) or cp.get(t) or 1
    else:
        value = cp
    return max(int(round(float(value))), 1)


def _floor_case(qty: float, cp: int) -> int:
    return max(0, int(qty // cp) * cp)


def _residual(qty: float, cp: int) -> float:
    return max(0.0, qty - math.floor(qty / cp) * cp)


# ---------------------------------------------------------------------------
# Greedy Operational Heuristic
# ---------------------------------------------------------------------------

class GreedyOperationalHeuristic:
    """
    Core Greedy Operational Heuristic (baseline hiện trạng).

    Port từ heuristic_baseline.py của Hậu, thích ứng với LT_OA per-warehouse.
    """

    def __init__(self, problem):
        self.p = problem
        self.warehouses = list(problem.warehouses)
        self.periods = list(problem.periods)
        self.max_t = max(self.periods)

        self.Q_oa: Dict[Tuple[str, int], float] = {}
        self.Q_plt: Dict[Tuple[str, str, int], float] = {}
        self.inventory: Dict[Tuple[str, int], float] = {}

    def solve(self) -> Dict[str, Any]:
        start_time = time.perf_counter()

        current_inventory = {
            wh: _safe(self.p.BI, wh, 0.0)
            for wh in self.warehouses
        }

        for t in self.periods:
            temp_inventory: Dict[str, float] = {}

            # 1. Cập nhật tồn kho trước PLT
            for wh in self.warehouses:
                temp_inventory[wh] = (
                    current_inventory.get(wh, 0.0)
                    + self._arrive_oa(wh, t)
                    + self._arrive_plt(wh, t)
                    + _safe(self.p.delta_I, (wh, t), 0.0)
                )

            # 2. Điều chuyển ngang PLT
            self._greedy_plt(t, temp_inventory)

            # 3. Lưu tồn kho cuối kỳ
            for wh in self.warehouses:
                self.inventory[(wh, t)] = temp_inventory[wh]

            current_inventory = temp_inventory

            # 4. Phân bổ OA cho kỳ t
            oa_plan = self._greedy_oa(t, current_inventory)
            for wh, qty in oa_plan.items():
                self.Q_oa[(wh, t)] = qty

        breakdown = self._evaluate()

        return {
            "objective_value": round(breakdown["total_cost"], 4),
            "runtime_seconds": round(time.perf_counter() - start_time, 4),
            "solver_status": "ok",
            "breakdown": breakdown,
            "Q_oa": self.Q_oa,
            "Q_plt": self.Q_plt,
            "inventory": self.inventory,
        }

    # ── Arrival ──────────────────────────────────────────────────────
    def _arrive_oa(self, wh: str, t: int) -> float:
        lt = _lt_oa(self.p, wh)
        order_t = t - lt
        if order_t < min(self.periods):
            return 0.0
        return float(self.Q_oa.get((wh, order_t), 0.0))

    def _arrive_plt(self, wh: str, t: int) -> float:
        total = 0.0
        for (donor, receiver, ship_t), qty in self.Q_plt.items():
            if receiver != wh:
                continue
            lt = int(self.p.LT_PLT.get((donor, receiver), 0))
            if ship_t + lt == t:
                total += qty
        return total

    # ── OA allocation ────────────────────────────────────────────────
    def _greedy_oa(self, t: int, current_inventory: Dict[str, float]) -> Dict[str, int]:
        capacity = int(round(_safe(self.p.CAP, t, 0.0)))
        if capacity <= 0:
            return {wh: 0 for wh in self.warehouses}

        priorities = self._oa_priorities(t, current_inventory)
        total_priority = sum(priorities.values())
        if total_priority <= 0:
            priorities = {wh: 1.0 for wh in self.warehouses}
            total_priority = float(len(self.warehouses))

        allocation = {
            wh: _floor_case(
                capacity * priorities[wh] / total_priority,
                _case_pack(self.p, wh, t),
            )
            for wh in self.warehouses
        }
        allocation = self._repair_capacity(allocation, capacity, priorities, t)
        return allocation

    def _oa_priorities(self, t: int, current_inventory: Dict[str, float]) -> Dict[str, float]:
        priorities: Dict[str, float] = {}
        for wh in self.warehouses:
            lt = _lt_oa(self.p, wh)
            target_t = min(t + lt, self.max_t)
            projected_inventory = self._project_inventory(
                wh=wh, current_t=t, target_t=target_t,
                current_inventory=current_inventory.get(wh, 0.0),
            )
            floor = _safe(self.p.L, (wh, target_t), 0.0)
            shortage_cost = _safe(self.p.Cs, (wh, target_t), 1.0)
            backorder_cost = _safe(self.p.Cb, (wh, target_t), 1.0)
            shortage_need = max(0.0, floor - projected_inventory)
            backorder_risk = max(0.0, -projected_inventory)
            priorities[wh] = max(
                shortage_need * shortage_cost + backorder_risk * backorder_cost, 0.0,
            )
        return priorities

    def _project_inventory(self, wh: str, current_t: int, target_t: int,
                           current_inventory: float) -> float:
        projected = float(current_inventory)
        lt_oa = _lt_oa(self.p, wh)
        for tau in range(current_t + 1, target_t + 1):
            projected += _safe(self.p.delta_I, (wh, tau), 0.0)
            order_t = tau - lt_oa
            if order_t in self.periods:
                projected += self.Q_oa.get((wh, order_t), 0.0)
            for (donor, receiver, ship_t), qty in self.Q_plt.items():
                if receiver != wh:
                    continue
                lt_plt = int(self.p.LT_PLT.get((donor, receiver), 0))
                if ship_t + lt_plt == tau:
                    projected += qty
        return projected

    def _repair_capacity(self, allocation: Dict[str, int], capacity: int,
                         priorities: Dict[str, float], t: int) -> Dict[str, int]:
        remain = capacity - sum(allocation.values())
        if remain <= 0:
            return allocation
        sorted_warehouses = sorted(
            self.warehouses, key=lambda wh: priorities.get(wh, 0.0), reverse=True,
        )
        changed = True
        while remain > 0 and changed:
            changed = False
            for wh in sorted_warehouses:
                if remain <= 0:
                    break
                cp = _case_pack(self.p, wh, t)
                if remain >= cp:
                    allocation[wh] += cp
                    remain -= cp
                    changed = True
        if remain > 0:
            allocation[sorted_warehouses[0]] += remain
        return allocation

    # ── PLT allocation ───────────────────────────────────────────────
    def _greedy_plt(self, t: int, inventory_now: Dict[str, float]) -> None:
        surplus = {
            wh: max(0.0, inventory_now.get(wh, 0.0) - _safe(self.p.L, (wh, t), 0.0))
            for wh in self.warehouses
        }
        surplus = {wh: qty for wh, qty in surplus.items() if qty > 0}
        if not surplus:
            return

        receiver_scores = self._plt_scores(t, inventory_now)
        receivers = sorted(
            [wh for wh, score in receiver_scores.items() if score > 0],
            key=lambda wh: receiver_scores[wh], reverse=True,
        )

        for receiver in receivers:
            if t not in self.p.PLT_periods.get(receiver, frozenset()):
                continue
            donors = sorted(
                surplus.keys(),
                key=lambda donor: (
                    -surplus.get(donor, 0.0),
                    self.p.dist.get((donor, receiver), 1e9),
                ),
            )
            for donor in donors:
                if donor == receiver:
                    continue
                available = surplus.get(donor, 0.0)
                if available <= 0:
                    continue
                if (donor, receiver) not in self.p.LT_PLT:
                    continue
                lt = int(self.p.LT_PLT[(donor, receiver)])
                arrival_t = t + lt
                if arrival_t > self.max_t:
                    continue
                projected_receiver = self._project_inventory(
                    wh=receiver, current_t=t, target_t=arrival_t,
                    current_inventory=inventory_now.get(receiver, 0.0),
                )
                need = max(0.0, _safe(self.p.L, (receiver, arrival_t), 0.0) - projected_receiver)
                if need <= 0:
                    continue
                transfer = _floor_case(
                    min(available, need), _case_pack(self.p, receiver, arrival_t),
                )
                if transfer <= 0:
                    continue
                key = (donor, receiver, t)
                self.Q_plt[key] = self.Q_plt.get(key, 0.0) + transfer
                inventory_now[donor] -= transfer
                surplus[donor] -= transfer
                if lt == 0:
                    inventory_now[receiver] += transfer
                if surplus[donor] <= 0:
                    break

    def _plt_scores(self, t: int, inventory_now: Dict[str, float]) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for receiver in self.warehouses:
            if t not in self.p.PLT_periods.get(receiver, frozenset()):
                scores[receiver] = 0.0
                continue
            best_score = 0.0
            for donor in self.warehouses:
                if donor == receiver:
                    continue
                if (donor, receiver) not in self.p.LT_PLT:
                    continue
                lt = int(self.p.LT_PLT[(donor, receiver)])
                arrival_t = t + lt
                if arrival_t > self.max_t:
                    continue
                projected = self._project_inventory(
                    wh=receiver, current_t=t, target_t=arrival_t,
                    current_inventory=inventory_now.get(receiver, 0.0),
                )
                need = max(0.0, _safe(self.p.L, (receiver, arrival_t), 0.0) - projected)
                shortage_cost = _safe(self.p.Cs, (receiver, arrival_t), 1.0)
                best_score = max(best_score, need * shortage_cost)
            scores[receiver] = best_score
        return scores

    # ── Objective ────────────────────────────────────────────────────
    def _evaluate(self) -> Dict[str, float]:
        p = self.p
        inventory_cost = 0.0
        oa_penalty_cost = 0.0
        plt_penalty_cost = 0.0
        transport_cost = 0.0

        for wh in self.warehouses:
            for t in self.periods:
                inv = self.inventory.get((wh, t), 0.0)
                floor = _safe(p.L, (wh, t), 0.0)
                ceiling = _safe(p.U, (wh, t), 0.0)
                overstock = max(0.0, inv - ceiling)
                shortage = max(0.0, floor - inv)
                backorder = max(0.0, -inv)
                inventory_cost += (
                    _safe(p.Co, (wh, t)) * overstock
                    + _safe(p.Cs, (wh, t)) * shortage
                    + _safe(p.Cb, (wh, t)) * backorder
                )

        for (wh, t), qty in self.Q_oa.items():
            if _residual(qty, _case_pack(p, wh, t)) > 1e-9:
                oa_penalty_cost += _safe(p.Cp, (wh, t))

        for (donor, receiver, t), qty in self.Q_plt.items():
            if qty <= 0:
                continue
            if _residual(qty, _case_pack(p, receiver, t)) > 1e-9:
                plt_penalty_cost += _safe(p.Cp_plt, (donor, receiver, t))
            transport_cost += p.dist.get((donor, receiver), 0.0) * float(p.TC)

        total_cost = inventory_cost + oa_penalty_cost + plt_penalty_cost + transport_cost
        return {
            "total_cost": total_cost,
            "inventory_cost": inventory_cost,
            "oa_penalty_cost": oa_penalty_cost,
            "plt_penalty_cost": plt_penalty_cost,
            "transport_cost": transport_cost,
        }


# ---------------------------------------------------------------------------
# Build Problem cho baseline — CHỈ trên các kho mà sản phẩm THỰC SỰ có mặt
# ---------------------------------------------------------------------------
# QUAN TRỌNG: khác build_problem của ma_adapter (dùng cho MA — luôn 6 kho).
# Baseline "hiện trạng" chỉ mô phỏng vận hành trên các kho mà SP xuất hiện trong
# inventory_flow (giống heuristic gốc của Hậu: warehouses = sorted(flow.keys())).
# Nếu thêm cả kho SP không có mặt (với tồn kho default) sẽ phát sinh chi phí ảo
# và làm baseline lệch cao hơn thực tế.

def _build_problem_operational(product_id: str, loader: CSVDataLoader):
    """Build MA Problem cho baseline, chỉ trên kho SP có mặt trong inventory_flow."""
    from ma.core.problem import Problem
    from backend.domain.ma_adapter import LT_OA_DEFAULT, WH_TO_STATE

    flow_df = loader.inv_flow[loader.inv_flow["product_id"] == product_id]
    if flow_df.empty:
        return None
    # Chỉ các kho SP thực sự có mặt (giống Hậu)
    warehouses = tuple(sorted(str(w) for w in flow_df["warehouse_id"].unique()))
    periods = tuple(loader.periods)

    cp_row = loader.packing[loader.packing["product_id"] == product_id]
    if cp_row.empty:
        return None
    CP = int(cp_row.iloc[0]["pack_multiple"])

    bi_df = loader.inv_begin[loader.inv_begin["product_id"] == product_id]
    BI = {wh: 0.0 for wh in warehouses}
    for _, row in bi_df.iterrows():
        wh = str(row["warehouse_id"])
        if wh in BI:
            BI[wh] = float(row["beginning_inventory"])

    delta_I, U, L = {}, {}, {}
    for _, row in flow_df.iterrows():
        wh = str(row["warehouse_id"]); t = int(row["time_period"])
        delta_I[(wh, t)] = float(row["inventory_fluctuation"])
        U[(wh, t)] = float(row["inventory_ceiling"])
        L[(wh, t)] = float(row["inventory_floor"])
    for wh in warehouses:
        for t in periods:
            delta_I.setdefault((wh, t), 0.0)
            U.setdefault((wh, t), 1e6)
            L.setdefault((wh, t), 0.0)

    cap_df = loader.capacity[loader.capacity["product_id"] == product_id]
    if cap_df.empty:
        return None
    CAP = {t: 9999.0 for t in periods}
    for _, row in cap_df.iterrows():
        CAP[int(row["time_period"])] = float(row["capacity"])

    cost_df = loader.unit_cost[loader.unit_cost["product_id"] == product_id]
    Co, Cs, Cb, Cp = {}, {}, {}, {}
    for _, row in cost_df.iterrows():
        wh = str(row["warehouse_id"]); t = int(row["time_period"])
        Co[(wh, t)] = float(row["overstock_cost"])
        Cs[(wh, t)] = float(row["shortage_cost"])
        Cb[(wh, t)] = float(row["backlog_cost"])
        Cp[(wh, t)] = float(row["penalty_cost"])
    for wh in warehouses:
        for t in periods:
            Co.setdefault((wh, t), 0.1)
            Cs.setdefault((wh, t), 0.5)
            Cb.setdefault((wh, t), 1500.0)
            Cp.setdefault((wh, t), 2000.0)

    LT_OA = {wh: loader.lt_oa_per_wh.get(wh, LT_OA_DEFAULT) for wh in warehouses}

    wh_num = {str(i + 1): f"WH0{i+1}" for i in range(6)}
    LT_PLT = {}
    for _, row in loader.plt_lead.iterrows():
        frm = wh_num.get(str(int(row["from_warehouse_id"])))
        to = wh_num.get(str(int(row["to_warehouse_id"])))
        if frm in warehouses and to in warehouses:
            LT_PLT[(frm, to)] = int(row["lead_time_weeks"])

    PLT_periods = {
        wh: frozenset(t for t in periods if t <= LT_OA[wh] - 1) for wh in warehouses
    }

    dist = {}
    dm = loader.distance_matrix
    for wi in warehouses:
        for wj in warehouses:
            if wi == wj:
                continue
            si, sj = WH_TO_STATE.get(wi), WH_TO_STATE.get(wj)
            if si and sj and si in dm.index and sj in dm.columns:
                dist[(wi, wj)] = float(dm.loc[si, sj])

    Cp_plt = {}
    for (i, j) in LT_PLT:
        for t in periods:
            Cp_plt[(i, j, t)] = Cp.get((j, t), 0.0)

    return Problem(
        product=product_id, warehouses=warehouses, periods=periods,
        LT_OA=LT_OA, LT_PLT=LT_PLT, PLT_periods=PLT_periods,
        BI=BI, delta_I=delta_I, U=U, L=L, CAP=CAP, CP=CP, TC=loader.TC,
        dist=dist, Co=Co, Cs=Cs, Cb=Cb, Cp=Cp, Cp_plt=Cp_plt,
    )


# ---------------------------------------------------------------------------
# Public API — tính baseline hiện trạng trên toàn bộ (hoặc tập) sản phẩm
# ---------------------------------------------------------------------------

def compute_operational_baseline_from_csv(
    loader: CSVDataLoader,
    overrides: Optional[Dict] = None,
    product_ids: Optional[List[str]] = None,
) -> float:
    """
    Tổng chi phí baseline "hiện trạng" (Greedy Operational Heuristic) trên
    tập sản phẩm — dùng làm mốc so sánh cho MA (mức cải thiện của luận văn).

    overrides:   factor What-if/Sensitivity, áp cho baseline trên cùng kịch bản
                 (đồng bộ với MA) qua apply_overrides_to_problem.
    product_ids: giới hạn baseline đúng tập SP mà MA đã giải (test/product_limit).
                 None = toàn bộ sản phẩm active.

    Tất định: cùng data + tham số → cùng kết quả. Khớp file gốc Hậu.
    """
    products = product_ids if product_ids else loader.get_active_products()
    total = 0.0
    for pid in products:
        problem = _build_problem_operational(pid, loader)
        if problem is None:
            continue
        if overrides:
            problem = apply_overrides_to_problem(problem, overrides)
        sol = GreedyOperationalHeuristic(problem).solve()
        total += float(sol["objective_value"])
    return total
