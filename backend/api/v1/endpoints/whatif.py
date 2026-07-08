"""
What-If scenario endpoints.
Provides scenario templates, what-if creation/execution,
and side-by-side run comparison.
"""
import json
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db_nds, get_csv_data
from backend.data_access.csv_repository import CsvOptimizationDataRepository
from backend.data_access.repositories import (
    ResultRepository,
    ScenarioRepository,
)
from backend.data_access.models_nds import (
    WhatIfScenario,
    OptimizationRun,
    DssKPI,
)
from backend.domain.services import OptimizationService
from backend.domain.whatif_service import WhatIfService
from backend.schemas.whatif import (
    ScenarioType,
    ScenarioTemplate,
    WhatIfCreate,
    WhatIfKPIs,
    WhatIfResponse,
    WhatIfComparison,
    KPIDelta,
)

router = APIRouter()

# Singleton service instance
_whatif_svc = WhatIfService()


# ================================================================== #
#  Template catalogue                                                  #
# ================================================================== #

_TEMPLATES: List[ScenarioTemplate] = [
    ScenarioTemplate(
        scenario_type=ScenarioType.DEMAND_SURGE,
        display_name="Demand Surge",
        description="Increase demand (DI) by a multiplicative factor",
        affected_parameters=["DI"],
        default_overrides={"factor": 1.2, "products": [], "periods": []},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.DEMAND_DROP,
        display_name="Demand Drop",
        description="Decrease demand (DI) by a multiplicative factor",
        affected_parameters=["DI"],
        default_overrides={"factor": 0.8, "products": [], "periods": []},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.CAPACITY_DISRUPTION,
        display_name="Capacity Disruption",
        description="Reduce firm capacity (CAP) to simulate supply disruption",
        affected_parameters=["CAP"],
        default_overrides={"factor": 0.5, "products": [], "periods": []},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.CAPACITY_EXPANSION,
        display_name="Capacity Expansion",
        description="Increase firm capacity (CAP) to evaluate expansion benefits",
        affected_parameters=["CAP"],
        default_overrides={"factor": 1.5, "products": [], "periods": []},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.COST_INCREASE,
        display_name="Cost Increase",
        description="Increase all cost parameters (Cb, Co, Cs, Cp) by a factor",
        affected_parameters=["Cb", "Co", "Cs", "Cp"],
        default_overrides={"factor": 1.2},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.COST_DECREASE,
        display_name="Cost Decrease",
        description="Decrease all cost parameters (Cb, Co, Cs, Cp) by a factor",
        affected_parameters=["Cb", "Co", "Cs", "Cp"],
        default_overrides={"factor": 0.8},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.SAFETY_STOCK_TIGHTEN,
        display_name="Safety Stock Tighten",
        description="Narrow the upper-lower inventory bounds (U/L gap)",
        affected_parameters=["U", "L"],
        default_overrides={"factor": 0.5, "products": [], "warehouses": []},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.SAFETY_STOCK_LOOSEN,
        display_name="Safety Stock Loosen",
        description="Widen the upper-lower inventory bounds (U/L gap)",
        affected_parameters=["U", "L"],
        default_overrides={"factor": 1.5, "products": [], "warehouses": []},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.NEW_PRODUCT_INTRODUCTION,
        display_name="New Product Introduction",
        description="Add a new product to the optimization model",
        affected_parameters=["I", "DI", "CAP", "BI", "CP", "U", "L", "Cb", "Co", "Cs", "Cp"],
        default_overrides={
            "new_product_id": "NEW_PROD",
            "bi_values": {},
            "cp_values": {},
            "di_values": {},
            "cap_values": {},
        },
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.WAREHOUSE_CLOSURE,
        display_name="Warehouse Closure",
        description="Simulate closing one or more warehouses",
        affected_parameters=["DI", "U", "L"],
        default_overrides={"warehouses": [], "redistribute": False},
    ),
    ScenarioTemplate(
        scenario_type=ScenarioType.CUSTOM,
        display_name="Custom Scenario",
        description="Apply arbitrary parameter overrides via explicit key-value pairs",
        affected_parameters=[],
        default_overrides={"parameter_overrides": {}},
    ),
]


