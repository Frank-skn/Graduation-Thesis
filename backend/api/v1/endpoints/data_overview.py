"""
Data overview endpoints.
Provides dataset exploration, model-parameter management,
and dataset version tracking.
"""
import json
import hashlib
import statistics
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db_nds, get_db_dds
from backend.data_access.repositories import OptimizationDataRepository
from backend.data_access.models_dds import DDSModelParameters
from backend.data_access.models_nds import DatasetVersion
from backend.schemas.data_overview import (
    DataOverview,
    ParameterSummary,
    DatasetVersionInfo,
    DatasetVersionList,
)

router = APIRouter()


# ------------------------------------------------------------------ #
#  1. GET / -- Dataset overview                                       #
# ------------------------------------------------------------------ #

@router.get("/", response_model=DataOverview)
def get_data_overview(db: Session = Depends(get_db_dds)):
    """
    Get high-level overview of the loaded optimization dataset.

    Returns product / warehouse / period counts and per-parameter
    summary statistics (min, max, mean, std, zero-count).
    """
    repo = OptimizationDataRepository(db)
    opt_input = repo.get_optimization_input()

    # Build summary stats for each parameter dictionary
    param_dicts = {
        "BI": opt_input.BI,
        "CP": opt_input.CP,
        "U": opt_input.U,
        "L": opt_input.L,
        "DI": opt_input.DI,
        "CAP": opt_input.CAP,
        "Cb": opt_input.Cb,
        "Co": opt_input.Co,
        "Cs": opt_input.Cs,
        "Cp": opt_input.Cp,
    }

    summaries: List[ParameterSummary] = []
    for name, d in param_dicts.items():
        if not d:
            continue
        float_values = [float(v) for v in d.values()]
        summaries.append(
            ParameterSummary(
                name=name,
                num_entries=len(float_values),
                min_value=min(float_values),
                max_value=max(float_values),
                mean_value=statistics.mean(float_values),
                std_value=(
                    statistics.stdev(float_values)
                    if len(float_values) > 1
                    else 0.0
                ),
                zero_count=sum(1 for v in float_values if v == 0),
                sample_keys=[str(k) for k in list(d.keys())[:5]],
            )
        )

    return DataOverview(
        num_products=len(opt_input.I),
        num_warehouses=len(opt_input.J),
        num_periods=len(opt_input.T),
        products=opt_input.I,
        warehouses=opt_input.J,
        periods=opt_input.T,
        parameters=summaries,
        total_combinations=(
            len(opt_input.I) * len(opt_input.J) * len(opt_input.T)
        ),
    )


# ------------------------------------------------------------------ #
#  2. GET /parameters -- List model parameters                        #
# ------------------------------------------------------------------ #

class ModelParameterResponse(BaseModel):
    """Single model parameter."""
    param_id: int
    param_name: str
    param_value: float
    param_description: Optional[str] = None


class ModelParameterList(BaseModel):
    """Collection of model parameters."""
    parameters: List[ModelParameterResponse]
    total: int


@router.get("/parameters", response_model=ModelParameterList)
def get_model_parameters(db: Session = Depends(get_db_dds)):
    """
    Get all model parameters from dds.dds_model_parameters.
    """
    params = db.query(DDSModelParameters).order_by(
        DDSModelParameters.param_name
    ).all()

    return ModelParameterList(
        parameters=[
            ModelParameterResponse(
                param_id=p.param_id,
                param_name=p.param_name,
                param_value=float(p.param_value or 0),
                param_description=p.param_description,
            )
            for p in params
        ],
        total=len(params),
    )


# ------------------------------------------------------------------ #
#  3. PUT /parameters/{param_name} -- Update a model parameter        #
# ------------------------------------------------------------------ #

class ModelParameterUpdate(BaseModel):
    """Payload to update a model parameter value."""
    param_value: float = Field(..., description="New parameter value")


