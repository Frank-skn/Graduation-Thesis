"""
Insights service.
Generates rule-based decision insights and recommendations by examining
KPIs and per-record optimization results.
"""
import uuid
from collections import defaultdict
from typing import Dict, List, Any, Optional

from backend.schemas.insights import (
    Insight,
    InsightSeverity,
    InsightCategory,
    InsightsRequest,
    InsightsResponse,
)


class InsightsService:
    """
    Rule-based insight generator for supply-chain optimization results.

    Each rule method examines the KPIs dict and/or the per-record results
    and emits zero or more Insight objects.  The rules are:

        1. Service level thresholds (critical / warning)
        2. Capacity utilization (over-utilization / under-utilization)
        3. Backorder pattern detection
        4. Overstock pattern detection
        5. Shortage detection
        6. Penalty flag accumulation
        7. Cost driver identification
        8. Inventory imbalance across warehouses
    """

    def generate(self, request: InsightsRequest) -> InsightsResponse:
        """
        Run all insight rules and return a sorted, counted response.

        Args:
            request: InsightsRequest with KPIs, results, and thresholds.

        Returns:
            InsightsResponse with all generated insights.
        """
        kpis = request.kpis
        results = request.results
        thresholds = request.thresholds
        insights: List[Insight] = []

        # Run every rule
        insights.extend(self._check_service_level(kpis, results, thresholds))
        insights.extend(self._check_capacity_utilization(kpis, results, thresholds))
        insights.extend(self._check_backorder_patterns(kpis, results, thresholds))
        insights.extend(self._check_overstock_patterns(kpis, results, thresholds))
        insights.extend(self._check_shortage(kpis, results, thresholds))
        insights.extend(self._check_penalty_flags(kpis, results, thresholds))
        insights.extend(self._check_cost_drivers(kpis, results, thresholds))
        insights.extend(self._check_inventory_imbalance(kpis, results, thresholds))

        # Sort: critical first, then warning, then info, then opportunity
        severity_order = {
            InsightSeverity.CRITICAL: 0,
            InsightSeverity.WARNING: 1,
            InsightSeverity.INFO: 2,
            InsightSeverity.OPPORTUNITY: 3,
        }
        insights.sort(key=lambda ins: severity_order.get(ins.severity, 99))

        # Count by severity
        critical = sum(1 for i in insights if i.severity == InsightSeverity.CRITICAL)
        warning = sum(1 for i in insights if i.severity == InsightSeverity.WARNING)
        info = sum(1 for i in insights if i.severity == InsightSeverity.INFO)
        opportunity = sum(1 for i in insights if i.severity == InsightSeverity.OPPORTUNITY)

        return InsightsResponse(
            scenario_id=request.scenario_id,
            run_id=request.run_id,
            total_insights=len(insights),
            critical_count=critical,
            warning_count=warning,
            info_count=info,
            opportunity_count=opportunity,
            insights=insights,
        )

    # ------------------------------------------------------------------ #
    #  Rule 1: Service Level                                             #
    # ------------------------------------------------------------------ #

    def _check_service_level(
        self,
        kpis: Dict[str, float],
        results: List[Dict[str, Any]],
        thresholds: Dict[str, float],
    ) -> List[Insight]:
        insights: List[Insight] = []
        sl = kpis.get("service_level")
        if sl is None:
            return insights

        critical_th = thresholds.get("service_level_critical", 90.0)
        warning_th = thresholds.get("service_level_warning", 95.0)

        if sl < critical_th:
            insights.append(
                Insight(
                    insight_id=self._id("SL-CRIT"),
                    severity=InsightSeverity.CRITICAL,
                    category=InsightCategory.SERVICE_LEVEL,
                    title=f"Service level critically low at {sl:.1f}%",
                    description=(
                        f"The overall service level ({sl:.1f}%) is below "
                        f"the critical threshold of {critical_th:.0f}%. "
                        "A significant number of product-warehouse-period combinations "
                        "are experiencing backorders."
                    ),
                    recommendation=(
                        "Urgently review demand forecasts and safety stock parameters. "
                        "Consider increasing upper inventory bounds (U) or "
                        "re-evaluating capacity allocations."
                    ),
                    metric_name="service_level",
                    metric_value=sl,
                    threshold=critical_th,
                )
            )
        elif sl < warning_th:
            insights.append(
                Insight(
                    insight_id=self._id("SL-WARN"),
                    severity=InsightSeverity.WARNING,
                    category=InsightCategory.SERVICE_LEVEL,
                    title=f"Service level below target at {sl:.1f}%",
                    description=(
                        f"The service level ({sl:.1f}%) is below the "
                        f"target of {warning_th:.0f}% but above critical."
                    ),
                    recommendation=(
                        "Monitor closely and consider adjusting safety stock "
                        "bounds to improve fill rates."
                    ),
                    metric_name="service_level",
                    metric_value=sl,
                    threshold=warning_th,
                )
            )
        else:
            insights.append(
                Insight(
                    insight_id=self._id("SL-OK"),
                    severity=InsightSeverity.INFO,
                    category=InsightCategory.SERVICE_LEVEL,
                    title=f"Service level healthy at {sl:.1f}%",
                    description=f"Service level ({sl:.1f}%) meets or exceeds target.",
                    metric_name="service_level",
                    metric_value=sl,
                    threshold=warning_th,
                )
            )

        return insights

    # ------------------------------------------------------------------ #
    #  Rule 2: Capacity Utilization                                      #
    # ------------------------------------------------------------------ #

    def _check_capacity_utilization(
        self,
        kpis: Dict[str, float],
        results: List[Dict[str, Any]],
        thresholds: Dict[str, float],
    ) -> List[Insight]:
        insights: List[Insight] = []
        cu = kpis.get("capacity_utilization")
        if cu is None:
            return insights

        high_th = thresholds.get("capacity_utilization_high", 90.0)
        low_th = thresholds.get("capacity_utilization_low", 30.0)

        if cu > high_th:
            insights.append(
                Insight(
                    insight_id=self._id("CAP-HIGH"),
                    severity=InsightSeverity.WARNING,
                    category=InsightCategory.CAPACITY,
                    title=f"Capacity utilization very high at {cu:.1f}%",
                    description=(
                        f"Capacity utilization ({cu:.1f}%) exceeds {high_th:.0f}%. "
                        "The system has limited headroom for demand spikes."
                    ),
                    recommendation=(
                        "Evaluate capacity expansion options or "
                        "implement demand smoothing strategies."
                    ),
                    metric_name="capacity_utilization",
                    metric_value=cu,
                    threshold=high_th,
                )
            )
        elif cu < low_th:
            insights.append(
                Insight(
                    insight_id=self._id("CAP-LOW"),
                    severity=InsightSeverity.OPPORTUNITY,
                    category=InsightCategory.CAPACITY,
                    title=f"Capacity under-utilized at {cu:.1f}%",
                    description=(
                        f"Capacity utilization ({cu:.1f}%) is below {low_th:.0f}%. "
                        "Significant spare capacity may represent cost savings opportunities."
                    ),
                    recommendation=(
                        "Consider consolidating warehouse operations or "
                        "accepting new product lines to improve utilization."
                    ),
                    metric_name="capacity_utilization",
                    metric_value=cu,
                    threshold=low_th,
                )
            )

        return insights

    # ------------------------------------------------------------------ #
    #  Rule 3: Backorder Patterns                                        #
    # ------------------------------------------------------------------ #

    def _check_backorder_patterns(
        self,
        kpis: Dict[str, float],
        results: List[Dict[str, Any]],
        thresholds: Dict[str, float],
    ) -> List[Insight]:
        insights: List[Insight] = []
        if not results:
            return insights

        total_bo = kpis.get("total_backorder", 0.0)
        if total_bo == 0:
            return insights

        # Identify products and warehouses with highest backorder concentration
        bo_by_product: Dict[str, float] = defaultdict(float)
        bo_by_warehouse: Dict[str, float] = defaultdict(float)
        bo_periods: Dict[str, List[int]] = defaultdict(list)

        for r in results:
            bo = r.get("backorder_qty", 0)
            if bo > 0:
                pid = r.get("product_id", "")
                wid = r.get("warehouse_id", "")
                t = r.get("time_period", 0)
                bo_by_product[pid] += bo
                bo_by_warehouse[wid] += bo
                bo_periods[pid].append(t)

        if not bo_by_product:
            return insights

        # Top offenders
        top_products = sorted(bo_by_product.items(), key=lambda x: x[1], reverse=True)[:5]
        top_warehouses = sorted(bo_by_warehouse.items(), key=lambda x: x[1], reverse=True)[:3]

        bo_ratio = len(bo_by_product) / max(len(set(r.get("product_id", "") for r in results)), 1)
        warning_ratio = thresholds.get("backorder_ratio_warning", 0.05)

        severity = (
            InsightSeverity.CRITICAL if bo_ratio > 2 * warning_ratio
            else InsightSeverity.WARNING if bo_ratio > warning_ratio
            else InsightSeverity.INFO
        )

        insights.append(
            Insight(
                insight_id=self._id("BO-PATTERN"),
                severity=severity,
                category=InsightCategory.BACKORDER,
                title=f"Backorder detected: {total_bo:.0f} units across {len(bo_by_product)} products",
                description=(
                    f"Total backorder of {total_bo:.0f} units spread across "
                    f"{len(bo_by_product)} products and {len(bo_by_warehouse)} warehouses. "
                    f"Most affected product: {top_products[0][0]} "
                    f"({top_products[0][1]:.0f} units)."
                ),
                recommendation=(
                    "Review demand forecasts for heavily back-ordered products. "
                    "Consider increasing production capacity or adjusting "
                    "safety stock parameters."
                ),
                affected_products=[p for p, _ in top_products],
                affected_warehouses=[w for w, _ in top_warehouses],
                metric_name="total_backorder",
                metric_value=total_bo,
                metadata={
                    "backorder_by_product": {p: v for p, v in top_products},
                    "backorder_by_warehouse": {w: v for w, v in top_warehouses},
                },
            )
        )

        # Check for persistent backorder (same product in 3+ periods)
        for pid, periods in bo_periods.items():
            unique_periods = sorted(set(periods))
            if len(unique_periods) >= 3:
                insights.append(
                    Insight(
                        insight_id=self._id(f"BO-PERSIST-{pid}"),
                        severity=InsightSeverity.WARNING,
                        category=InsightCategory.BACKORDER,
                        title=f"Persistent backorder: {pid} in {len(unique_periods)} periods",
                        description=(
                            f"Product {pid} has backorders in periods "
                            f"{unique_periods}. This may indicate a "
                            "systematic supply-demand imbalance."
                        ),
                        recommendation=(
                            f"Investigate root cause for {pid}: "
                            "is demand growing faster than planned supply?"
                        ),
                        affected_products=[pid],
                        affected_periods=unique_periods,
                        metric_name="backorder_persistence",
                        metric_value=float(len(unique_periods)),
                    )
                )

        return insights

    # ------------------------------------------------------------------ #
    #  Rule 4: Overstock Patterns                                        #
    # ------------------------------------------------------------------ #

    def _check_overstock_patterns(
        self,
        kpis: Dict[str, float],
        results: List[Dict[str, Any]],
        thresholds: Dict[str, float],
    ) -> List[Insight]:
        insights: List[Insight] = []
        if not results:
            return insights

        total_os = kpis.get("total_overstock", 0.0)
        if total_os == 0:
            return insights

        os_by_product: Dict[str, float] = defaultdict(float)
        os_by_warehouse: Dict[str, float] = defaultdict(float)

        for r in results:
            os_qty = r.get("overstock_qty", 0)
            if os_qty > 0:
                os_by_product[r.get("product_id", "")] += os_qty
                os_by_warehouse[r.get("warehouse_id", "")] += os_qty

        if not os_by_product:
            return insights

        top_products = sorted(os_by_product.items(), key=lambda x: x[1], reverse=True)[:5]
        top_warehouses = sorted(os_by_warehouse.items(), key=lambda x: x[1], reverse=True)[:3]

        os_ratio = len(os_by_product) / max(len(set(r.get("product_id", "") for r in results)), 1)
        warning_ratio = thresholds.get("overstock_ratio_warning", 0.10)

        severity = (
            InsightSeverity.WARNING if os_ratio > warning_ratio
            else InsightSeverity.INFO
        )

        insights.append(
            Insight(
                insight_id=self._id("OS-PATTERN"),
                severity=severity,
                category=InsightCategory.OVERSTOCK,
                title=f"Overstock detected: {total_os:.0f} units across {len(os_by_product)} products",
                description=(
                    f"Total overstock of {total_os:.0f} units. "
                    f"Most affected product: {top_products[0][0]} "
                    f"({top_products[0][1]:.0f} units)."
                ),
                recommendation=(
                    "Consider tightening upper inventory bounds (U) for "
                    "over-stocked products, or investigate whether demand "
                    "forecasts are too conservative."
                ),
                affected_products=[p for p, _ in top_products],
                affected_warehouses=[w for w, _ in top_warehouses],
                metric_name="total_overstock",
                metric_value=total_os,
                metadata={
                    "overstock_by_product": {p: v for p, v in top_products},
                },
            )
        )

        return insights

    # ------------------------------------------------------------------ #
    #  Rule 5: Shortage                                                  #
    # ------------------------------------------------------------------ #

    def _check_shortage(
        self,
        kpis: Dict[str, float],
        results: List[Dict[str, Any]],
        thresholds: Dict[str, float],
    ) -> List[Insight]:
        insights: List[Insight] = []
        total_shortage = kpis.get("total_shortage", 0.0)
        if total_shortage == 0:
            return insights

        # Find which products/warehouses are short
        shortage_products: Dict[str, float] = defaultdict(float)
        for r in results:
            sq = r.get("shortage_qty", 0)
            if sq > 0:
                shortage_products[r.get("product_id", "")] += sq

        top = sorted(shortage_products.items(), key=lambda x: x[1], reverse=True)[:5]

        insights.append(
            Insight(
                insight_id=self._id("SHORT"),
                severity=InsightSeverity.WARNING,
                category=InsightCategory.SHORTAGE,
                title=f"Shortage of {total_shortage:.0f} units detected",
                description=(
                    f"Total shortage across {len(shortage_products)} products. "
                    "Shortages indicate inventory fell below the lower bound."
                ),
                recommendation=(
                    "Increase safety stock lower bounds (L) or review "
                    "replenishment frequency for affected products."
                ),
                affected_products=[p for p, _ in top],
                metric_name="total_shortage",
                metric_value=total_shortage,
            )
        )

        return insights

    # ------------------------------------------------------------------ #
    #  Rule 6: Penalty Flags                                             #
    # ------------------------------------------------------------------ #

    def _check_penalty_flags(
        self,
        kpis: Dict[str, float],
        results: List[Dict[str, Any]],
        thresholds: Dict[str, float],
    ) -> List[Insight]:
        insights: List[Insight] = []
        total_penalty = kpis.get("total_penalty", 0.0)
        if total_penalty == 0:
            return insights

        penalty_records = [r for r in results if r.get("penalty_flag", False)]
        penalty_products = set(r.get("product_id", "") for r in penalty_records)
        penalty_warehouses = set(r.get("warehouse_id", "") for r in penalty_records)

        severity = (
            InsightSeverity.CRITICAL if total_penalty > 10
            else InsightSeverity.WARNING
        )

        insights.append(
            Insight(
                insight_id=self._id("PENALTY"),
                severity=severity,
                category=InsightCategory.PENALTY,
                title=f"{int(total_penalty)} penalty flags triggered",
                description=(
                    f"{int(total_penalty)} product-warehouse-period combinations "
                    f"triggered penalty flags across {len(penalty_products)} products "
                    f"and {len(penalty_warehouses)} warehouses."
                ),
                recommendation=(
                    "Penalty flags indicate case-pack constraints could not be "
                    "fully satisfied. Review case-pack sizes (CP) and consider "
                    "allowing residual units or adjusting pack configurations."
                ),
                affected_products=sorted(penalty_products),
                affected_warehouses=sorted(penalty_warehouses),
                metric_name="total_penalty",
                metric_value=total_penalty,
            )
        )

        return insights

    # ------------------------------------------------------------------ #
    #  Rule 7: Cost Driver Identification                                #
    # ------------------------------------------------------------------ #

    def _check_cost_drivers(
        self,
        kpis: Dict[str, float],
        results: List[Dict[str, Any]],
        thresholds: Dict[str, float],
    ) -> List[Insight]:
        """Identify the dominant cost component and flag if one category
        dominates (>50% of total cost)."""
        insights: List[Insight] = []
        total_cost = kpis.get("total_cost", 0.0)
        if total_cost <= 0:
            return insights

        # Approximate cost components from KPIs
        # The exact per-component cost would require re-calculation; use proportional estimates
        cost_components: Dict[str, float] = {}

        # Use backorder/overstock/shortage/penalty quantities as proxies
        # A more precise approach would sum cost_param * qty; we use what is available
        bo = kpis.get("total_backorder", 0.0)
        os_qty = kpis.get("total_overstock", 0.0)
        sh = kpis.get("total_shortage", 0.0)
        pn = kpis.get("total_penalty", 0.0)

        total_qty = bo + os_qty + sh + pn
        if total_qty == 0:
            return insights

        # Build component shares
        cost_components["backorder"] = bo / total_qty * total_cost if total_qty else 0
        cost_components["overstock"] = os_qty / total_qty * total_cost if total_qty else 0
        cost_components["shortage"] = sh / total_qty * total_cost if total_qty else 0
        cost_components["penalty"] = pn / total_qty * total_cost if total_qty else 0

        dominant = max(cost_components.items(), key=lambda x: x[1])
        dominant_name, dominant_cost = dominant
        dominant_share = dominant_cost / total_cost * 100 if total_cost else 0

        if dominant_share > 50:
            insights.append(
                Insight(
                    insight_id=self._id("COST-DRIVER"),
                    severity=InsightSeverity.INFO,
                    category=InsightCategory.COST,
                    title=f"Dominant cost driver: {dominant_name} ({dominant_share:.0f}% of total)",
                    description=(
                        f"The {dominant_name} cost component accounts for approximately "
                        f"{dominant_share:.0f}% of the total cost ({total_cost:.0f}). "
                        "Reducing this component would have the greatest impact."
                    ),
                    recommendation=(
                        f"Focus optimization efforts on reducing {dominant_name}. "
                        f"Use sensitivity analysis on the associated cost parameter "
                        f"to quantify potential savings."
                    ),
                    metric_name="total_cost",
                    metric_value=total_cost,
                    metadata={
                        "cost_breakdown": cost_components,
                        "dominant_component": dominant_name,
                        "dominant_share_pct": round(dominant_share, 1),
                    },
                )
            )

        return insights

    # ------------------------------------------------------------------ #
    #  Rule 8: Inventory Imbalance Across Warehouses                     #
    # ------------------------------------------------------------------ #

    def _check_inventory_imbalance(
        self,
        kpis: Dict[str, float],
        results: List[Dict[str, Any]],
        thresholds: Dict[str, float],
    ) -> List[Insight]:
        """Detect if some warehouses are consistently overstocked while
        others are back-ordered for the same products."""
        insights: List[Insight] = []
        if not results:
            return insights

        # Build per-product, per-warehouse signals
        product_warehouse_bo: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        product_warehouse_os: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for r in results:
            pid = r.get("product_id", "")
            wid = r.get("warehouse_id", "")
            bo = r.get("backorder_qty", 0)
            os_qty = r.get("overstock_qty", 0)
            if bo > 0:
                product_warehouse_bo[pid][wid] += bo
            if os_qty > 0:
                product_warehouse_os[pid][wid] += os_qty

        # For each product, check if it is back-ordered at some warehouses
        # and simultaneously overstocked at others
        imbalanced_products: List[str] = []
        for pid in product_warehouse_bo:
            bo_warehouses = set(product_warehouse_bo[pid].keys())
            os_warehouses = set(product_warehouse_os.get(pid, {}).keys())
            if bo_warehouses and os_warehouses and bo_warehouses != os_warehouses:
                imbalanced_products.append(pid)

        if not imbalanced_products:
            return insights

        insights.append(
            Insight(
                insight_id=self._id("INV-IMBAL"),
                severity=InsightSeverity.OPPORTUNITY,
                category=InsightCategory.INVENTORY,
                title=f"Inventory imbalance detected for {len(imbalanced_products)} product(s)",
                description=(
                    f"Products {imbalanced_products[:5]} are simultaneously overstocked "
                    "at some warehouses and back-ordered at others. "
                    "Lateral redistribution could reduce both backorders and overstock."
                ),
                recommendation=(
                    "Evaluate inter-warehouse transfer options to rebalance "
                    "inventory. This may reduce total cost without additional production."
                ),
                affected_products=imbalanced_products[:10],
                metric_name="inventory_imbalance_count",
                metric_value=float(len(imbalanced_products)),
            )
        )

        return insights

    # ------------------------------------------------------------------ #
    #  Helpers                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _id(prefix: str) -> str:
        """Generate a short unique insight ID with a human-readable prefix."""
        short_uuid = uuid.uuid4().hex[:8]
        return f"{prefix}-{short_uuid}"
