"""
Sensitivity analysis service.
Performs one-at-a-time (OAT) parameter sensitivity and tornado analysis
by perturbing individual parameters and re-solving the optimization model.
"""
import copy
from typing import Dict, List, Optional, Any, Tuple

from backend.schemas.optimization import OptimizationInput
from backend.schemas.sensitivity import (
    SensitivityRequest,
    SensitivityPoint,
    SensitivityResult,
    TornadoRequest,
    TornadoBar,
    TornadoResult,
)
from backend.domain.services import OptimizationService, OptimizationResult


class SensitivityService:
    """
    Service for parameter sensitivity and tornado analysis.

    Workflow (OAT sensitivity):
        1. Solve the base scenario to get baseline KPIs / objective.
        2. For each variation percentage in the request:
            a. Deep-copy the base data.
            b. Scale the target parameter by (1 + pct/100).
            c. Solve the modified model.
            d. Record KPIs and objective.
        3. Optionally compute elasticity.

    Workflow (tornado):
        1. Solve the base scenario.
        2. For each parameter in the list:
            a. Solve at -variation_pct and +variation_pct.
            b. Record the low/high objective values.
        3. Sort bars by descending spread.
    """

    # ------------------------------------------------------------------ #
    #  One-at-a-time sensitivity                                         #
    # ------------------------------------------------------------------ #

    def run_sensitivity(
        self,
        base_data: OptimizationInput,
        request: SensitivityRequest,
        base_result: Optional[OptimizationResult] = None,
    ) -> SensitivityResult:
        """
        Run OAT sensitivity on a single parameter.

        Args:
            base_data: Original OptimizationInput.
            request: SensitivityRequest specifying parameter and variations.
            base_result: Pre-computed base result (avoids re-solving base).

        Returns:
            SensitivityResult with baseline and per-variation points.
        """
        solver_kwargs = dict(
            solver=request.solver or "cbc",
            time_limit=request.time_limit or 300,
            mip_gap=request.mip_gap or 0.01,
        )

        # Apply stratified sample if requested
        sample_size = getattr(request, 'sample_size', None)
        if sample_size:
            base_data = self._sample_products(base_data, sample_size)

        # Solve baseline if not provided
        if base_result is None:
            base_result = OptimizationService(**solver_kwargs).solve(base_data)

        baseline_obj = base_result.objective_value
        baseline_kpis = dict(base_result.kpis)

        # Run each variation
        points: List[SensitivityPoint] = []
        for pct in request.variation_percentages:
            scale_factor = 1.0 + pct / 100.0
            modified = self._scale_parameter(
                base_data,
                request.parameter_name,
                scale_factor,
                products=request.products,
                warehouses=request.warehouses,
                periods=request.periods,
            )

            try:
                svc = OptimizationService(**solver_kwargs)
                res = svc.solve(modified)
                points.append(
                    SensitivityPoint(
                        variation_pct=pct,
                        scale_factor=round(scale_factor, 4),
                        objective_value=res.objective_value,
                        solver_status=res.solver_status,
                        kpis=dict(res.kpis),
                    )
                )
            except RuntimeError as exc:
                # Infeasible or solver failure at this variation
                points.append(
                    SensitivityPoint(
                        variation_pct=pct,
                        scale_factor=round(scale_factor, 4),
                        objective_value=float("nan"),
                        solver_status=f"failed: {exc}",
                        kpis={},
                    )
                )

        # Compute elasticity from the smallest absolute variation
        elasticity = self._compute_elasticity(baseline_obj, points)

        return SensitivityResult(
            scenario_id=request.scenario_id,
            parameter_name=request.parameter_name,
            baseline_objective=baseline_obj,
            baseline_kpis=baseline_kpis,
            points=points,
            elasticity=elasticity,
        )

    # ------------------------------------------------------------------ #
    #  Tornado analysis                                                  #
    # ------------------------------------------------------------------ #

    def run_tornado(
        self,
        base_data: OptimizationInput,
        request: TornadoRequest,
        base_result: Optional[OptimizationResult] = None,
    ) -> TornadoResult:
        """
        Run tornado analysis across multiple parameters.

        Args:
            base_data: Original OptimizationInput.
            request: TornadoRequest with parameters and variation_pct.
            base_result: Pre-computed base result (avoids re-solving base).

        Returns:
            TornadoResult with bars sorted by descending spread.
        """
        solver_kwargs = dict(
            solver=request.solver or "cbc",
            time_limit=request.time_limit or 300,
            mip_gap=request.mip_gap or 0.01,
        )

        # Apply stratified sample if requested
        sample_size = getattr(request, 'sample_size', None)
        if sample_size:
            base_data = self._sample_products(base_data, sample_size)

        if base_result is None:
            base_result = OptimizationService(**solver_kwargs).solve(base_data)

        baseline_obj = base_result.objective_value
        variation = request.variation_pct

        bars: List[TornadoBar] = []
        for param_name in request.parameters:
            low_obj = self._solve_at_variation(
                base_data, param_name, -variation, solver_kwargs
            )
            high_obj = self._solve_at_variation(
                base_data, param_name, +variation, solver_kwargs
            )

            # If either solve failed, skip this parameter
            if low_obj is None or high_obj is None:
                continue

            spread = abs(high_obj - low_obj)
            low_pct = (
                (low_obj - baseline_obj) / baseline_obj * 100
                if baseline_obj != 0
                else 0.0
            )
            high_pct = (
                (high_obj - baseline_obj) / baseline_obj * 100
                if baseline_obj != 0
                else 0.0
            )

            bars.append(
                TornadoBar(
                    parameter_name=param_name,
                    low_value=low_obj,
                    high_value=high_obj,
                    spread=round(spread, 4),
                    low_pct_change=round(low_pct, 2),
                    high_pct_change=round(high_pct, 2),
                )
            )

        # Sort by descending spread (most impactful first)
        bars.sort(key=lambda b: b.spread, reverse=True)

        return TornadoResult(
            scenario_id=request.scenario_id,
            variation_pct=variation,
            baseline_objective=baseline_obj,
            bars=bars,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    def _solve_at_variation(
        self,
        base_data: OptimizationInput,
        param_name: str,
        variation_pct: float,
        solver_kwargs: Dict[str, Any],
    ) -> Optional[float]:
        """
        Scale *param_name* by (1 + variation_pct/100), solve, and return
        the objective value.  Returns None on solver failure.
        """
        scale_factor = 1.0 + variation_pct / 100.0
        modified = self._scale_parameter(base_data, param_name, scale_factor)
        try:
            svc = OptimizationService(**solver_kwargs)
            res = svc.solve(modified)
            return res.objective_value
        except RuntimeError:
            return None

    @staticmethod
    def _scale_parameter(
        base_data: OptimizationInput,
        param_name: str,
        scale_factor: float,
        products: Optional[List[str]] = None,
        warehouses: Optional[List[str]] = None,
        periods: Optional[List[int]] = None,
    ) -> OptimizationInput:
        """
        Deep-copy base_data and scale the named parameter by *scale_factor*.

        Supports:
            - (i, j, t) keyed params: DI, U, L, Cb, Co, Cs, Cp
            - (i, t) keyed params: CAP
            - (i, j) keyed params: BI, CP

        Scoping via products / warehouses / periods filters entries.
        """
        data = copy.deepcopy(base_data)
        param_map: Dict[str, Any] = {
            "DI": data.DI,
            "U": data.U,
            "L": data.L,
            "Cb": data.Cb,
            "Co": data.Co,
            "Cs": data.Cs,
            "Cp": data.Cp,
            "CAP": data.CAP,
            "BI": data.BI,
            "CP": data.CP,
        }

        target = param_map.get(param_name)
        if target is None:
            raise ValueError(
                f"Unknown parameter '{param_name}'. "
                f"Valid names: {list(param_map.keys())}"
            )

        products = products or []
        warehouses = warehouses or []
        periods = periods or []

        for key in list(target.keys()):
            if not SensitivityService._key_in_scope(key, products, warehouses, periods):
                continue

            original = target[key]
            if isinstance(original, int):
                target[key] = int(original * scale_factor)
            else:
                target[key] = original * scale_factor

        return data

    @staticmethod
    def _key_in_scope(
        key: tuple,
        products: List[str],
        warehouses: List[str],
        periods: List[int],
    ) -> bool:
        """
        Check whether a parameter key falls within the requested scope.
        Works for keys of length 2 (i,t) or (i,j), and length 3 (i,j,t).
        """
        if len(key) == 3:
            i, j, t = key
            if products and i not in products:
                return False
            if warehouses and j not in warehouses:
                return False
            if periods and t not in periods:
                return False
        elif len(key) == 2:
            a, b = key
            # (i, t) for CAP or (i, j) for BI/CP
            if isinstance(b, int):
                # Likely (i, t)
                if products and a not in products:
                    return False
                if periods and b not in periods:
                    return False
            else:
                # Likely (i, j)
                if products and a not in products:
                    return False
                if warehouses and b not in warehouses:
                    return False
        return True

    @staticmethod
    def _sample_products(
        base_data: OptimizationInput,
        sample_size: int,
    ) -> OptimizationInput:
        """
        Return a copy of base_data restricted to a *stratified* sample of products.

        Stratification by number of warehouses served (n_wh groups):
        each group contributes proportionally to sample_size, with top-Cb
        products selected within each group. This ensures the sample covers
        all warehouse-count tiers and captures the high-cost products that
        dominate the sensitivity signal.
        """
        from collections import defaultdict

        # Build per-product stats: total Cb and set of warehouses
        cb_total: Dict[str, float] = defaultdict(float)
        n_wh: Dict[str, set] = defaultdict(set)
        for (i, j, t), v in base_data.Cb.items():
            cb_total[i] += v
            n_wh[i].add(j)

        # Group products by warehouse count
        wh_groups: Dict[int, List[str]] = defaultdict(list)
        for i in base_data.I:
            wh_groups[len(n_wh.get(i, set()))].append(i)

        # Remove group 0 (no warehouse data — not useful for sensitivity)
        wh_groups.pop(0, None)

        if not wh_groups:
            # Fallback: just take first sample_size products
            sampled_products = sorted(base_data.I)[:sample_size]
        else:
            total_active = sum(len(g) for g in wh_groups.values())
            sampled_products = []
            for nwh in sorted(wh_groups):
                grp = wh_groups[nwh]
                n_pick = max(1, round(len(grp) / total_active * sample_size))
                # Pick top-Cb products within group for maximum signal
                top = sorted(grp, key=lambda x: -cb_total.get(x, 0))[:n_pick]
                sampled_products.extend(top)
            # Trim or pad to exact sample_size
            sampled_products = sampled_products[:sample_size]

        product_set = set(sampled_products)
        print(f"[SensitivityService] Stratified sample: {len(sampled_products)} products "
              f"from {len(wh_groups)} WH-count groups (out of {len(base_data.I)} total)")

        data = copy.deepcopy(base_data)
        data.I = sampled_products

        for attr in ('DI', 'U', 'L', 'Cb', 'Co', 'Cs', 'Cp'):
            original = getattr(data, attr)
            setattr(data, attr, {k: v for k, v in original.items() if k[0] in product_set})

        data.CAP = {k: v for k, v in data.CAP.items() if k[0] in product_set}
        data.BI  = {k: v for k, v in data.BI.items()  if k[0] in product_set}
        data.CP  = {k: v for k, v in data.CP.items()  if k[0] in product_set}

        return data

    @staticmethod
    def _compute_elasticity(
        baseline_obj: float,
        points: List[SensitivityPoint],
    ) -> Optional[float]:
        """
        Compute approximate elasticity from the smallest-magnitude valid
        variation point:  elasticity = (%change_obj) / (%change_param).
        """
        if baseline_obj == 0:
            return None

        # Filter to valid (non-nan) points
        valid = [
            p for p in points
            if p.variation_pct != 0 and p.objective_value == p.objective_value  # NaN check
        ]
        if not valid:
            return None

        # Pick the one with the smallest absolute variation
        closest = min(valid, key=lambda p: abs(p.variation_pct))
        pct_change_obj = (closest.objective_value - baseline_obj) / baseline_obj * 100
        elasticity = pct_change_obj / closest.variation_pct
        return round(elasticity, 4)