@router.put("/parameters/{param_name}", response_model=ModelParameterResponse)
def update_model_parameter(
    param_name: str,
    update: ModelParameterUpdate,
    db: Session = Depends(get_db_dds),
):
    """
    Update a model parameter value by name.
    """
    param = db.query(DDSModelParameters).filter(
        DDSModelParameters.param_name == param_name
    ).first()

    if not param:
        raise HTTPException(
            status_code=404,
            detail=f"Parameter '{param_name}' not found",
        )

    param.param_value = update.param_value
    db.commit()
    db.refresh(param)

    return ModelParameterResponse(
        param_id=param.param_id,
        param_name=param.param_name,
        param_value=float(param.param_value or 0),
        param_description=param.param_description,
    )


# ------------------------------------------------------------------ #
#  4. GET /datasets -- List dataset versions                          #
# ------------------------------------------------------------------ #

@router.get("/datasets", response_model=DatasetVersionList)
def list_dataset_versions(
    limit: int = 50,
    db: Session = Depends(get_db_nds),
):
    """
    List all active dataset version snapshots, newest first.
    """
    versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.is_active == True)
        .order_by(DatasetVersion.created_at.desc())
        .limit(limit)
        .all()
    )

    items: List[DatasetVersionInfo] = []
    for v in versions:
        snapshot = {}
        if v.snapshot_data:
            try:
                snapshot = json.loads(v.snapshot_data)
            except (json.JSONDecodeError, TypeError):
                pass

        items.append(
            DatasetVersionInfo(
                version_id=v.version_id,
                scenario_id=snapshot.get("scenario_id", 0),
                label=v.version_name,
                created_at=v.created_at or datetime.utcnow(),
                created_by=v.created_by or "system",
                num_products=snapshot.get("num_products", 0),
                num_warehouses=snapshot.get("num_warehouses", 0),
                num_periods=snapshot.get("num_periods", 0),
                checksum=snapshot.get("checksum"),
                notes=v.description,
            )
        )

    return DatasetVersionList(versions=items, total=len(items))


# ------------------------------------------------------------------ #
#  5. POST /datasets -- Create a dataset version snapshot              #
# ------------------------------------------------------------------ #

class DatasetVersionCreate(BaseModel):
    """Payload to create a new dataset version snapshot."""
    version_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    created_by: str = Field(default="system", max_length=100)


@router.post("/datasets", response_model=DatasetVersionInfo, status_code=201)
def create_dataset_version(
    request: DatasetVersionCreate,
    db_nds: Session = Depends(get_db_nds),
    db_dds: Session = Depends(get_db_dds),
):
    """
    Create a dataset version snapshot from the current DDS data.

    Captures the current set of products, warehouses, and periods,
    computes a SHA-256 checksum, and stores the metadata in
    nds.dataset_version.
    """
    repo = OptimizationDataRepository(db_dds)
    products = repo.get_products()
    warehouses = repo.get_warehouses()
    periods = repo.get_time_periods()

    # Build snapshot metadata
    snapshot_meta = {
        "scenario_id": 0,
        "num_products": len(products),
        "num_warehouses": len(warehouses),
        "num_periods": len(periods),
        "products": products,
        "warehouses": warehouses,
        "periods": periods,
        "checksum": hashlib.sha256(
            json.dumps(
                {"I": products, "J": warehouses, "T": periods},
                sort_keys=True,
            ).encode()
        ).hexdigest(),
    }

    version = DatasetVersion(
        version_name=request.version_name,
        description=request.description,
        snapshot_data=json.dumps(snapshot_meta),
        created_by=request.created_by,
        is_active=True,
    )

    db_nds.add(version)
    db_nds.commit()
    db_nds.refresh(version)

    return DatasetVersionInfo(
        version_id=version.version_id,
        scenario_id=0,
        label=version.version_name,
        created_at=version.created_at or datetime.utcnow(),
        created_by=version.created_by or "system",
        num_products=snapshot_meta["num_products"],
        num_warehouses=snapshot_meta["num_warehouses"],
        num_periods=snapshot_meta["num_periods"],
        checksum=snapshot_meta["checksum"],
        notes=version.description,
    )