# ================================================================== #
#  1. GET /templates                                                   #
# ================================================================== #

@router.get("/templates", response_model=List[ScenarioTemplate])
def get_whatif_templates():
    """
    Get available what-if analysis templates.

    Each template describes a scenario type, the parameters it modifies,
    and its default override values.
    """
    return _TEMPLATES


# ================================================================== #
#  2. POST / -- Create and execute a what-if scenario                  #
# ================================================================== #

def _run_whatif_task(whatif_id: int, request_dict: dict, data_dir: str):
    """
    Background worker for a what-if scenario.

    Solves the modified problem via the MA solver and persists the run,
    KPIs, detailed rows and the extended summary. Updates the WhatIfScenario
    record status to "completed" / "failed".
    """
    from backend.core.database import SessionLocalNDS
    from backend.data_access.csv_repository import CsvOptimizationDataRepository as Repo
    from backend.schemas.whatif import WhatIfCreate as Req

    db = SessionLocalNDS()
    whatif = db.query(WhatIfScenario).filter(
        WhatIfScenario.whatif_id == whatif_id
    ).first()
    try:
        request = Req(**request_dict)
        csv_repo = Repo(data_dir)
        base_input = csv_repo.get_optimization_input()

        # Fetch base KPIs from the latest run of the base scenario
        latest_run = (
            db.query(OptimizationRun)
            .filter(OptimizationRun.scenario_id == request.base_scenario_id)
            .order_by(OptimizationRun.run_time.desc())
            .first()
        )
        base_kpis = None
        base_objective = None
        if latest_run:
            base_kpis = ResultRepository(db).get_kpis(latest_run.run_id)
            base_objective = float(latest_run.objective_value or 0)

        whatif_response, whatif_output, whatif_plt_rows = _whatif_svc.run_whatif(
            base_data=base_input,
            request=request,
            base_kpis=base_kpis,
            base_objective=base_objective,
            data_dir=data_dir,
        )

        result_repo = ResultRepository(db)
        run_id = result_repo.save_optimization_run(
            scenario_id=request.base_scenario_id,
            solver_status=whatif_response.solver_status,
            solve_time=whatif_response.solve_time_seconds,
            objective_value=whatif_response.objective_value,
            mip_gap=0.0,
        )

        kpi_dict = {
            "total_cost": whatif_response.kpis.total_cost,
            "total_backorder": whatif_response.kpis.total_backorder,
            "total_overstock": whatif_response.kpis.total_overstock,
            "total_shortage": whatif_response.kpis.total_shortage,
            "total_penalty": whatif_response.kpis.total_penalty,
            "cost_backorder": whatif_response.kpis.cost_backorder,
            "cost_overstock": whatif_response.kpis.cost_overstock,
            "cost_shortage":  whatif_response.kpis.cost_shortage,
            "cost_penalty":   whatif_response.kpis.cost_penalty,
            "service_level": whatif_response.kpis.service_level,
            "capacity_utilization": whatif_response.kpis.capacity_utilization,
        }
        result_repo.save_kpis(run_id, kpi_dict)
        result_repo.save_results(run_id, whatif_output)
        if whatif_plt_rows:
            result_repo.save_plt_transfers(run_id, whatif_plt_rows)

        result_repo.save_run_summary(
            run_id=run_id,
            baseline_cost=whatif_response.baseline_cost,
            opt_cost=whatif_response.ma_inv_cost,
            savings=whatif_response.savings,
            savings_pct=whatif_response.savings_pct,
            n_changes=whatif_response.n_changes,
            si_mean=whatif_response.si_mean,
            ss_below_count=whatif_response.ss_below_count,
        )

        if whatif:
            whatif.run_id = run_id
            whatif.status = "completed"
            db.commit()

    except Exception as e:
        if whatif:
            whatif.status = f"failed: {str(e)[:200]}"
            db.commit()
    finally:
        db.close()


