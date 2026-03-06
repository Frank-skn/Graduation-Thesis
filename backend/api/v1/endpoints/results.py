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
    DssRunSummary,
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
    cost_backorder: float = 0
    cost_overstock: float = 0
    cost_shortage:  float = 0
    cost_penalty:   float = 0
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
            cost_backorder=float(kpi.cost_backorder or 0),
            cost_overstock=float(kpi.cost_overstock or 0),
            cost_shortage= float(kpi.cost_shortage  or 0),
            cost_penalty=  float(kpi.cost_penalty   or 0),
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


# ================================================================== #
#  4. GET /{run_id}/summary-extended                                   #
# ================================================================== #

class RunSummaryExtended(BaseModel):
    """Baseline vs optimal cost, savings and SI/SS metrics."""
    run_id: int
    baseline_cost: float = 0
    opt_cost: float = 0
    savings: float = 0
    savings_pct: float = 0
    n_changes: int = 0
    si_mean: float = 0
    ss_below_count: int = 0


@router.get("/{run_id}/summary-extended", response_model=RunSummaryExtended)
def get_summary_extended(run_id: int, db: Session = Depends(get_db_nds)):
    """
    Mở rộng tóm tắt: chi phí cơ sở, tiết kiệm, chỉ số SI/SS.
    Returns baseline vs optimised cost and safety-index metrics.
    """
    _load_run(run_id, db)
    s = db.query(DssRunSummary).filter(DssRunSummary.run_id == run_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Run summary not found. Run optimisation first.")
    return RunSummaryExtended(
        run_id=run_id,
        baseline_cost=float(s.baseline_cost or 0),
        opt_cost=float(s.opt_cost or 0),
        savings=float(s.savings or 0),
        savings_pct=float(s.savings_pct or 0),
        n_changes=int(s.n_changes or 0),
        si_mean=float(s.si_mean or 0),
        ss_below_count=int(s.ss_below_count or 0),
    )


# ================================================================== #
#  5. GET /{run_id}/variables                                          #
# ================================================================== #

class VariableRecord(BaseModel):
    """All 7 model variables for a single (i, j, t) cell."""
    product_id: str
    warehouse_id: str
    time_period: int
    q: int = 0
    r: int = 0
    inv: float = 0
    bo: float = 0
    o: float = 0
    s: float = 0
    p: int = 0


class VariablesResponse(BaseModel):
    run_id: int
    variables: List[VariableRecord]
    total: int


@router.get("/{run_id}/variables", response_model=VariablesResponse)
def get_variables(
    run_id: int,
    product_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db_nds),
):
    """
    Biến quyết định chi tiết (q, r, I, bo, o, s, p) cho mỗi ô (sản phẩm × kho × kỳ).
    """
    _load_run(run_id, db)
    query = db.query(OptimizationResult).filter(OptimizationResult.run_id == run_id)
    if product_id:
        query = query.filter(OptimizationResult.product_id == product_id)
    if warehouse_id:
        query = query.filter(OptimizationResult.warehouse_id == warehouse_id)
    rows = query.order_by(
        OptimizationResult.product_id,
        OptimizationResult.warehouse_id,
        OptimizationResult.time_period,
    ).all()
    records = [
        VariableRecord(
            product_id=r.product_id,
            warehouse_id=r.warehouse_id,
            time_period=r.time_period,
            q=r.q_case_pack or 0,
            r=r.r_residual_units or 0,
            inv=float(r.net_inventory or 0),
            bo=float(r.backorder_qty or 0),
            o=float(r.overstock_qty or 0),
            s=float(r.shortage_qty or 0),
            p=1 if r.penalty_flag else 0,
        )
        for r in rows
    ]
    return VariablesResponse(run_id=run_id, variables=records, total=len(records))


# ================================================================== #
#  6. GET /{run_id}/si-ss                                             #
# ================================================================== #

class SiSsRecord(BaseModel):
    product_id: str
    warehouse_id: str
    time_period: int
    inv: float = 0
    si: float = 0          # Safety Index = inv / max(L, 1)
    ss_level: float = 0    # Safety Stock threshold = L value (stored as net_inventory floor)
    below_ss: bool = False  # inv < ss_level


