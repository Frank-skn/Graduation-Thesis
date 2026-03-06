"""
Result analysis endpoints.
Provides executive summary, allocation detail, and inventory-dynamics
views for optimization runs stored in the NDS schema.
"""
from collections import defaultdict
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db_nds
from backend.data_access.models_nds import (
    OptimizationRun,
    OptimizationResult,
    DssKPI,
)

router = APIRouter()


# ================================================================== #
#  Response schemas                                                    #
# ================================================================== #

class RunMetadata(BaseModel):
    """Optimisation-run metadata."""
    run_id: int
    scenario_id: int
    run_time: Optional[str] = None
    solver_status: str
    solve_time_seconds: float
    objective_value: float
    mip_gap: float


class KPIDetail(BaseModel):
    """Full KPI breakdown."""
    total_cost: float = 0
    total_backorder: float = 0
    total_overstock: float = 0
    total_shortage: float = 0
    total_penalty: float = 0
    service_level: float = 0
    capacity_utilization: float = 0


class ExecutiveSummary(BaseModel):
    """Executive summary combining run metadata, KPIs, and counts."""
    run: RunMetadata
    kpis: KPIDetail
    result_count: int = 0
    product_count: int = 0
    warehouse_count: int = 0
    period_count: int = 0


class AllocationRecord(BaseModel):
    """Single allocation row."""
    product_id: str
    warehouse_id: str
    time_period: int
    q_case_pack: int
    r_residual_units: int
    net_inventory: float
    backorder_qty: float
    overstock_qty: float
    shortage_qty: float
    penalty_flag: bool


class AllocationResponse(BaseModel):
    """Paged allocation list with applied filters."""
    run_id: int
    allocations: List[AllocationRecord]
    total: int
    filters_applied: Dict[str, Any] = {}


class InventoryPoint(BaseModel):
    """Single time-period data point in an inventory time-series."""
    time_period: int
    net_inventory: float
    backorder_qty: float
    overstock_qty: float
    shortage_qty: float
    q_case_pack: int
    r_residual_units: int


class WarehouseSeries(BaseModel):
    """Time-series for one warehouse."""
    warehouse_id: str
    data_points: List[InventoryPoint]


class ProductDynamics(BaseModel):
    """Inventory dynamics for one product across warehouses."""
    product_id: str
    warehouses: List[WarehouseSeries]


class InventoryDynamicsResponse(BaseModel):
    """Inventory dynamics grouped by product and warehouse."""
    run_id: int
    dynamics: List[ProductDynamics]


# ================================================================== #
#  Helper                                                              #
# ================================================================== #