@router.post("/", status_code=202)
def create_whatif(
    request: WhatIfCreate,
    background_tasks: BackgroundTasks,
    db_nds: Session = Depends(get_db_nds),
    csv_repo: CsvOptimizationDataRepository = Depends(get_csv_data),
):
    """
    Create a what-if scenario and run it in the background.

    Returns immediately with the whatif_id and status "running".
    Poll GET /whatif/{whatif_id}/status for completion.
    """
    # Verify scenario exists
    scenario_repo = ScenarioRepository(db_nds)
    scenario = scenario_repo.get_scenario(request.base_scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Persist what-if record (status=running); store label inside overrides JSON
    overrides_with_label = dict(request.overrides)
    if request.label:
        overrides_with_label["label"] = request.label
    whatif = WhatIfScenario(
        scenario_id=request.base_scenario_id,
        whatif_type=request.scenario_type.value,
        parameter_overrides=json.dumps(overrides_with_label),
        status="running",
    )
    db_nds.add(whatif)
    db_nds.commit()
    db_nds.refresh(whatif)

    background_tasks.add_task(
        _run_whatif_task,
        whatif_id=whatif.whatif_id,
        request_dict=request.model_dump(mode="json"),
        data_dir=str(csv_repo._dir),
    )

    return {
        "whatif_id": whatif.whatif_id,
        "status": "running",
        "message": "What-if analysis started. Poll /whatif/{whatif_id}/status for progress.",
    }


# ================================================================== #
#  2b. GET /{whatif_id}/status -- Poll a what-if job                   #
# ================================================================== #

@router.get("/{whatif_id}/status")
def get_whatif_status(whatif_id: int, db: Session = Depends(get_db_nds)):
    """Poll a what-if job. Returns status, and run_id + objective when completed."""
    from datetime import datetime, timedelta

    whatif = db.query(WhatIfScenario).filter(
        WhatIfScenario.whatif_id == whatif_id
    ).first()
    if not whatif:
        raise HTTPException(status_code=404, detail="What-if scenario not found")

    status = whatif.status or "running"

    # Phát hiện job kẹt: nếu vẫn "running" quá lâu (backend restart/crash giữa
    # chừng) thì đánh dấu failed, tránh frontend poll vô hạn.
    if status == "running" and whatif.created_at:
        if datetime.utcnow() - whatif.created_at > timedelta(hours=2):
            status = "failed: timed out / interrupted"
            whatif.status = status
            db.commit()

    is_done = status not in ("running", "pending")

    payload = {
        "whatif_id": whatif_id,
        "status": status,
        "is_done": is_done,
        "run_id": whatif.run_id,
    }
    if whatif.run_id:
        run = db.query(OptimizationRun).filter(
            OptimizationRun.run_id == whatif.run_id
        ).first()
        if run:
            payload["objective_value"] = float(run.objective_value or 0)
            payload["solver_status"] = run.solver_status
    return payload


# ================================================================== #
#  3. GET /compare -- Side-by-side run comparison                      #
# ================================================================== #

class CompareRequest(BaseModel):
    """Query parameters wrapped as a schema for documentation."""
    base_run_id: int = Field(..., description="Run ID of the base scenario")
    compare_run_id: int = Field(..., description="Run ID of the what-if scenario")


@router.get("/compare", response_model=WhatIfComparison)
def compare_runs(
    base_run_id: int,
    compare_run_id: int,
    db: Session = Depends(get_db_nds),
):
    """
    Compare KPIs between two optimization runs side by side.

    Returns per-KPI deltas (absolute and percentage) and a
    human-readable textual summary of the differences.
    """
    # Load both runs
    base_run = db.query(OptimizationRun).filter(
        OptimizationRun.run_id == base_run_id
    ).first()
    if not base_run:
        raise HTTPException(
            status_code=404, detail=f"Base run {base_run_id} not found"
        )

    compare_run = db.query(OptimizationRun).filter(
        OptimizationRun.run_id == compare_run_id
    ).first()
    if not compare_run:
        raise HTTPException(
            status_code=404, detail=f"Compare run {compare_run_id} not found"
        )

    # Load KPIs
    base_kpi = db.query(DssKPI).filter(DssKPI.run_id == base_run_id).first()
    compare_kpi = db.query(DssKPI).filter(DssKPI.run_id == compare_run_id).first()

    def _kpi_to_dict(kpi) -> Dict[str, float]:
        if not kpi:
            return {}
        return {
            "total_cost": float(kpi.total_cost or 0),
            "total_backorder": float(kpi.total_backorder or 0),
            "total_overstock": float(kpi.total_overstock or 0),
            "total_shortage": float(kpi.total_shortage or 0),
            "total_penalty": float(kpi.total_penalty or 0),
            "service_level": float(kpi.service_level or 0),
            "capacity_utilization": float(kpi.capacity_utilization or 0),
        }

    base_dict = _kpi_to_dict(base_kpi)
    compare_dict = _kpi_to_dict(compare_kpi)

    # Build deltas
    deltas: List[KPIDelta] = []
    summary_parts: List[str] = []

    kpi_names = [
        "total_cost", "total_backorder", "total_overstock",
        "total_shortage", "total_penalty", "service_level",
        "capacity_utilization",
    ]

    for name in kpi_names:
        base_val = base_dict.get(name, 0.0)
        comp_val = compare_dict.get(name, 0.0)
        abs_change = comp_val - base_val
        pct_change = (
            round((abs_change / base_val) * 100, 2)
            if base_val != 0
            else None
        )
        deltas.append(
            KPIDelta(
                kpi_name=name,
                base_value=base_val,
                whatif_value=comp_val,
                absolute_change=abs_change,
                percent_change=pct_change,
            )
        )
        if pct_change is not None and abs(pct_change) >= 1.0:
            direction = "increases" if pct_change > 0 else "decreases"
            summary_parts.append(
                f"{name} {direction} by {abs(pct_change):.1f}%"
            )

    summary = (
        "; ".join(summary_parts)
        if summary_parts
        else "No significant KPI changes."
    )

    # Determine what-if type from WhatIfScenario table if available
    whatif_record = (
        db.query(WhatIfScenario)
        .filter(WhatIfScenario.run_id == compare_run_id)
        .first()
    )
    scenario_type = ScenarioType.CUSTOM
    label = ""
    whatif_id = 0
    if whatif_record:
        try:
            scenario_type = ScenarioType(whatif_record.whatif_type)
        except ValueError:
            scenario_type = ScenarioType.CUSTOM
        label = whatif_record.whatif_type
        whatif_id = whatif_record.whatif_id

    return WhatIfComparison(
        base_scenario_id=base_run.scenario_id,
        whatif_id=whatif_id,
        scenario_type=scenario_type,
        label=label,
        deltas=deltas,
        summary=summary,
    )


# ================================================================== #
#  4. GET /history -- List all what-if scenario runs                   #
# ================================================================== #

class WhatIfHistoryItem(BaseModel):
    whatif_id: int
    scenario_id: int
    whatif_type: str
    label: str = ""
    status: str
    run_id: Optional[int] = None
    objective_value: Optional[float] = None
    solver_status: Optional[str] = None
    created_at: Optional[str] = None


class WhatIfHistoryResponse(BaseModel):
    scenarios: List[WhatIfHistoryItem]
    total: int


@router.get("/history", response_model=WhatIfHistoryResponse)
def get_whatif_history(
    limit: int = 50,
    db: Session = Depends(get_db_nds),
):
    """
    List all what-if scenario runs with their status and results.
    """
    records = (
        db.query(WhatIfScenario)
        .order_by(WhatIfScenario.created_at.desc())
        .limit(limit)
        .all()
    )

    items = []
    for w in records:
        run = None
        if w.run_id:
            run = db.query(OptimizationRun).filter(OptimizationRun.run_id == w.run_id).first()

        # Try to extract label from parameter_overrides JSON
        label = ""
        if w.parameter_overrides:
            try:
                overrides = json.loads(w.parameter_overrides)
                label = overrides.get("label", "")
            except Exception:
                pass

        items.append(WhatIfHistoryItem(
            whatif_id=w.whatif_id,
            scenario_id=w.scenario_id,
            whatif_type=w.whatif_type,
            label=label,
            status=w.status or "unknown",
            run_id=w.run_id,
            objective_value=float(run.objective_value) if run and run.objective_value else None,
            solver_status=run.solver_status if run else None,
            created_at=w.created_at.isoformat() if w.created_at else None,
        ))

    return WhatIfHistoryResponse(scenarios=items, total=len(items))
