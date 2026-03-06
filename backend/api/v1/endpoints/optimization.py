"""
Optimization execution endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from backend.core.database import get_db_nds, get_db_dds
from backend.schemas.optimization import (
    OptimizationRequest,
    OptimizationResponse,
    OptimizationOutput,
    KPISummary
)
from backend.data_access.repositories import (
    OptimizationDataRepository,
    ResultRepository,
    ScenarioRepository
)
from backend.domain.services import OptimizationService

router = APIRouter()


@router.post("/run", response_model=OptimizationResponse)
def run_optimization(
    request: OptimizationRequest,
    db_nds: Session = Depends(get_db_nds),
    db_dds: Session = Depends(get_db_dds)
):
    """
    Execute optimization for a scenario
    
    - **scenario_id**: ID of the scenario to optimize
    - **solver**: Solver to use (cbc, glpk)
    - **time_limit**: Maximum solve time in seconds
    - **mip_gap**: MIP gap tolerance
    
    Returns run details and objective value
    """
    # Verify scenario exists
    scenario_repo = ScenarioRepository(db_nds)
    scenario = scenario_repo.get_scenario(request.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Get optimization data
    data_repo = OptimizationDataRepository(db_dds)
    opt_input = data_repo.get_optimization_input()
    
    # Run optimization
    opt_service = OptimizationService(
        solver=request.solver,
        time_limit=request.time_limit,
        mip_gap=request.mip_gap
    )
    
    try:
        result = opt_service.solve(opt_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
    
    # Save results
    result_repo = ResultRepository(db_nds)
    run_id = result_repo.save_optimization_run(
        scenario_id=request.scenario_id,
        solver_status=result.solver_status,
        solve_time=result.solve_time,
        objective_value=result.objective_value,
        mip_gap=result.mip_gap
    )
    
    result_repo.save_results(run_id, result.output)
    result_repo.save_kpis(run_id, result.kpis)
    
    return OptimizationResponse(
        run_id=run_id,
        scenario_id=request.scenario_id,
        solver_status=result.solver_status,
        solve_time_seconds=result.solve_time,
        objective_value=result.objective_value,
        mip_gap=result.mip_gap,
        message=f"Optimization completed with status: {result.solver_status}"
    )


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
