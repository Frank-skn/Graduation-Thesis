"""
Insights generation endpoints.
Produces rule-based decision insights and recommendations
by examining KPIs and per-record optimization results.
"""
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db_nds
from backend.data_access.models_nds import (
    OptimizationRun,
    OptimizationResult,
    DssKPI,
)
from backend.domain.insights_service import InsightsService
from backend.schemas.insights import (
    InsightsRequest,
    InsightsResponse,
)

router = APIRouter()

# Singleton service instance
_insights_svc = InsightsService()


# ================================================================== #
#  1. GET /{run_id} -- Generate insights for a run                     #
# ================================================================== #

@router.get("/{run_id}", response_model=InsightsResponse)
def generate_insights_for_run(
    run_id: int,
    db: Session = Depends(get_db_nds),
):
    """
    Generate actionable decision insights for an optimization run.

    Loads KPIs and detailed results from the database, then runs
    the rule-based insight engine to identify:

    - Service-level issues (critical / warning)
    - Capacity utilization concerns
    - Cost-driver identification
    - Backorder patterns and persistence
    - Overstock concentrations
    - Shortage detection
    - Penalty-flag accumulation
    - Inventory imbalance across warehouses
    """
    # Verify run exists
    run = db.query(OptimizationRun).filter(
        OptimizationRun.run_id == run_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Load KPIs
    kpi = db.query(DssKPI).filter(DssKPI.run_id == run_id).first()
    if not kpi:
        raise HTTPException(
            status_code=404,
            detail="KPIs not found for this run. Run optimization first.",
        )

    kpi_dict: Dict[str, float] = {
        "total_cost": float(kpi.total_cost or 0),
        "total_backorder": float(kpi.total_backorder or 0),
        "total_overstock": float(kpi.total_overstock or 0),
        "total_shortage": float(kpi.total_shortage or 0),
        "total_penalty": float(kpi.total_penalty or 0),
        "service_level": float(kpi.service_level or 0),
        "capacity_utilization": float(kpi.capacity_utilization or 0),
    }

    # Load detailed results for deeper analysis
    result_rows = db.query(OptimizationResult).filter(
        OptimizationResult.run_id == run_id
    ).all()

    results_list: List[Dict[str, Any]] = [
        {
            "product_id": r.product_id,
            "warehouse_id": r.warehouse_id,
            "time_period": r.time_period,
            "q_case_pack": r.q_case_pack,
            "r_residual_units": r.r_residual_units,
            "net_inventory": float(r.net_inventory or 0),
            "backorder_qty": float(r.backorder_qty or 0),
            "overstock_qty": float(r.overstock_qty or 0),
            "shortage_qty": float(r.shortage_qty or 0),
            "penalty_flag": r.penalty_flag or False,
        }
        for r in result_rows
    ]

    # Build InsightsRequest and generate
    request = InsightsRequest(
        scenario_id=run.scenario_id,
        run_id=run_id,
        kpis=kpi_dict,
        results=results_list,
    )

    return _insights_svc.generate(request)


# ================================================================== #
#  2. POST / -- Generate insights with custom thresholds               #
# ================================================================== #

@router.post("/", response_model=InsightsResponse)
def generate_insights_custom(
    request: InsightsRequest,
    db: Session = Depends(get_db_nds),
):
    """
    Generate insights using a custom InsightsRequest payload.

    Allows the caller to supply their own KPIs, results, and
    configurable thresholds (e.g. different service-level targets)
    instead of loading from the database.

    If `run_id` is provided in the request, the endpoint will
    load results from the database and merge with any supplied data.
    """
    # If run_id is provided but no results, load from DB
    if request.run_id and not request.results:
        run = db.query(OptimizationRun).filter(
            OptimizationRun.run_id == request.run_id
        ).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Load KPIs if not supplied
        if not request.kpis:
            kpi = db.query(DssKPI).filter(
                DssKPI.run_id == request.run_id
            ).first()
            if kpi:
                request.kpis = {
                    "total_cost": float(kpi.total_cost or 0),
                    "total_backorder": float(kpi.total_backorder or 0),
                    "total_overstock": float(kpi.total_overstock or 0),
                    "total_shortage": float(kpi.total_shortage or 0),
                    "total_penalty": float(kpi.total_penalty or 0),
                    "service_level": float(kpi.service_level or 0),
                    "capacity_utilization": float(kpi.capacity_utilization or 0),
                }

        # Load results
        result_rows = db.query(OptimizationResult).filter(
            OptimizationResult.run_id == request.run_id
        ).all()
        request.results = [
            {
                "product_id": r.product_id,
                "warehouse_id": r.warehouse_id,
                "time_period": r.time_period,
                "q_case_pack": r.q_case_pack,
                "r_residual_units": r.r_residual_units,
                "net_inventory": float(r.net_inventory or 0),
                "backorder_qty": float(r.backorder_qty or 0),
                "overstock_qty": float(r.overstock_qty or 0),
                "shortage_qty": float(r.shortage_qty or 0),
                "penalty_flag": r.penalty_flag or False,
            }
            for r in result_rows
        ]

    return _insights_svc.generate(request)
