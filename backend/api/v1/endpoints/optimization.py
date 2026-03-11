"""
Optimization execution endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from backend.core.database import get_db_nds, get_csv_data, SessionLocalNDS
from backend.data_access.csv_repository import CsvOptimizationDataRepository
from backend.schemas.optimization import (
    OptimizationRequest,
    OptimizationResponse,
    OptimizationOutput,
    KPISummary
)
from backend.data_access.repositories import (
    ResultRepository,
    ScenarioRepository
)
from backend.data_access.models_nds import (
    OptimizationRun as RunModel,
    OptimizationResult as ResultModel,
    DssKPI,
    DssRunSummary,
    WhatIfScenario,
)
from backend.domain.services import OptimizationService

router = APIRouter()


def _run_optimization_task(
    run_id: int,
    request_dict: dict,
    data_dir: str,
):
    """Background task: solve and update run record in its own DB session."""
    from backend.data_access.csv_repository import CsvOptimizationDataRepository as Repo
    db = SessionLocalNDS()
    try:
        csv_repo = Repo(data_dir)
        opt_input = csv_repo.get_optimization_input()

        opt_service = OptimizationService(
            solver=request_dict["solver"],
            time_limit=request_dict["time_limit"],
            mip_gap=request_dict["mip_gap"],
        )
        result = opt_service.solve(opt_input)

        result_repo = ResultRepository(db)
        # Update run record with final status
        run = db.query(RunModel).filter(RunModel.run_id == run_id).first()
        if run:
            run.solver_status = result.solver_status
            run.solve_time_seconds = result.solve_time
            run.objective_value = result.objective_value
            run.mip_gap = result.mip_gap
            db.commit()

        result_repo.save_results(run_id, result.output)
        result_repo.save_kpis(run_id, result.kpis)
        result_repo.save_run_summary(
            run_id=run_id,
            baseline_cost=result.baseline_cost,
            opt_cost=result.objective_value,
            savings=result.savings,
            savings_pct=result.savings_pct,
            n_changes=result.n_changes,
            si_mean=result.si_mean,
            ss_below_count=result.ss_below_count,
            prop_cost=result.prop_cost,
            savings_vs_prop=result.savings_vs_prop,
            savings_pct_prop=result.savings_pct_prop,
        )

    except Exception as exc:
        run = db.query(RunModel).filter(RunModel.run_id == run_id).first()
        if run:
            run.solver_status = f"error: {str(exc)[:200]}"
            db.commit()
    finally:
        db.close()


@router.post("/run", response_model=OptimizationResponse)
def run_optimization(
    request: OptimizationRequest,
    background_tasks: BackgroundTasks,
    db_nds: Session = Depends(get_db_nds),
    csv_repo: CsvOptimizationDataRepository = Depends(get_csv_data),
):
    """
    Submit optimization job — returns immediately with run_id.
    Poll GET /optimize/runs/{run_id}/status to track progress.
    """
    # Verify scenario exists
    scenario_repo = ScenarioRepository(db_nds)
    scenario = scenario_repo.get_scenario(request.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Create run record immediately with status "running"
    result_repo = ResultRepository(db_nds)
    run_id = result_repo.save_optimization_run(
        scenario_id=request.scenario_id,
        solver_status="running",
        solve_time=0.0,
        objective_value=0.0,
        mip_gap=request.mip_gap,
    )

    # Launch solver in background
    background_tasks.add_task(
        _run_optimization_task,
        run_id=run_id,
        request_dict={
            "solver": request.solver,
            "time_limit": request.time_limit,
            "mip_gap": request.mip_gap,
        },
        data_dir=str(csv_repo._dir),
    )

    return OptimizationResponse(
        run_id=run_id,
        scenario_id=request.scenario_id,
        solver_status="running",
        solve_time_seconds=0.0,
        objective_value=0.0,
        mip_gap=request.mip_gap,
        message="Optimization started in background. Poll /optimize/runs/{run_id}/status for progress."
    )


@router.get("/runs", tags=["Optimization"])
def list_runs(
    db_nds: Session = Depends(get_db_nds),
):
    """
    List all optimization runs ordered by most recent first.
    """
    runs = (
        db_nds.query(RunModel)
        .order_by(RunModel.run_id.desc())
        .all()
    )
    return [
        {
            "run_id": r.run_id,
            "scenario_id": r.scenario_id,
            "run_time": r.run_time.isoformat() if r.run_time else None,
            "solver_status": r.solver_status,
            "objective_value": float(r.objective_value or 0),
            "solve_time_seconds": float(r.solve_time_seconds or 0),
            "mip_gap": float(r.mip_gap or 0),
        }
        for r in runs
    ]


@router.get("/runs/{run_id}/status")
def get_run_status(
    run_id: int,
    db_nds: Session = Depends(get_db_nds),
):
    """Poll optimization run status. Returns current status + result when done."""
    run = db_nds.query(RunModel).filter(RunModel.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    status = run.solver_status or "running"
    is_done = status not in ("running",)

    return {
        "run_id": run_id,
        "solver_status": status,
        "is_done": is_done,
        "objective_value": float(run.objective_value or 0),
        "solve_time_seconds": float(run.solve_time_seconds or 0),
        "mip_gap": float(run.mip_gap or 0),
    }


@router.get("/results/{run_id}", response_model=OptimizationOutput)
def get_results(
    run_id: int,
    db: Session = Depends(get_db_nds)
):
    """
    Get optimization results by run ID
    """
    repo = ResultRepository(db)
    results = repo.get_results(run_id)
    
    if not results:
        raise HTTPException(status_code=404, detail="Results not found")
    
    return results


@router.get("/kpis/{run_id}", response_model=KPISummary)
def get_kpis(
    run_id: int,
    db: Session = Depends(get_db_nds)
):
    """
    Get KPI summary for a run
    """
    repo = ResultRepository(db)
    kpis = repo.get_kpis(run_id)
    
    if not kpis:
        raise HTTPException(status_code=404, detail="KPIs not found")
    
    return KPISummary(run_id=run_id, **kpis)


@router.delete("/runs/{run_id}", status_code=204)
def delete_run(
    run_id: int,
    db_nds: Session = Depends(get_db_nds),
):
    """
    Delete an optimization run and all related data
    (KPIs, results, run summary, what-if references).
    """
    run = db_nds.query(RunModel).filter(RunModel.run_id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Cascade-delete child records in correct order
    db_nds.query(DssRunSummary).filter(DssRunSummary.run_id == run_id).delete()
    db_nds.query(DssKPI).filter(DssKPI.run_id == run_id).delete()
    db_nds.query(ResultModel).filter(ResultModel.run_id == run_id).delete()
    # Detach what-if scenarios that reference this run (don't delete the scenario itself)
    db_nds.query(WhatIfScenario).filter(WhatIfScenario.run_id == run_id).update(
        {"run_id": None, "status": "deleted"}
    )
    db_nds.delete(run)
    db_nds.commit()
    return None