class SiSsResponse(BaseModel):
    run_id: int
    records: List[SiSsRecord]
    si_mean: float
    ss_below_count: int
    total: int


@router.get("/{run_id}/si-ss", response_model=SiSsResponse)
def get_si_ss(
    run_id: int,
    product_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db_nds),
):
    """
    Chỉ số an toàn (SI) và tồn kho an toàn (SS) cho từng ô (i, j, t).
    SI = tồn kho / max(ngưỡng dưới, 1).  SI < 1 → dưới ngưỡng an toàn.
    """
    _load_run(run_id, db)
    query = db.query(OptimizationResult).filter(OptimizationResult.run_id == run_id)
    if product_id:
        query = query.filter(OptimizationResult.product_id == product_id)
    if warehouse_id:
        query = query.filter(OptimizationResult.warehouse_id == warehouse_id)
    rows = query.order_by(
        OptimizationResult.product_id,
        OptimizationResult.warehouse_id,
        OptimizationResult.time_period,
    ).all()

    # shortage_qty > 0  ↔  inv < L  (the model constraint: s >= L - I)
    records = []
    si_sum = 0.0
    ss_below = 0
    for r in rows:
        inv = float(r.net_inventory or 0)
        s_qty = float(r.shortage_qty or 0)
        # Reconstruct L from shortage: s = max(0, L - inv) → L ≈ inv + s
        l_approx = inv + s_qty if s_qty > 0 else max(inv, 0)
        si = inv / max(l_approx, 1.0)
        below = s_qty > 0
        si_sum += si
        if below:
            ss_below += 1
        records.append(SiSsRecord(
            product_id=r.product_id,
            warehouse_id=r.warehouse_id,
            time_period=r.time_period,
            inv=inv,
            si=round(si, 4),
            ss_level=round(l_approx, 2),
            below_ss=below,
        ))

    si_mean = si_sum / len(records) if records else 0.0
    return SiSsResponse(
        run_id=run_id,
        records=records,
        si_mean=round(si_mean, 4),
        ss_below_count=ss_below,
        total=len(records),
    )


# ================================================================== #
#  7. GET /{run_id}/changes-detail                                     #
# ================================================================== #

class ChangeRecord(BaseModel):
    product_id: str
    warehouse_id: str
    time_period: int
    q: int = 0
    r: int = 0
    inv: float = 0
    shortage_qty: float = 0


class ChangesDetailResponse(BaseModel):
    run_id: int
    changes: List[ChangeRecord]
    total: int


@router.get("/{run_id}/changes-detail", response_model=ChangesDetailResponse)
def get_changes_detail(
    run_id: int,
    product_id: Optional[str] = None,
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db_nds),
):
    """
    Danh sách các ô có hành động thay đổi (p=1 hoặc r>0),
    dùng để theo dõi quyết định phân bổ lẻ.
    """
    _load_run(run_id, db)
    query = (
        db.query(OptimizationResult)
        .filter(OptimizationResult.run_id == run_id)
        .filter(
            (OptimizationResult.penalty_flag == True)
            | (OptimizationResult.r_residual_units > 0)
        )
    )
    if product_id:
        query = query.filter(OptimizationResult.product_id == product_id)
    if warehouse_id:
        query = query.filter(OptimizationResult.warehouse_id == warehouse_id)
    rows = query.order_by(
        OptimizationResult.product_id,
        OptimizationResult.warehouse_id,
        OptimizationResult.time_period,
    ).all()
    changes = [
        ChangeRecord(
            product_id=r.product_id,
            warehouse_id=r.warehouse_id,
            time_period=r.time_period,
            q=r.q_case_pack or 0,
            r=r.r_residual_units or 0,
            inv=float(r.net_inventory or 0),
            shortage_qty=float(r.shortage_qty or 0),
        )
        for r in rows
    ]
    return ChangesDetailResponse(run_id=run_id, changes=changes, total=len(changes))
