from __future__ import annotations

import argparse
import csv
import logging
import math
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("manual_heuristic")


# ============================================================
# Internal imports
# ============================================================

from model.core.problem import Problem


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "sample_100_fixed"
OUTPUT_DIR = BASE_DIR / "output_manual_baseline"


# ============================================================
# Helpers
# ============================================================

def _safe(mapping: Dict, key: Any, default: float = 0.0) -> float:
    try:
        return float(mapping.get(key, default))
    except Exception:
        return float(default)


def _case_pack(problem, wh: str, t: int) -> int:
    if hasattr(problem, "case_pack"):
        return problem.case_pack(wh, t)
    cp = getattr(problem, "CP", 1)

    if isinstance(cp, dict):
        value = cp.get((wh, t)) or cp.get(wh) or cp.get(t) or 1
    else:
        value = cp

    return max(int(round(float(value))), 1)


def _floor_case(qty: float, cp: int) -> int:
    """
    Làm tròn xuống theo case-pack.
    """
    return max(0, int(qty // cp) * cp)


def _residual(qty: float, cp: int) -> float:
    return max(0.0, qty - math.floor(qty / cp) * cp)


# ============================================================
# Manual Planner Heuristic
# ============================================================

class ManualPlannerHeuristic:
    """
    Heuristic mô phỏng planner thủ công thực tế hơn.

    Khác với Greedy Operational Heuristic mạnh:
    - Không dự báo tồn kho nhiều tuần bằng _project_inventory.
    - Không dùng cost để tính priority.
    - PLT chỉ dựa trên thiếu/dư hiện tại.
    - OA phân bổ theo mức thiếu hiện tại.
    - Vẫn tôn trọng case-pack và repair capacity.
    """

    def __init__(self, problem: Problem):
        self.p = problem
        self.warehouses = list(problem.warehouses)
        self.periods = list(problem.periods)

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

            # 1. Cập nhật tồn kho hiện tại
            for wh in self.warehouses:
                temp_inventory[wh] = (
                    current_inventory.get(wh, 0.0)
                    + self._arrive_oa(wh, t)
                    + self._arrive_plt(wh, t)
                    + _safe(self.p.delta_I, (wh, t), 0.0)
                )

            # 2. PLT theo rule thủ công: thiếu hiện tại nhận từ dư hiện tại
            self._manual_plt(t, temp_inventory)

            # 3. Lưu tồn kho cuối kỳ sau PLT gửi đi
            for wh in self.warehouses:
                self.inventory[(wh, t)] = temp_inventory[wh]

            current_inventory = temp_inventory

            # 4. OA theo rule thủ công: chia theo thiếu hiện tại
            oa_plan = self._manual_oa(t, current_inventory)
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

    # ------------------------------------------------------------
    # Arrival
    # ------------------------------------------------------------

    def _arrive_oa(self, wh: str, t: int) -> float:
        """
        OA đặt tại kỳ s đến tại s + LT_OA - 1.
        Quy ước này giữ giống runner hiện tại.
        """
        lt_oa_field = getattr(self.p, "LT_OA", 0)
        if isinstance(lt_oa_field, dict):
            lt = int(lt_oa_field.get(wh, 8))
        else:
            lt = int(lt_oa_field)
        order_t = t - lt + 1

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

    # ------------------------------------------------------------
    # Manual OA
    # ------------------------------------------------------------

    def _manual_oa(self, t: int, current_inventory: Dict[str, float]) -> Dict[str, int]:
        """
        Phân bổ OA theo thiếu hụt hiện tại.

        Priority:
        - Nếu warehouse đang dưới inventory floor thì ưu tiên theo mức thiếu.
        - Nếu không có warehouse nào thiếu, chia theo gap tới inventory ceiling.
        - Nếu vẫn không có gap, chia đều.
        """
        capacity = int(round(_safe(self.p.CAP, t, 0.0)))

        if capacity <= 0:
            return {wh: 0 for wh in self.warehouses}

        priorities = self._current_oa_priorities(t, current_inventory)
        total_priority = sum(priorities.values())

        if total_priority <= 0:
            priorities = {wh: 1.0 for wh in self.warehouses}
            total_priority = float(len(self.warehouses))

        allocation = {}

        for wh in self.warehouses:
            cp = _case_pack(self.p, wh, t)
            raw_qty = capacity * priorities[wh] / total_priority
            allocation[wh] = _floor_case(raw_qty, cp)

        allocation = self._repair_capacity(
            allocation=allocation,
            capacity=capacity,
            priorities=priorities,
            t=t,
        )

        return allocation

    def _current_oa_priorities(
        self,
        t: int,
        current_inventory: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Priority thủ công, chỉ nhìn tồn kho hiện tại.
        Không dùng cost, không look-ahead.
        """
        priorities: Dict[str, float] = {}

        # Ưu tiên 1: thiếu dưới floor hiện tại
        for wh in self.warehouses:
            inv = current_inventory.get(wh, 0.0)
            floor = _safe(self.p.L, (wh, t), 0.0)

            shortage_now = max(0.0, floor - inv)
            backorder_now = max(0.0, -inv)

            priorities[wh] = shortage_now + backorder_now

        if sum(priorities.values()) > 0:
            return priorities

        # Ưu tiên 2: nếu không thiếu, ưu tiên warehouse còn khoảng trống tới ceiling
        for wh in self.warehouses:
            inv = current_inventory.get(wh, 0.0)
            ceiling = _safe(self.p.U, (wh, t), 0.0)

            priorities[wh] = max(0.0, ceiling - inv)

        if sum(priorities.values()) > 0:
            return priorities

        # Ưu tiên 3: chia đều
        return {wh: 1.0 for wh in self.warehouses}

    def _repair_capacity(
        self,
        allocation: Dict[str, int],
        capacity: int,
        priorities: Dict[str, float],
        t: int,
    ) -> Dict[str, int]:
        """
        Repair tổng OA để tổng phân bổ bằng capacity.

        Sau khi floor theo case-pack, tổng allocation thường nhỏ hơn capacity.
        Phần còn lại được thêm theo priority.
        """
        remain = capacity - sum(allocation.values())

        if remain <= 0:
            return allocation

        sorted_warehouses = sorted(
            self.warehouses,
            key=lambda wh: priorities.get(wh, 0.0),
            reverse=True,
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

        # Phần dư cuối cùng nhỏ hơn case-pack vẫn phải phân bổ để đủ capacity.
        # Dòng này có thể tạo OA residual và phát sinh penalty, giống thực tế khi capacity không chia hết case-pack.
        if remain > 0:
            allocation[sorted_warehouses[0]] += remain

        return allocation

    # ------------------------------------------------------------
    # Manual PLT
    # ------------------------------------------------------------

    def _manual_plt(self, t: int, inventory_now: Dict[str, float]) -> None:
        """
        PLT thủ công:
        - Chỉ xét shortage hiện tại.
        - Chỉ lấy từ warehouse đang dư hiện tại.
        - Không dự báo arrival_t.
        - Donor ưu tiên dư nhiều và gần hơn.
        """
        surplus = {}
        need = {}

        for wh in self.warehouses:
            floor = _safe(self.p.L, (wh, t), 0.0)
            inv = inventory_now.get(wh, 0.0)

            surplus_qty = max(0.0, inv - floor)
            need_qty = max(0.0, floor - inv)

            if surplus_qty > 0:
                surplus[wh] = surplus_qty

            if need_qty > 0:
                need[wh] = need_qty

        if not surplus or not need:
            return

        receivers = sorted(
            need.keys(),
            key=lambda wh: need[wh],
            reverse=True,
        )

        for receiver in receivers:
            if t not in self.p.PLT_periods.get(receiver, frozenset()):
                continue

            remaining_need = need.get(receiver, 0.0)

            if remaining_need <= 0:
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

                if available <= 0 or remaining_need <= 0:
                    continue

                if (donor, receiver) not in self.p.LT_PLT:
                    continue

                lt = int(self.p.LT_PLT[(donor, receiver)])
                arrival_t = t + lt

                if arrival_t > max(self.periods):
                    continue

                cp = _case_pack(self.p, receiver, t)
                transfer = _floor_case(
                    min(available, remaining_need),
                    cp,
                )

                if transfer <= 0:
                    continue

                key = (donor, receiver, t)
                self.Q_plt[key] = self.Q_plt.get(key, 0.0) + transfer

                # Donor mất hàng ngay khi gửi
                inventory_now[donor] -= transfer
                surplus[donor] -= transfer

                # Receiver chỉ nhận ngay nếu lead time = 0
                if lt == 0:
                    inventory_now[receiver] += transfer

                # Dù chưa nhận ngay, planner đã đặt chuyển để xử lý nhu cầu hiện tại.
                remaining_need -= transfer
                need[receiver] = remaining_need

                if surplus[donor] <= 0:
                    surplus[donor] = 0.0

                if remaining_need <= 0:
                    break

    # ------------------------------------------------------------
    # Objective
    # ------------------------------------------------------------

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
            cp = _case_pack(p, wh, t)
            if _residual(qty, cp) > 1e-9:
                oa_penalty_cost += _safe(p.Cp, (wh, t), 0.0)

        for (donor, receiver, t), qty in self.Q_plt.items():
            if qty <= 0:
                continue

            cp = _case_pack(p, receiver, t)

            if _residual(qty, cp) > 1e-9:
                plt_penalty_cost += _safe(p.Cp_plt, (donor, receiver, t), 0.0)

            transport_cost += p.dist.get((donor, receiver), 0.0) * float(p.TC)

        total_cost = (
            inventory_cost
            + oa_penalty_cost
            + plt_penalty_cost
            + transport_cost
        )

        return {
            "total_cost": total_cost,
            "inventory_cost": inventory_cost,
            "oa_penalty_cost": oa_penalty_cost,
            "plt_penalty_cost": plt_penalty_cost,
            "transport_cost": transport_cost,
        }


# ============================================================
# Solution wrapper
# ============================================================

class HeuristicSolutionWrapper:
    def __init__(self, problem: Problem, sol_dict: Dict[str, Any]):
        self.I = sol_dict["inventory"]
        self.Q_OA = sol_dict["Q_oa"]
        self.Q_PLT = sol_dict["Q_plt"]
        self.fitness = sol_dict["objective_value"]

        self.r_OA = {}
        for wh in problem.warehouses:
            for t in problem.periods:
                qty = self.Q_OA.get((wh, t), 0.0)
                cp = _case_pack(problem, wh, t)
                self.r_OA[(wh, t)] = 1 if _residual(qty, cp) > 1e-9 else 0


# ============================================================
# Data loaders
# ============================================================

def load_inventory_flow(n: int = 999999) -> Tuple[List[str], Dict]:
    path = DATA_DIR / "inventory_flow.csv"

    product_order: List[str] = []
    flow: Dict[str, Dict[str, Dict[int, Dict]]] = defaultdict(lambda: defaultdict(dict))

    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            pid = row["product_id"]
            wh = row["warehouse_id"]
            t = int(row["time_period"])

            if pid not in product_order:
                if len(product_order) >= n:
                    continue
                product_order.append(pid)

            if pid in product_order:
                flow[pid][wh][t] = {
                    "delta_I": float(row["inventory_fluctuation"]),
                    "U": float(row["inventory_ceiling"]),
                    "L": float(row["inventory_floor"]),
                }

    return product_order, flow


def load_inventory_begin() -> Dict[str, Dict[str, float]]:
    bi: Dict[str, Dict[str, float]] = defaultdict(dict)

    with (DATA_DIR / "inventory_begin.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            bi[row["product_id"]][row["warehouse_id"]] = float(row["beginning_inventory"])

    return bi


def load_unit_costs() -> Dict[str, Dict[str, Dict[int, Dict]]]:
    costs: Dict = defaultdict(lambda: defaultdict(dict))

    with (DATA_DIR / "unit_cost.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = row["product_id"]
            wh = row["warehouse_id"]
            t = int(row["time_period"])

            costs[pid][wh][t] = {
                "Co": float(row["overstock_cost"]),
                "Cs": float(row["shortage_cost"]),
                "Cb": float(row["backlog_cost"]),
                "Cp": float(row["penalty_cost"]),
            }

    return costs


def load_vendor_capacity() -> Dict[str, Dict[int, float]]:
    cap: Dict[str, Dict[int, float]] = defaultdict(dict)

    with (DATA_DIR / "vendor_capacity.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cap[row["product_id"]][int(row["time_period"])] = float(row["capacity"])

    return cap


def load_packing_details() -> Dict[str, int]:
    cp: Dict[str, int] = {}

    with (DATA_DIR / "packing_details.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cp[row["product_id"]] = int(row["pack_multiple"])

    return cp


def load_oa_lead_times() -> Dict[str, int]:
    path = DATA_DIR / "oa_lead_time.csv"
    lt: Dict[str, int] = {}
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            wh = _format_wh(row["warehouse_id"])
            lt[wh] = int(row["week_lead_time"])
    return lt


def _format_wh(val: str) -> str:
    val = val.strip()

    if val.startswith("WH"):
        return val

    try:
        return f"WH{int(val):02d}"
    except ValueError:
        return val


def load_plt_lead_times() -> Dict[Tuple[str, str], int]:
    lt: Dict[Tuple[str, str], int] = {}

    with (DATA_DIR / "plt_lead_time.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            frm = _format_wh(row["from_warehouse_id"])
            to = _format_wh(row["to_warehouse_id"])
            lt[(frm, to)] = int(row["lead_time_weeks"])

    return lt


def load_distances() -> Dict[Tuple[str, str], float]:
    state_map = {
        "MI": "WH01",
        "OH": "WH02",
        "IN": "WH03",
        "IL": "WH04",
        "KY": "WH05",
        "MO": "WH06",
    }

    dist: Dict[Tuple[str, str], float] = {}

    with (DATA_DIR / "FGPs_distance.csv").open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            from_state = row["State"].strip()
            from_wh = state_map.get(from_state)

            if not from_wh:
                continue

            for state, wh in state_map.items():
                if state in row:
                    dist[(from_wh, wh)] = float(row[state])

    return dist


# ============================================================
# Problem builder
# ============================================================

def build_problem(
    product_id: str,
    flow: Dict[str, Dict[int, Dict]],
    bi_map: Dict[str, float],
    costs_map: Dict[str, Dict[int, Dict]],
    cap_map: Dict[int, float],
    cp: int,
    lt_oa: int | Dict[str, int],
    lt_plt_map: Dict[Tuple[str, str], int],
    dist_map: Dict[Tuple[str, str], float],
    tc: float = 1.2,
) -> Problem:
    warehouses = tuple(sorted(flow.keys()))

    periods_set = set()
    for wh_data in flow.values():
        periods_set.update(wh_data.keys())

    periods = tuple(sorted(periods_set))

    LT_PLT = {
        (i, j): v
        for (i, j), v in lt_plt_map.items()
        if i in warehouses and j in warehouses
    }

    if isinstance(lt_oa, dict):
        LT_OA = {wh: int(lt_oa[wh]) for wh in warehouses}
    else:
        LT_OA = {wh: int(lt_oa) for wh in warehouses}

    PLT_periods = {
        wh: frozenset(t for t in periods if t <= LT_OA[wh] - 1)
        for wh in warehouses
    }

    BI = {wh: bi_map.get(wh, 0.0) for wh in warehouses}

    delta_I = {}
    U = {}
    L = {}

    for wh in warehouses:
        for t in periods:
            entry = flow[wh].get(t, {})
            delta_I[(wh, t)] = entry.get("delta_I", 0.0)
            U[(wh, t)] = entry.get("U", 1e6)
            L[(wh, t)] = entry.get("L", 0.0)

    CAP = {
        t: cap_map.get(t, 9999.0)
        for t in periods
    }

    Co = {}
    Cs = {}
    Cb = {}
    Cp_map = {}

    for wh in warehouses:
        for t in periods:
            c = costs_map.get(wh, {}).get(t, {})
            Co[(wh, t)] = c.get("Co", 0.1)
            Cs[(wh, t)] = c.get("Cs", 0.5)
            Cb[(wh, t)] = c.get("Cb", 1500.0)
            Cp_map[(wh, t)] = c.get("Cp", 2000.0)

    dist = {
        (i, j): dist_map.get((i, j), 0.0)
        for i in warehouses
        for j in warehouses
    }

    Cp_plt = {}
    for (i, j) in LT_PLT:
        for t in periods:
            Cp_plt[(i, j, t)] = Cp_map.get((j, t), 0.0)

    return Problem(
        product=product_id,
        warehouses=warehouses,
        periods=periods,
        LT_OA=LT_OA,
        LT_PLT=LT_PLT,
        PLT_periods=PLT_periods,
        BI=BI,
        delta_I=delta_I,
        U=U,
        L=L,
        CAP=CAP,
        CP=cp,
        TC=tc,
        dist=dist,
        Co=Co,
        Cs=Cs,
        Cb=Cb,
        Cp=Cp_map,
        Cp_plt=Cp_plt,
    )


# ============================================================
# Output builders
# ============================================================

def extract_results(problem: Problem, sol: HeuristicSolutionWrapper, elapsed: float):
    p = problem

    schedule_rows = []
    cost_rows = []

    grand = {
        "overstock": 0.0,
        "shortage": 0.0,
        "backorder": 0.0,
        "penalty_OA": 0.0,
        "plt_penalty": 0.0,
        "transport": 0.0,
        "total": 0.0,
    }

    for t in p.periods:
        for wh in p.warehouses:
            inv = sol.I.get((wh, t), 0.0)
            q_oa = sol.Q_OA.get((wh, t), 0)

            lt_oa = p.LT_OA[wh] if isinstance(p.LT_OA, dict) else p.LT_OA
            recv_t = t - lt_oa + 1
            q_received = sol.Q_OA.get((wh, recv_t), 0) if recv_t in p.periods else 0

            plt_in = sum(
                sol.Q_PLT.get((src, wh, t2), 0.0)
                for src in p.warehouses
                if src != wh
                for t2 in p.periods
                if t2 == t - p.LT_PLT.get((src, wh), 0)
            )

            plt_out = sum(
                sol.Q_PLT.get((wh, dst, t), 0.0)
                for dst in p.warehouses
                if dst != wh
            )

            u_val = p.U.get((wh, t), 1e9)
            l_val = p.L.get((wh, t), 0.0)

            Co_ = p.Co.get((wh, t), 0.0) * max(inv - u_val, 0.0)
            Cs_ = p.Cs.get((wh, t), 0.0) * max(l_val - inv, 0.0)
            Cb_ = p.Cb.get((wh, t), 0.0) * max(-inv, 0.0)

            r_val = sol.r_OA.get((wh, t), 0)
            Cp_ = p.Cp.get((wh, t), 0.0) if r_val > 0 else 0.0

            tc_row = sum(
                p.dist.get((i, j), 0.0) * p.TC
                for (i, j, t2), q in sol.Q_PLT.items()
                if t2 == t and j == wh and q > 0
            )

            plt_pen_row = sum(
                p.Cp_plt.get((src, wh, t), 0.0)
                for src in p.warehouses
                if src != wh
                if sol.Q_PLT.get((src, wh, t), 0.0) % max(p.case_pack(wh, t), 1) > 0
            )

            row_total = Co_ + Cs_ + Cb_ + Cp_ + plt_pen_row + tc_row

            inv_begin = (
                sol.I.get((wh, t - 1), p.BI.get(wh, 0.0))
                if t > p.periods[0]
                else p.BI.get(wh, 0.0)
            )

            schedule_rows.append({
                "product": p.product,
                "week": t,
                "warehouse": wh,
                "inv_begin": round(inv_begin, 2),
                "Q_OA_allocated": q_oa,
                "Q_OA_received": q_received,
                "PLT_in": round(plt_in, 2),
                "PLT_out": round(plt_out, 2),
                "delta_I": p.delta_I.get((wh, t), 0.0),
                "inventory_end": round(inv, 2),
                "surplus_E": round(max(inv - l_val, 0.0), 2),
                "backorder": round(max(-inv, 0.0), 2),
                "shortage": round(max(l_val - inv, 0.0), 2),
                "overstock": round(max(inv - u_val, 0.0), 2),
            })

            cost_rows.append({
                "product": p.product,
                "week": t,
                "warehouse": wh,
                "overstock_cost": round(Co_, 4),
                "shortage_cost": round(Cs_, 4),
                "backorder_cost": round(Cb_, 4),
                "penalty_OA_cost": round(Cp_, 4),
                "plt_penalty_cost": round(plt_pen_row, 4),
                "transport_cost": round(tc_row, 4),
                "total_cost": round(row_total, 4),
            })

            grand["overstock"] += Co_
            grand["shortage"] += Cs_
            grand["backorder"] += Cb_
            grand["penalty_OA"] += Cp_
            grand["plt_penalty"] += plt_pen_row
            grand["transport"] += tc_row
            grand["total"] += row_total

    summary = {
        "product": p.product,
        "n_warehouses": p.n_wh,
        "n_periods": p.n_periods,
        "fitness": round(sol.fitness, 4),
        "elapsed_s": round(elapsed, 4),
        "total_overstock_cost": round(grand["overstock"], 4),
        "total_shortage_cost": round(grand["shortage"], 4),
        "total_backorder_cost": round(grand["backorder"], 4),
        "total_penalty_OA_cost": round(grand["penalty_OA"], 4),
        "total_plt_penalty_cost": round(grand["plt_penalty"], 4),
        "total_transport_cost": round(grand["transport"], 4),
        "grand_total_cost": round(grand["total"], 4),
    }

    return schedule_rows, cost_rows, summary


def write_csv(path: Path, rows: List[Dict], mode: str = "w") -> None:
    if not rows:
        return

    write_header = mode == "w" or not path.exists()

    with path.open(mode, newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())

        if write_header:
            w.writeheader()

        w.writerows(rows)


def get_writable_path(path: Path) -> Path:
    if not path.exists():
        return path

    try:
        with path.open("a", encoding="utf-8-sig"):
            pass
        return path
    except (IOError, PermissionError):
        suffix = 1

        while True:
            alt_path = path.parent / f"{path.stem}_{suffix}{path.suffix}"

            if not alt_path.exists():
                return alt_path

            try:
                with alt_path.open("a", encoding="utf-8-sig"):
                    pass
                return alt_path
            except (IOError, PermissionError):
                suffix += 1


# ============================================================
# Main
# ============================================================

def main() -> None:
    global DATA_DIR

    parser = argparse.ArgumentParser(
        description="Run Manual Planner Heuristic baseline for inventory allocation."
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(BASE_DIR / "sample_100_fixed"),
        help="Path to data directory",
    )

    parser.add_argument(
        "--max-products",
        type=int,
        default=999999,
        help="Max products to run",
    )

    args = parser.parse_args()

    DATA_DIR = Path(args.data_dir)

    if not DATA_DIR.exists():
        log.error("Data directory not found: %s", DATA_DIR)
        sys.exit(1)

    log.info("Loading CSV data from %s...", DATA_DIR)

    product_ids, flow_data = load_inventory_flow(n=args.max_products)
    bi_data = load_inventory_begin()
    costs_data = load_unit_costs()
    cap_data = load_vendor_capacity()
    cp_data = load_packing_details()
    lt_plt = load_plt_lead_times()
    dist_data = load_distances()

    LT_OA = load_oa_lead_times()
    TC = 1.2

    log.info("Found %d products to process.", len(product_ids))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    schedule_path = get_writable_path(OUTPUT_DIR / "schedule.csv")
    costs_path = get_writable_path(OUTPUT_DIR / "costs.csv")
    summary_path = get_writable_path(OUTPUT_DIR / "cost_summary.csv")
    log_path = get_writable_path(OUTPUT_DIR / "run_log.csv")

    for path in [schedule_path, costs_path, summary_path, log_path]:
        try:
            if path.exists():
                path.unlink()
        except Exception as exc:
            log.warning("Could not clear %s: %s", path.name, exc)

    all_summaries: List[Dict] = []
    success = 0
    failed = 0

    for idx, pid in enumerate(product_ids, 1):
        log.info("=" * 60)
        log.info("[%d/%d] Manual heuristic product: %s", idx, len(product_ids), pid)
        log.info("=" * 60)

        try:
            pflow = flow_data.get(pid, {})
            bi_map = bi_data.get(pid, {})
            c_map = costs_data.get(pid, {})
            cap_map = cap_data.get(pid, {})
            cp = cp_data.get(pid, 1)

            if not pflow:
                log.warning("No inventory_flow data for %s", pid)
                failed += 1
                continue

            if not bi_map:
                log.warning("No inventory_begin data for %s", pid)
                failed += 1
                continue

            problem = build_problem(
                product_id=pid,
                flow=pflow,
                bi_map=bi_map,
                costs_map=c_map,
                cap_map=cap_map,
                cp=cp,
                lt_oa=LT_OA,
                lt_plt_map=lt_plt,
                dist_map=dist_data,
                tc=TC,
            )

            t0 = time.perf_counter()
            solver = ManualPlannerHeuristic(problem)
            sol_dict = solver.solve()
            elapsed = time.perf_counter() - t0

            sol_wrapped = HeuristicSolutionWrapper(problem, sol_dict)

            sched_rows, cost_rows, summary = extract_results(
                problem=problem,
                sol=sol_wrapped,
                elapsed=elapsed,
            )

            write_csv(schedule_path, sched_rows, mode="a")
            write_csv(costs_path, cost_rows, mode="a")

            all_summaries.append(summary)

            log.info("  Cost      : %.4f", sol_wrapped.fitness)
            log.info("  Backorder : %.2f", summary["total_backorder_cost"])
            log.info("  Penalty OA: %.2f", summary["total_penalty_OA_cost"])
            log.info("  Transport : %.2f", summary["total_transport_cost"])
            log.info("  TOTAL     : %.2f", summary["grand_total_cost"])

            success += 1

        except Exception as exc:
            log.error("FAILED for %s: %s", pid, exc)
            log.debug(traceback.format_exc())

            failed += 1

            all_summaries.append({
                "product": pid,
                "n_warehouses": 0,
                "n_periods": 0,
                "fitness": None,
                "elapsed_s": None,
                "total_overstock_cost": None,
                "total_shortage_cost": None,
                "total_backorder_cost": None,
                "total_penalty_OA_cost": None,
                "total_plt_penalty_cost": None,
                "total_transport_cost": None,
                "grand_total_cost": None,
            })

    if all_summaries:
        write_csv(summary_path, all_summaries, mode="w")

    log_rows = []
    for s in all_summaries:
        log_rows.append({
            "product": s["product"],
            "n_warehouses": s["n_warehouses"],
            "n_periods": s["n_periods"],
            "fitness": s["fitness"],
            "elapsed_s": s["elapsed_s"],
            "grand_total_cost": s["grand_total_cost"],
            "status": "ok" if s["fitness"] is not None else "failed",
        })

    write_csv(log_path, log_rows, mode="w")

    log.info("=" * 60)
    log.info("DONE MANUAL HEURISTIC: %d success, %d failed", success, failed)
    log.info("Outputs in: %s", OUTPUT_DIR)
    log.info("  schedule.csv")
    log.info("  costs.csv")
    log.info("  cost_summary.csv")
    log.info("  run_log.csv")


if __name__ == "__main__":
    main()