"""
Sensitivity analysis endpoints.
Provides one-at-a-time (OAT) parameter sensitivity, result retrieval,
and tornado-chart analysis.
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db_nds, get_db_dds
from backend.data_access.repositories import OptimizationDataRepository
from backend.data_access.models_nds import (
    SensitivityRun,
    OptimizationRun,
)
from backend.domain.services import OptimizationService
from backend.domain.sensitivity_service import SensitivityService
from backend.schemas.sensitivity import (
    SensitivityRequest,
    SensitivityResult,
    TornadoRequest,
    TornadoResult,
)

router = APIRouter()

# Singleton service instance
_sensitivity_svc = SensitivityService()


# ================================================================== #
#  1. POST /run -- One-at-a-time sensitivity analysis                  #
# ================================================================== #

@router.post("/run", response_model=SensitivityResult, status_code=201)
def run_sensitivity(
    request: SensitivityRequest,
    db_nds: Session = Depends(get_db_nds),
    db_dds: Session = Depends(get_db_dds),
):
    """
    Run one-at-a-time sensitivity analysis on a single parameter.

    For each variation percentage the specified parameter is scaled,
    the optimization is re-solved, and the resulting objective value
    and KPIs are recorded.

    The results are persisted in nds.sensitivity_run for later retrieval.
    """
    # Validate parameter name
    valid_params = {"DI", "CAP", "Cb", "Co", "Cs", "Cp", "U", "L", "BI", "CP"}
    if request.parameter_name not in valid_params:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid parameter '{request.parameter_name}'. "
                f"Must be one of: {', '.join(sorted(valid_params))}"
            ),
        )

    # Get base run for scenario_id reference (use latest for the scenario)
    latest_run = (
        db_nds.query(OptimizationRun)
        .filter(OptimizationRun.scenario_id == request.scenario_id)
        .order_by(OptimizationRun.run_time.desc())
        .first()
    )

    base_run_id = latest_run.run_id if latest_run else 0

    # Create sensitivity-run record
    sensitivity = SensitivityRun(
        base_run_id=base_run_id,
        parameter_name=request.parameter_name,
        variation_points=json.dumps(request.variation_percentages),
        status="running",
    )
    db_nds.add(sensitivity)
    db_nds.commit()
    db_nds.refresh(sensitivity)

    try:
        # Fetch base input
        data_repo = OptimizationDataRepository(db_dds)
        base_input = data_repo.get_optimization_input()

        # Optionally pre-compute base result
        base_result = None
        if latest_run:
            # We could pass a pre-computed result, but
            # SensitivityService will solve base if None is passed
            pass

        # Execute sensitivity analysis
        result = _sensitivity_svc.run_sensitivity(
            base_data=base_input,
            request=request,
            base_result=base_result,
        )

        # Persist results
        serialised_points = []
        for pt in result.points:
            serialised_points.append({
                "variation_pct": pt.variation_pct,
                "scale_factor": pt.scale_factor,
                "objective_value": pt.objective_value,
                "solver_status": pt.solver_status,
                "kpis": pt.kpis,
            })

        sensitivity.results = json.dumps(serialised_points)
        sensitivity.status = "completed"
        db_nds.commit()

        return result

    except Exception as e:
        sensitivity.status = "failed"
        sensitivity.results = json.dumps([])
        db_nds.commit()
        raise HTTPException(
            status_code=500,
            detail=f"Sensitivity analysis failed: {str(e)}",
        )


# ================================================================== #
#  2. GET /{sensitivity_id} -- Retrieve sensitivity results            #
# ================================================================== #

@router.get("/{sensitivity_id}", response_model=SensitivityResult)
def get_sensitivity_results(
    sensitivity_id: int,
    db: Session = Depends(get_db_nds),
):
    """
    Retrieve the results of a previously-run sensitivity analysis
    by its sensitivity_id.
    """
    sensitivity = db.query(SensitivityRun).filter(
        SensitivityRun.sensitivity_id == sensitivity_id
    ).first()

    if not sensitivity:
        raise HTTPException(
            status_code=404, detail="Sensitivity run not found"
        )

    # Deserialise stored JSON
    variation_points: List[float] = []
    if sensitivity.variation_points:
        try:
            variation_points = json.loads(sensitivity.variation_points)
        except (json.JSONDecodeError, TypeError):
            pass

    points = []
    baseline_objective = 0.0
    if sensitivity.results:
        try:
            raw_points = json.loads(sensitivity.results)
            from backend.schemas.sensitivity import SensitivityPoint
            for rp in raw_points:
                points.append(SensitivityPoint(**rp))
        except (json.JSONDecodeError, TypeError):
            pass

    # Fetch base run objective for baseline
    if sensitivity.base_run_id:
        base_run = db.query(OptimizationRun).filter(
            OptimizationRun.run_id == sensitivity.base_run_id
        ).first()
        if base_run:
            baseline_objective = float(base_run.objective_value or 0)

    # Determine scenario_id from base run
    scenario_id = 0
    if sensitivity.base_run_id:
        base_run = db.query(OptimizationRun).filter(
            OptimizationRun.run_id == sensitivity.base_run_id
        ).first()
        if base_run:
            scenario_id = base_run.scenario_id

    return SensitivityResult(
        scenario_id=scenario_id,
        parameter_name=sensitivity.parameter_name,
        baseline_objective=baseline_objective,
        baseline_kpis={},
        points=points,
        elasticity=None,
    )


# ================================================================== #
#  3. POST /tornado -- Tornado analysis across multiple parameters     #
# ================================================================== #

@router.post("/tornado", response_model=TornadoResult, status_code=201)
def run_tornado(
    request: TornadoRequest,
    db_nds: Session = Depends(get_db_nds),
    db_dds: Session = Depends(get_db_dds),
):
    """
    Run tornado analysis across multiple parameters.

    For each parameter in the request, the model is solved at
    +/- variation_pct. Results are returned sorted by descending
    spread (most impactful parameter first).

    This is computationally expensive -- it solves 2*N optimizations
    where N = len(parameters).
    """
    # Validate parameters
    valid_params = {"DI", "CAP", "Cb", "Co", "Cs", "Cp", "U", "L", "BI", "CP"}
    invalid = set(request.parameters) - valid_params
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid parameter(s): {', '.join(sorted(invalid))}. "
                f"Must be one of: {', '.join(sorted(valid_params))}"
            ),
        )

    try:
        # Fetch base input
        data_repo = OptimizationDataRepository(db_dds)
        base_input = data_repo.get_optimization_input()

        # Execute tornado analysis
        result = _sensitivity_svc.run_tornado(
            base_data=base_input,
            request=request,
            base_result=None,
        )

        # Persist a summary record
        sensitivity = SensitivityRun(
            base_run_id=0,
            parameter_name="TORNADO:" + ",".join(request.parameters),
            variation_points=json.dumps(
                [request.variation_pct, -request.variation_pct]
            ),
            results=json.dumps([
                {
                    "parameter_name": bar.parameter_name,
                    "low_value": bar.low_value,
                    "high_value": bar.high_value,
                    "spread": bar.spread,
                    "low_pct_change": bar.low_pct_change,
                    "high_pct_change": bar.high_pct_change,
                }
                for bar in result.bars
            ]),
            status="completed",
        )
        db_nds.add(sensitivity)
        db_nds.commit()

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Tornado analysis failed: {str(e)}",
        )
