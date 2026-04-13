"""
Sensitivity analysis endpoints — background-job pattern.
POST /run and POST /tornado return immediately with a job_id.
Poll GET /jobs/{job_id} for status; GET /jobs/{job_id}/result for full result.
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.core.database import get_db_nds, get_csv_data
from backend.data_access.csv_repository import CsvOptimizationDataRepository
from backend.data_access.models_nds import SensitivityRun, OptimizationRun
from backend.domain.sensitivity_service import SensitivityService
from backend.schemas.sensitivity import (
    SensitivityRequest,
    SensitivityResult,
    TornadoRequest,
    TornadoResult,
)

router = APIRouter()

_sensitivity_svc = SensitivityService()


# ------------------------------------------------------------------ #
#  Background task helpers                                            #
# ------------------------------------------------------------------ #

def _run_oat_task(sensitivity_id: int, request_dict: dict, data_dir: str):
    """Background worker for OAT sensitivity."""
    from backend.core.database import SessionLocalNDS
    from backend.schemas.sensitivity import SensitivityRequest as Req

    db = SessionLocalNDS()
    try:
        repo = CsvOptimizationDataRepository(data_dir)
        base_input = repo.get_optimization_input()
        request = Req(**request_dict)

        result = _sensitivity_svc.run_sensitivity(
            base_data=base_input,
            request=request,
        )

        serialised = [
            {
                "variation_pct": pt.variation_pct,
                "scale_factor": pt.scale_factor,
                "objective_value": pt.objective_value,
                "solver_status": pt.solver_status,
                "kpis": pt.kpis,
            }
            for pt in result.points
        ]

        row = db.query(SensitivityRun).filter(
            SensitivityRun.sensitivity_id == sensitivity_id
        ).first()
        if row:
            row.results = json.dumps(serialised)
            row.status = "completed"
            db.commit()

    except Exception as exc:
        row = db.query(SensitivityRun).filter(
            SensitivityRun.sensitivity_id == sensitivity_id
        ).first()
        if row:
            row.status = "failed"
            row.results = json.dumps({"error": str(exc)})
            db.commit()
    finally:
        db.close()


def _run_tornado_task(sensitivity_id: int, request_dict: dict, data_dir: str):
    """Background worker for Tornado analysis."""
    from backend.core.database import SessionLocalNDS
    from backend.schemas.sensitivity import TornadoRequest as Req

    db = SessionLocalNDS()
    try:
        repo = CsvOptimizationDataRepository(data_dir)
        base_input = repo.get_optimization_input()
        request = Req(**request_dict)

        result = _sensitivity_svc.run_tornado(
            base_data=base_input,
            request=request,
        )

        serialised = [
            {
                "parameter_name": bar.parameter_name,
                "low_value": bar.low_value,
                "high_value": bar.high_value,
                "spread": bar.spread,
                "low_pct_change": bar.low_pct_change,
                "high_pct_change": bar.high_pct_change,
            }
            for bar in result.bars
        ]

        row = db.query(SensitivityRun).filter(
            SensitivityRun.sensitivity_id == sensitivity_id
        ).first()
        if row:
            row.results = json.dumps({
                "baseline_objective": result.baseline_objective,
                "variation_pct": result.variation_pct,
                "bars": serialised,
            })
            row.status = "completed"
            db.commit()

    except Exception as exc:
        row = db.query(SensitivityRun).filter(
            SensitivityRun.sensitivity_id == sensitivity_id
        ).first()
        if row:
            row.status = "failed"
            row.results = json.dumps({"error": str(exc)})
            db.commit()
    finally:
        db.close()


# ================================================================== #
#  1. POST /run — OAT sensitivity (background)                        #
# ================================================================== #

@router.post("/run", status_code=202)
def run_sensitivity(
    request: SensitivityRequest,
    background_tasks: BackgroundTasks,
    db_nds: Session = Depends(get_db_nds),
    csv_repo: CsvOptimizationDataRepository = Depends(get_csv_data),
):
    """Submit OAT sensitivity job. Returns job_id immediately. Poll /jobs/{job_id}."""
    valid_params = {"DI", "CAP", "Cb", "Co", "Cs", "Cp", "U", "L", "BI", "CP"}
    if request.parameter_name not in valid_params:
        raise HTTPException(status_code=400, detail=f"Invalid parameter '{request.parameter_name}'")

    latest_run = (
        db_nds.query(OptimizationRun)
        .filter(OptimizationRun.scenario_id == request.scenario_id)
        .order_by(OptimizationRun.run_time.desc())
        .first()
    )

    row = SensitivityRun(
        base_run_id=latest_run.run_id if latest_run else None,
        parameter_name=request.parameter_name,
        variation_points=json.dumps(request.variation_percentages),
        status="running",
    )
    db_nds.add(row)
    db_nds.commit()
    db_nds.refresh(row)

    background_tasks.add_task(
        _run_oat_task,
        sensitivity_id=row.sensitivity_id,
        request_dict=request.model_dump(),
        data_dir=str(csv_repo._dir),
    )

    return {"job_id": row.sensitivity_id, "status": "running",
            "message": "OAT analysis started. Poll /sensitivity/jobs/{job_id} for status."}


# ================================================================== #
#  2. POST /tornado — Tornado analysis (background)                   #
# ================================================================== #

@router.post("/tornado", status_code=202)
def run_tornado(
    request: TornadoRequest,
    background_tasks: BackgroundTasks,
    db_nds: Session = Depends(get_db_nds),
    csv_repo: CsvOptimizationDataRepository = Depends(get_csv_data),
):
    """Submit Tornado job. Returns job_id immediately. Poll /sensitivity/jobs/{job_id}."""
    valid_params = {"DI", "CAP", "Cb", "Co", "Cs", "Cp", "U", "L", "BI", "CP"}
    invalid = set(request.parameters) - valid_params
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid parameter(s): {invalid}")

    row = SensitivityRun(
        base_run_id=None,
        parameter_name="TORNADO:" + ",".join(request.parameters),
        variation_points=json.dumps([request.variation_pct, -request.variation_pct]),
        status="running",
    )
    db_nds.add(row)
    db_nds.commit()
    db_nds.refresh(row)

    background_tasks.add_task(
        _run_tornado_task,
        sensitivity_id=row.sensitivity_id,
        request_dict=request.model_dump(),
        data_dir=str(csv_repo._dir),
    )

    return {"job_id": row.sensitivity_id, "status": "running",
            "message": "Tornado analysis started. Poll /sensitivity/jobs/{job_id} for status."}


# ================================================================== #
#  3. GET /jobs/{job_id} — Poll job status                            #
# ================================================================== #

@router.get("/jobs/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db_nds)):
    """Poll status of a sensitivity job. Returns status + result when completed."""
    row = db.query(SensitivityRun).filter(
        SensitivityRun.sensitivity_id == job_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {"job_id": job_id, "status": row.status}

    if row.status == "completed" and row.results:
        try:
            response["result"] = json.loads(row.results)
        except Exception:
            pass
    elif row.status == "failed" and row.results:
        try:
            err = json.loads(row.results)
            response["error"] = err.get("error", "Unknown error")
        except Exception:
            pass

    return response


# ================================================================== #
#  4. GET /{sensitivity_id} — Legacy retrieve                         #
# ================================================================== #

@router.get("/{sensitivity_id}")
def get_sensitivity_results(sensitivity_id: int, db: Session = Depends(get_db_nds)):
    """Retrieve a completed sensitivity run by ID."""
    row = db.query(SensitivityRun).filter(
        SensitivityRun.sensitivity_id == sensitivity_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Sensitivity run not found")
    return {"sensitivity_id": row.sensitivity_id, "status": row.status,
            "parameter_name": row.parameter_name,
            "result": json.loads(row.results) if row.results else None}