def _load_run(run_id: int, db: Session) -> OptimizationRun:
    """Load an OptimizationRun or raise 404."""
    run = db.query(OptimizationRun).filter(
        OptimizationRun.run_id == run_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ================================================================== #
#  1. GET /{run_id}/executive-summary                                  #
# ================================================================== #

@router.get("/{run_id}/executive-summary", response_model=ExecutiveSummary)
def get_executive_summary(
    run_id: int,
    db: Session = Depends(get_db_nds),
):
    """
    Get executive summary for an optimization run.

    Includes run metadata, KPI breakdown, and high-level counts
    of products, warehouses, and time periods in the result set.
    """
    run = _load_run(run_id, db)

    kpi = db.query(DssKPI).filter(DssKPI.run_id == run_id).first()

    results = db.query(OptimizationResult).filter(
        OptimizationResult.run_id == run_id
    ).all()

    products = set()
    warehouses = set()
    periods = set()
    for r in results:
        products.add(r.product_id)
        warehouses.add(r.warehouse_id)
        periods.add(r.time_period)

    run_meta = RunMetadata(
        run_id=run.run_id,
        scenario_id=run.scenario_id,
        run_time=str(run.run_time) if run.run_time else None,
        solver_status=run.solver_status or "unknown",
        solve_time_seconds=float(run.solve_time_seconds or 0),
        objective_value=float(run.objective_value or 0),
        mip_gap=float(run.mip_gap or 0),
    )

    kpi_detail = KPIDetail()
    if kpi:
        kpi_detail = KPIDetail(
            total_cost=float(kpi.total_cost or 0),
            total_backorder=float(kpi.total_backorder or 0),
            total_overstock=float(kpi.total_overstock or 0),
            total_shortage=float(kpi.total_shortage or 0),
            total_penalty=float(kpi.total_penalty or 0),
            service_level=float(kpi.service_level or 0),
            capacity_utilization=float(kpi.capacity_utilization or 0),
        )

    return ExecutiveSummary(
        run=run_meta,
        kpis=kpi_detail,
        result_count=len(results),
        product_count=len(products),
        warehouse_count=len(warehouses),
        period_count=len(periods),
    )


# ================================================================== #
#  2. GET /{run_id}/allocation                                         #
# ================================================================== #

@router.get("/{run_id}/allocation", response_model=AllocationResponse)
def get_allocation(
    run_id: int,
    product_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    time_period: Optional[int] = None,
    db: Session = Depends(get_db_nds),
):
    """
    Get allocation details for an optimization run.

    Supports optional filtering by product_id, warehouse_id,
    and/or time_period via query parameters.
    """
    _load_run(run_id, db)

    query = db.query(OptimizationResult).filter(
        OptimizationResult.run_id == run_id
    )

    filters: Dict[str, Any] = {}
    if product_id:
        query = query.filter(OptimizationResult.product_id == product_id)
        filters["product_id"] = product_id
    if warehouse_id:
        query = query.filter(OptimizationResult.warehouse_id == warehouse_id)
        filters["warehouse_id"] = warehouse_id
    if time_period is not None:
        query = query.filter(OptimizationResult.time_period == time_period)
        filters["time_period"] = time_period

    results = query.order_by(
        OptimizationResult.product_id,
        OptimizationResult.warehouse_id,
        OptimizationResult.time_period,
    ).all()

    allocations = [
        AllocationRecord(
            product_id=r.product_id,
            warehouse_id=r.warehouse_id,
            time_period=r.time_period,
            q_case_pack=r.q_case_pack,
            r_residual_units=r.r_residual_units,
            net_inventory=float(r.net_inventory or 0),
            backorder_qty=float(r.backorder_qty or 0),
            overstock_qty=float(r.overstock_qty or 0),
            shortage_qty=float(r.shortage_qty or 0),
            penalty_flag=r.penalty_flag or False,
        )
        for r in results
    ]

    return AllocationResponse(
        run_id=run_id,
        allocations=allocations,
        total=len(allocations),
        filters_applied=filters,
    )


# ================================================================== #
#  3. GET /{run_id}/inventory-dynamics                                 #
# ================================================================== #

@router.get(
    "/{run_id}/inventory-dynamics",
    response_model=InventoryDynamicsResponse,
)
def get_inventory_dynamics(
    run_id: int,
    product_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db_nds),
):
    """
    Get inventory dynamics (time-series) for an optimization run.

    Returns data grouped by product and warehouse, sorted by
    time period -- suitable for line-chart visualisation.
    """
    _load_run(run_id, db)

    query = db.query(OptimizationResult).filter(
        OptimizationResult.run_id == run_id
    )

    if product_id:
        query = query.filter(OptimizationResult.product_id == product_id)
    if warehouse_id:
        query = query.filter(OptimizationResult.warehouse_id == warehouse_id)

    results = query.order_by(
        OptimizationResult.product_id,
        OptimizationResult.warehouse_id,
        OptimizationResult.time_period,
    ).all()

    # Group: product -> warehouse -> [time-series points]
    grouped: Dict[str, Dict[str, List[InventoryPoint]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in results:
        grouped[r.product_id][r.warehouse_id].append(
            InventoryPoint(
                time_period=r.time_period,
                net_inventory=float(r.net_inventory or 0),
                backorder_qty=float(r.backorder_qty or 0),
                overstock_qty=float(r.overstock_qty or 0),
                shortage_qty=float(r.shortage_qty or 0),
                q_case_pack=r.q_case_pack,
                r_residual_units=r.r_residual_units,
            )
        )

    dynamics: List[ProductDynamics] = []
    for pid in sorted(grouped.keys()):
        warehouse_series = [
            WarehouseSeries(
                warehouse_id=wid,
                data_points=grouped[pid][wid],
            )
            for wid in sorted(grouped[pid].keys())
        ]
        dynamics.append(
            ProductDynamics(product_id=pid, warehouses=warehouse_series)
        )

    return InventoryDynamicsResponse(run_id=run_id, dynamics=dynamics)
