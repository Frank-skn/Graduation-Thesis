"""
What-If scenario service.
Applies predefined scenario modifications to a base OptimizationInput,
solves the modified problem, and returns comparison results.
"""
import copy
from typing import Dict, Any, List, Optional, Tuple

from backend.schemas.optimization import OptimizationInput
from backend.schemas.whatif import (
    ScenarioType,
    WhatIfCreate,
    WhatIfKPIs,
    WhatIfResponse,
    WhatIfComparison,
    KPIDelta,
)
from backend.domain.services import OptimizationService, OptimizationResult


class WhatIfService:
    """
    Service for creating and evaluating what-if scenarios.

    Workflow:
        1. Deep-copy the base OptimizationInput.
        2. Apply the requested scenario modification.
        3. Solve the modified model via OptimizationService.
        4. Return KPIs and optional comparison against the base run.
    """

    # ------------------------------------------------------------------ #
    #  Internal counter for whatif IDs (in-memory; replace with DB seq)   #
    # ------------------------------------------------------------------ #
    _next_id: int = 1

    @classmethod
    def _allocate_id(cls) -> int:
        wid = cls._next_id
        cls._next_id += 1
        return wid

    # ------------------------------------------------------------------ #
    #  Public API                                                        #
    # ------------------------------------------------------------------ #

    def run_whatif(
        self,
        base_data: OptimizationInput,
        request: WhatIfCreate,
        base_kpis: Optional[Dict[str, float]] = None,
        base_objective: Optional[float] = None,
    ) -> WhatIfResponse:
        """
        Execute a what-if scenario.

        Args:
            base_data: The original (unmodified) optimization input.
            request: What-if creation request with scenario type + overrides.
            base_kpis: KPIs from the base run (used for comparison).
            base_objective: Objective value from the base run.

        Returns:
            WhatIfResponse containing solver results and KPIs.
        """
        # 1. Clone & modify
        modified_data = self.apply_whatif(base_data, request.scenario_type, request.overrides)

        # 2. Solve
        svc = OptimizationService(
            solver=request.solver or "cbc",
            time_limit=request.time_limit or 300,
            mip_gap=request.mip_gap or 0.01,
        )
        result: OptimizationResult = svc.solve(modified_data)

        # 3. Build response
        kpis = WhatIfKPIs(
            total_cost=result.kpis.get("total_cost", 0.0),
            total_backorder=result.kpis.get("total_backorder", 0.0),
            total_overstock=result.kpis.get("total_overstock", 0.0),
            total_shortage=result.kpis.get("total_shortage", 0.0),
            total_penalty=result.kpis.get("total_penalty", 0.0),
            cost_backorder=result.kpis.get("cost_backorder", 0.0),
            cost_overstock=result.kpis.get("cost_overstock", 0.0),
            cost_shortage=result.kpis.get("cost_shortage",  0.0),
            cost_penalty=result.kpis.get("cost_penalty",   0.0),
            service_level=result.kpis.get("service_level", 0.0),
            capacity_utilization=result.kpis.get("capacity_utilization", 0.0),
        )

        params_modified = self._affected_parameters(request.scenario_type)

        return WhatIfResponse(
            whatif_id=self._allocate_id(),
            base_scenario_id=request.base_scenario_id,
            scenario_type=request.scenario_type,
            label=request.label,
            solver_status=result.solver_status,
            solve_time_seconds=result.solve_time,
            objective_value=result.objective_value,
            kpis=kpis,
            parameters_modified=params_modified,
            baseline_cost=result.baseline_cost,
            savings=result.savings,
            savings_pct=result.savings_pct,
            n_changes=result.n_changes,
            si_mean=result.si_mean,
            ss_below_count=result.ss_below_count,
        )

    def compare(
        self,
        base_kpis: Dict[str, float],
        whatif_response: WhatIfResponse,
    ) -> WhatIfComparison:
        """
        Build a side-by-side KPI comparison between the base run and a what-if run.

        Args:
            base_kpis: KPIs dictionary from the base optimization run.
            whatif_response: Response from run_whatif().

        Returns:
            WhatIfComparison with per-KPI deltas and a text summary.
        """
        whatif_kpis = {
            "total_cost": whatif_response.kpis.total_cost,
            "total_backorder": whatif_response.kpis.total_backorder,
            "total_overstock": whatif_response.kpis.total_overstock,
            "total_shortage": whatif_response.kpis.total_shortage,
            "total_penalty": whatif_response.kpis.total_penalty,
            "service_level": whatif_response.kpis.service_level,
            "capacity_utilization": whatif_response.kpis.capacity_utilization,
        }

        deltas: List[KPIDelta] = []
        for name in whatif_kpis:
            base_val = base_kpis.get(name, 0.0)
            wi_val = whatif_kpis[name]
            abs_change = wi_val - base_val
            pct_change = (abs_change / base_val * 100) if base_val != 0 else None
            deltas.append(
                KPIDelta(
                    kpi_name=name,
                    base_value=base_val,
                    whatif_value=wi_val,
                    absolute_change=abs_change,
                    percent_change=round(pct_change, 2) if pct_change is not None else None,
                )
            )

        # Build a short textual summary
        summary_parts: List[str] = []
        for d in deltas:
            if d.percent_change is not None and abs(d.percent_change) >= 1.0:
                direction = "increases" if d.percent_change > 0 else "decreases"
                summary_parts.append(
                    f"{d.kpi_name} {direction} by {abs(d.percent_change):.1f}%"
                )
        summary = "; ".join(summary_parts) if summary_parts else "No significant KPI changes."

        return WhatIfComparison(
            base_scenario_id=whatif_response.base_scenario_id,
            whatif_id=whatif_response.whatif_id,
            scenario_type=whatif_response.scenario_type,
            label=whatif_response.label,
            deltas=deltas,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    #  Core modification logic                                           #
    # ------------------------------------------------------------------ #

    def apply_whatif(
        self,
        base_data: OptimizationInput,
        scenario_type: ScenarioType,
        overrides: Dict[str, Any],
    ) -> OptimizationInput:
        """
        Deep-copy *base_data* and apply the scenario modification in-place
        on the copy.

        Args:
            base_data: Original OptimizationInput (will NOT be mutated).
            scenario_type: Which modification to apply.
            overrides: Dict of override values (factor, products, periods, ...).

        Returns:
            A new OptimizationInput with modifications applied.
        """
        data = copy.deepcopy(base_data)

        handler = self._HANDLERS.get(scenario_type)
        if handler is None:
            raise ValueError(f"Unsupported scenario type: {scenario_type}")

        handler(self, data, overrides)
        return data

    # ------------------------------------------------------------------ #
    #  Individual scenario handlers                                      #
    # ------------------------------------------------------------------ #

    def _apply_demand_surge(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """Multiply DI values by *factor* (>1 means increase)."""
        factor = float(ov.get("factor", 1.2))
        self._scale_param_ijt(data.DI, factor, data, ov)

    def _apply_demand_drop(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """Multiply DI values by *factor* (<1 means decrease)."""
        factor = float(ov.get("factor", 0.8))
        self._scale_param_ijt(data.DI, factor, data, ov)

    def _apply_capacity_disruption(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """Reduce CAP by *factor* (e.g. 0.5 = 50% capacity remaining)."""
        factor = float(ov.get("factor", 0.5))
        products = ov.get("products", [])
        periods = ov.get("periods", [])
        for key in list(data.CAP.keys()):
            i, t = key
            if products and i not in products:
                continue
            if periods and t not in periods:
                continue
            data.CAP[key] = int(data.CAP[key] * factor)

    def _apply_capacity_expansion(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """Increase CAP by *factor* (e.g. 1.5 = 50% more capacity)."""
        factor = float(ov.get("factor", 1.5))
        products = ov.get("products", [])
        periods = ov.get("periods", [])
        for key in list(data.CAP.keys()):
            i, t = key
            if products and i not in products:
                continue
            if periods and t not in periods:
                continue
            data.CAP[key] = int(data.CAP[key] * factor)

    def _apply_cost_increase(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """Increase all cost parameters (Cb, Co, Cs, Cp) by *factor*."""
        factor = float(ov.get("factor", 1.2))
        for cost_dict in [data.Cb, data.Co, data.Cs, data.Cp]:
            self._scale_param_ijt(cost_dict, factor, data, ov)

    def _apply_cost_decrease(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """Decrease all cost parameters (Cb, Co, Cs, Cp) by *factor*."""
        factor = float(ov.get("factor", 0.8))
        for cost_dict in [data.Cb, data.Co, data.Cs, data.Cp]:
            self._scale_param_ijt(cost_dict, factor, data, ov)

    def _apply_safety_stock_tighten(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """
        Tighten safety stock bounds: increase L (lower) and/or decrease U (upper),
        narrowing the acceptable inventory range.
        The *factor* controls how much the U-L gap shrinks (0.5 = halve the gap).
        """
        factor = float(ov.get("factor", 0.5))
        products = ov.get("products", [])
        warehouses = ov.get("warehouses", [])
        periods = ov.get("periods", [])
        for key in list(data.U.keys()):
            i, j, t = key
            if products and i not in products:
                continue
            if warehouses and j not in warehouses:
                continue
            if periods and t not in periods:
                continue
            u_val = data.U[key]
            l_val = data.L.get(key, 0)
            gap = u_val - l_val
            new_gap = gap * factor
            mid = (u_val + l_val) / 2
            data.U[key] = int(mid + new_gap / 2)
            data.L[key] = int(mid - new_gap / 2)

    def _apply_safety_stock_loosen(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """
        Loosen safety stock bounds: widen the U-L gap by *factor* (>1).
        """
        factor = float(ov.get("factor", 1.5))
        products = ov.get("products", [])
        warehouses = ov.get("warehouses", [])
        periods = ov.get("periods", [])
        for key in list(data.U.keys()):
            i, j, t = key
            if products and i not in products:
                continue
            if warehouses and j not in warehouses:
                continue
            if periods and t not in periods:
                continue
            u_val = data.U[key]
            l_val = data.L.get(key, 0)
            gap = u_val - l_val
            new_gap = gap * factor
            mid = (u_val + l_val) / 2
            data.U[key] = int(mid + new_gap / 2)
            data.L[key] = max(0, int(mid - new_gap / 2))

    def _apply_new_product_introduction(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """
        Add a new product to the model.
        Requires overrides:
            new_product_id: str
            bi_values: Dict[str, int]  -- {warehouse_id: beginning_inventory}
            cp_values: Dict[str, int]  -- {warehouse_id: case_pack}
            di_values: Dict[str, Dict[str, int]]  -- {warehouse_id: {period: demand}}
            cap_values: Dict[str, int]  -- {period: capacity}
        Missing values default to 0.
        """
        new_id = ov.get("new_product_id", "NEW_PROD")
        if new_id not in data.I:
            data.I.append(new_id)

        bi_vals = ov.get("bi_values", {})
        cp_vals = ov.get("cp_values", {})
        di_vals = ov.get("di_values", {})
        cap_vals = ov.get("cap_values", {})

        for j in data.J:
            data.BI[(new_id, j)] = bi_vals.get(j, 0)
            data.CP[(new_id, j)] = cp_vals.get(j, 1)
            for t in data.T:
                wh_di = di_vals.get(j, {})
                data.DI[(new_id, j, t)] = wh_di.get(str(t), wh_di.get(t, 0))
                data.U[(new_id, j, t)] = 0
                data.L[(new_id, j, t)] = 0
                data.Cb[(new_id, j, t)] = 1.0
                data.Co[(new_id, j, t)] = 1.0
                data.Cs[(new_id, j, t)] = 1.0
                data.Cp[(new_id, j, t)] = 1.0

        for t in data.T:
            data.CAP[(new_id, t)] = cap_vals.get(str(t), cap_vals.get(t, 0))

    def _apply_warehouse_closure(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """
        Simulate closing one or more warehouses by setting their
        DI to 0 and capacity to 0 for the specified warehouses.
        Remaining demand can optionally be redistributed.
        """
        closed_warehouses: List[str] = ov.get("warehouses", [])
        redistribute: bool = ov.get("redistribute", False)

        if not closed_warehouses:
            return

        remaining_warehouses = [j for j in data.J if j not in closed_warehouses]

        for key in list(data.DI.keys()):
            i, j, t = key
            if j in closed_warehouses:
                lost_demand = data.DI[key]
                data.DI[key] = 0
                data.U[(i, j, t)] = 0
                data.L[(i, j, t)] = 0

                # Optionally redistribute demand equally among remaining warehouses
                if redistribute and remaining_warehouses and lost_demand != 0:
                    share = lost_demand // len(remaining_warehouses)
                    remainder = lost_demand % len(remaining_warehouses)
                    for idx, rj in enumerate(remaining_warehouses):
                        extra = 1 if idx < remainder else 0
                        rkey = (i, rj, t)
                        if rkey in data.DI:
                            data.DI[rkey] += share + extra

    def _apply_custom(self, data: OptimizationInput, ov: Dict[str, Any]) -> None:
        """
        Generic custom scenario: apply explicit parameter overrides.
        overrides may contain:
            parameter_overrides: Dict[str, Dict[str, Any]]
            e.g. {"DI": {("PROD001","WH01",1): 999}}
        """
        param_overrides: Dict[str, Dict] = ov.get("parameter_overrides", {})
        param_map = {
            "DI": data.DI,
            "CAP": data.CAP,
            "U": data.U,
            "L": data.L,
            "BI": data.BI,
            "CP": data.CP,
            "Cb": data.Cb,
            "Co": data.Co,
            "Cs": data.Cs,
            "Cp": data.Cp,
        }
        for param_name, values in param_overrides.items():
            target = param_map.get(param_name)
            if target is None:
                continue
            for key_str, val in values.items():
                # Keys may come as strings from JSON -- attempt tuple conversion
                key = self._parse_key(key_str)
                target[key] = val

    # ------------------------------------------------------------------ #
    #  Handler dispatch table                                            #
    # ------------------------------------------------------------------ #

    _HANDLERS = {
        ScenarioType.DEMAND_SURGE: _apply_demand_surge,
        ScenarioType.DEMAND_DROP: _apply_demand_drop,
        ScenarioType.CAPACITY_DISRUPTION: _apply_capacity_disruption,
        ScenarioType.CAPACITY_EXPANSION: _apply_capacity_expansion,
        ScenarioType.COST_INCREASE: _apply_cost_increase,
        ScenarioType.COST_DECREASE: _apply_cost_decrease,
        ScenarioType.SAFETY_STOCK_TIGHTEN: _apply_safety_stock_tighten,
        ScenarioType.SAFETY_STOCK_LOOSEN: _apply_safety_stock_loosen,
        ScenarioType.NEW_PRODUCT_INTRODUCTION: _apply_new_product_introduction,
        ScenarioType.WAREHOUSE_CLOSURE: _apply_warehouse_closure,
        ScenarioType.CUSTOM: _apply_custom,
    }

    # ------------------------------------------------------------------ #
    #  Helpers                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _scale_param_ijt(
        param: Dict,
        factor: float,
        data: OptimizationInput,
        ov: Dict[str, Any],
    ) -> None:
        """Scale a (i, j, t)-keyed parameter dict by *factor*, scoped by overrides."""
        products = ov.get("products", [])
        warehouses = ov.get("warehouses", [])
        periods = ov.get("periods", [])

        for key in list(param.keys()):
            # (i, j, t) or (i, t) -- handle both
            if len(key) == 3:
                i, j, t = key
                if products and i not in products:
                    continue
                if warehouses and j not in warehouses:
                    continue
                if periods and t not in periods:
                    continue
            elif len(key) == 2:
                i, t = key
                if products and i not in products:
                    continue
                if periods and t not in periods:
                    continue
            else:
                continue

            original = param[key]
            if isinstance(original, int):
                param[key] = int(original * factor)
            else:
                param[key] = original * factor

    @staticmethod
    def _affected_parameters(scenario_type: ScenarioType) -> List[str]:
        """Return the list of parameter names affected by a scenario type."""
        mapping = {
            ScenarioType.DEMAND_SURGE: ["DI"],
            ScenarioType.DEMAND_DROP: ["DI"],
            ScenarioType.CAPACITY_DISRUPTION: ["CAP"],
            ScenarioType.CAPACITY_EXPANSION: ["CAP"],
            ScenarioType.COST_INCREASE: ["Cb", "Co", "Cs", "Cp"],
            ScenarioType.COST_DECREASE: ["Cb", "Co", "Cs", "Cp"],
            ScenarioType.SAFETY_STOCK_TIGHTEN: ["U", "L"],
            ScenarioType.SAFETY_STOCK_LOOSEN: ["U", "L"],
            ScenarioType.NEW_PRODUCT_INTRODUCTION: ["I", "DI", "CAP", "BI", "CP", "U", "L", "Cb", "Co", "Cs", "Cp"],
            ScenarioType.WAREHOUSE_CLOSURE: ["DI", "U", "L"],
            ScenarioType.CUSTOM: [],
        }
        return mapping.get(scenario_type, [])

    @staticmethod
    def _parse_key(key_str):
        """
        Convert a string representation of a tuple key back to a tuple.
        E.g. "('PROD001', 'WH01', 1)" -> ('PROD001', 'WH01', 1)
        Also handles already-tuple keys gracefully.
        """
        if isinstance(key_str, tuple):
            return key_str
        if isinstance(key_str, list):
            return tuple(key_str)
        # Try literal eval for string representations
        import ast
        try:
            parsed = ast.literal_eval(key_str)
            if isinstance(parsed, tuple):
                return parsed
            return (parsed,)
        except (ValueError, SyntaxError):
            return key_str
