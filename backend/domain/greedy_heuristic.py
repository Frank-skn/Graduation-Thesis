"""
Greedy Operational Heuristic for baseline cost calculation.

Port từ khóa luận/heuristic_baseline.py
Mô phỏng cách vận hành thực tế:
1. Cập nhật tồn kho theo cầu (DI)
2. Điều chuyển PLT từ warehouse dư sang thiếu
3. Phân bổ OA từ nguồn cung theo mức thiếu hụt dự kiến
4. Tính tổng chi phí (Co/Cs/Cb)
"""
from __future__ import annotations
import math
from typing import Dict, Tuple, Any
from backend.schemas.optimization import OptimizationInput


def _safe(mapping: Dict, key: Any, default: float = 0.0) -> float:
    """Lấy giá trị an toàn từ dictionary."""
    try:
        return float(mapping.get(key, default))
    except Exception:
        return float(default)


def _floor_case(qty: float, cp: int) -> int:
    """Làm tròn xuống theo case-pack."""
    return max(0, int(qty // cp) * cp)


def _residual(qty: float, cp: int) -> float:
    """Tính phần dư sau khi chia theo case-pack."""
    return max(0.0, qty - math.floor(qty / cp) * cp)


class GreedyOperationalHeuristic:
    """
    Core Greedy Operational Heuristic cho baseline cost.
    
    Tính chi phí thực tế với:
    - PLT transfer (điều chuyển giữa kho)
    - OA allocation (phân bổ theo mức thiếu hụt)
    - Đơn vị: (Co × overstock + Cs × shortage + Cb × backorder)
    """

    def __init__(self, data: OptimizationInput, lt_oa: int = 8, tc: float = 1.2):
        """
        Args:
            data: OptimizationInput từ backend
            lt_oa: Lead time OA (tuần)
            tc: Transport cost multiplier
        """
        self.data = data
        self.lt_oa = lt_oa
        self.tc = tc
        
        # Parse data structure
        self.items = sorted(set(i for (i, _) in data.CAP.keys()))  # Products
        self.warehouses = sorted(set(j for (_, j) in data.BI.keys()))  # Warehouses
        self.periods = sorted(set(t for (_, _, t) in data.DI.keys()))  # Time periods
        
        self.Q_oa: Dict[Tuple[str, str, int], float] = {}     # (product, wh, t)
        self.Q_plt: Dict[Tuple[str, str, str, int], float] = {}  # (product, donor, receiver, t)
        self.inventory: Dict[Tuple[str, str, int], float] = {}   # (product, wh, t)

    def solve(self) -> float:
        """
        Chạy heuristic và trả về total cost.
        
        Returns:
            total_cost: Tổng chi phí (overstock + shortage + backorder)
        """
        # Với mỗi product
        for product in self.items:
            self._solve_product(product)
        
        # Tính objective
        return self._evaluate()

    def _solve_product(self, product: str) -> None:
        """Giải quyết từng product."""
        # Khởi tạo tồn kho
        current_inventory: Dict[str, float] = {
            wh: _safe(self.data.BI, (wh, product), 0.0)
            for wh in self.warehouses
        }

        for t in self.periods:
            temp_inventory: Dict[str, float] = {}

            # 1. Cập nhật tồn kho trước PLT
            for wh in self.warehouses:
                temp_inventory[wh] = (
                    current_inventory.get(wh, 0.0)
                    + self._arrive_oa(product, wh, t)
                    + self._arrive_plt(product, wh, t)
                    + _safe(self.data.DI, (product, wh, t), 0.0)
                )

            # 2. Điều chuyển PLT
            self._greedy_plt(product, t, temp_inventory)

            # 3. Lưu tồn kho cuối kỳ
            for wh in self.warehouses:
                self.inventory[(product, wh, t)] = temp_inventory[wh]

            current_inventory = temp_inventory

            # 4. Phân bổ OA cho kỳ t
            oa_plan = self._greedy_oa(product, t, current_inventory)
            for wh, qty in oa_plan.items():
                if qty > 0:
                    self.Q_oa[(product, wh, t)] = qty

    def _arrive_oa(self, product: str, wh: str, t: int) -> float:
        """OA được giao với lead time lt_oa."""
        order_t = t - self.lt_oa
        if order_t not in self.periods:
            return 0.0
        return float(self.Q_oa.get((product, wh, order_t), 0.0))

    def _arrive_plt(self, product: str, wh: str, t: int) -> float:
        """PLT được giao đến warehouse."""
        # Để đơn giản, heuristic này không mô phỏng PLT transfer chi tiết
        # Nếu cần PLT, thêm logic tương tự _arrive_oa
        return 0.0

    def _greedy_oa(
        self,
        product: str,
        t: int,
        current_inventory: Dict[str, float],
    ) -> Dict[str, int]:
        """
        Phân bổ OA theo mức thiếu hụt dự kiến.
        """
        capacity = int(round(_safe(self.data.CAP, (product, t), 0.0)))
        if capacity <= 0:
            return {wh: 0 for wh in self.warehouses}

        cp = max(1, int(self.data.CP.get((product, self.warehouses[0]), 1)))

        priorities = self._oa_priorities(product, t, current_inventory)
        total_priority = sum(priorities.values())

        if total_priority <= 0:
            priorities = {wh: 1.0 for wh in self.warehouses}
            total_priority = float(len(self.warehouses))

        allocation = {
            wh: _floor_case(
                capacity * priorities[wh] / total_priority,
                cp,
            )
            for wh in self.warehouses
        }

        # Phân bổ phần dư
        allocation = self._repair_capacity(allocation, capacity, priorities, cp)

        return allocation

    def _oa_priorities(
        self,
        product: str,
        t: int,
        current_inventory: Dict[str, float],
    ) -> Dict[str, float]:
        """Tính priority cho OA allocation."""
        lt = self.lt_oa
        target_t = min(t + lt, self.periods[-1])

        priorities: Dict[str, float] = {}
        for wh in self.warehouses:
            projected_inv = self._project_inventory(
                product, wh, t, target_t, current_inventory.get(wh, 0.0)
            )
            floor = _safe(self.data.L, (product, wh, target_t), 0.0)
            shortage_cost = _safe(self.data.Cs, (product, wh, target_t), 1.0)
            backorder_cost = _safe(self.data.Cb, (product, wh, target_t), 1.0)

            shortage_need = max(0.0, floor - projected_inv)
            backorder_risk = max(0.0, -projected_inv)

            priorities[wh] = max(
                shortage_need * shortage_cost
                + backorder_risk * backorder_cost,
                0.0,
            )

        return priorities

    def _project_inventory(
        self,
        product: str,
        wh: str,
        current_t: int,
        target_t: int,
        current_inventory: float,
    ) -> float:
        """Dự báo tồn kho đến target_t."""
        projected = float(current_inventory)
        lt_oa = self.lt_oa

        for tau in range(current_t + 1, target_t + 1):
            if tau in self.periods:
                projected += _safe(self.data.DI, (product, wh, tau), 0.0)
                
                # OA đến tại tau
                order_t = tau - lt_oa
                if order_t in self.periods:
                    projected += self.Q_oa.get((product, wh, order_t), 0.0)

        return projected

    def _repair_capacity(
        self,
        allocation: Dict[str, int],
        capacity: int,
        priorities: Dict[str, float],
        cp: int,
    ) -> Dict[str, int]:
        """Sửa total OA = capacity."""
        remain = capacity - sum(allocation.values())

        if remain <= 0:
            return allocation

        sorted_warehouses = sorted(
            self.warehouses,
            key=lambda wh: priorities.get(wh, 0.0),
            reverse=True,
        )

        while remain > 0:
            for wh in sorted_warehouses:
                if remain <= 0:
                    break
                if remain >= cp:
                    allocation[wh] += cp
                    remain -= cp

        if remain > 0:
            allocation[sorted_warehouses[0]] += remain

        return allocation

    def _greedy_plt(
        self,
        product: str,
        t: int,
        inventory_now: Dict[str, float],
    ) -> None:
        """Điều chuyển PLT (optional - có thể bỏ qua cho baseline đơn giản)."""
        pass

    def _evaluate(self) -> float:
        """
        Tính objective: tổng Chi phí = Co×OV + Cs×SH + Cb×BK.
        """
        total_cost = 0.0

        for product in self.items:
            for wh in self.warehouses:
                for t in self.periods:
                    inv = self.inventory.get((product, wh, t), 0.0)
                    
                    floor = _safe(self.data.L, (product, wh, t), 0.0)
                    ceiling = _safe(self.data.U, (product, wh, t), 0.0)

                    overstock = max(0.0, inv - ceiling)
                    shortage = max(0.0, floor - inv)
                    backorder = max(0.0, -inv)

                    total_cost += (
                        _safe(self.data.Co, (product, wh, t)) * overstock
                        + _safe(self.data.Cs, (product, wh, t)) * shortage
                        + _safe(self.data.Cb, (product, wh, t)) * backorder
                    )

        return total_cost


def compute_greedy_baseline_cost(
    data: OptimizationInput,
    lt_oa: int = 8,
    tc: float = 1.2,
) -> float:
    """
    Tính baseline cost bằng Greedy Operational Heuristic.
    
    Args:
        data: OptimizationInput
        lt_oa: Lead time OA (tuần)
        tc: Transport cost multiplier
    
    Returns:
        total_cost: Chi phí baseline
    """
    heuristic = GreedyOperationalHeuristic(data, lt_oa=lt_oa, tc=tc)
    return heuristic.solve()
