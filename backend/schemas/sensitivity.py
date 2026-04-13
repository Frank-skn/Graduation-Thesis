"""
Pydantic schemas for sensitivity analysis.
Defines request structures, result containers, and tornado analysis output.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class SensitivityRequest(BaseModel):
    """Request to run a one-at-a-time sensitivity analysis on a parameter."""
    scenario_id: int = Field(..., description="Base scenario ID to perturb")
    parameter_name: str = Field(
        ...,
        description="Name of the parameter to vary (e.g. 'DI', 'CAP', 'Cb', 'Co', 'U', 'L')"
    )
    variation_percentages: List[float] = Field(
        default=[-20, -10, -5, 5, 10, 20],
        description=(
            "List of percentage variations to apply. "
            "E.g. [-20, -10, 10, 20] means the parameter is scaled by "
            "0.8x, 0.9x, 1.1x, 1.2x respectively."
        )
    )
    products: List[str] = Field(
        default_factory=list,
        description="Scope to specific products (empty = all)"
    )
    warehouses: List[str] = Field(
        default_factory=list,
        description="Scope to specific warehouses (empty = all)"
    )
    periods: List[int] = Field(
        default_factory=list,
        description="Scope to specific periods (empty = all)"
    )
    solver: Optional[str] = Field(default="cbc", description="Solver to use")
    time_limit: Optional[int] = Field(default=300, description="Solver time limit (s)")
    mip_gap: Optional[float] = Field(default=0.01, description="MIP gap tolerance")
    class Config:
        json_schema_extra = {
            "example": {
                "scenario_id": 1,
                "parameter_name": "DI",
                "variation_percentages": [-20, -10, -5, 5, 10, 20],
                "products": [],
                "warehouses": [],
                "periods": [],
                "solver": "cbc",
                "time_limit": 300,
                "mip_gap": 0.01
            }
        }


class SensitivityPoint(BaseModel):
    """Result at a single variation point."""
    variation_pct: float = Field(..., description="Percentage change applied (e.g. -10, +20)")
    scale_factor: float = Field(..., description="Multiplicative factor (e.g. 0.9, 1.2)")
    objective_value: float = Field(..., description="Objective value at this variation")
    solver_status: str = Field(..., description="Solver status at this variation")
    kpis: Dict[str, float] = Field(
        default_factory=dict,
        description="Full KPI dict at this variation point"
    )


class SensitivityResult(BaseModel):
    """Complete result of a one-at-a-time sensitivity analysis."""
    scenario_id: int = Field(..., description="Base scenario ID")
    parameter_name: str = Field(..., description="Parameter that was varied")
    baseline_objective: float = Field(..., description="Objective value at 0% variation (base)")
    baseline_kpis: Dict[str, float] = Field(
        default_factory=dict,
        description="KPIs at the baseline"
    )
    points: List[SensitivityPoint] = Field(
        default_factory=list,
        description="Results at each variation point"
    )
    elasticity: Optional[float] = Field(
        None,
        description=(
            "Approximate elasticity: %change in objective / %change in parameter "
            "computed from the smallest variation. None if not computable."
        )
    )

    class Config:
        json_schema_extra = {
            "example": {
                "scenario_id": 1,
                "parameter_name": "DI",
                "baseline_objective": 15000.0,
                "baseline_kpis": {
                    "total_cost": 15000.0,
                    "service_level": 95.0
                },
                "points": [
                    {
                        "variation_pct": -10.0,
                        "scale_factor": 0.9,
                        "objective_value": 13200.0,
                        "solver_status": "optimal",
                        "kpis": {"total_cost": 13200.0, "service_level": 97.0}
                    },
                    {
                        "variation_pct": 10.0,
                        "scale_factor": 1.1,
                        "objective_value": 17100.0,
                        "solver_status": "optimal",
                        "kpis": {"total_cost": 17100.0, "service_level": 91.0}
                    }
                ],
                "elasticity": 1.3
            }
        }


class TornadoBar(BaseModel):
    """Single bar in a tornado chart (one parameter)."""
    parameter_name: str = Field(..., description="Parameter name")
    low_value: float = Field(
        ...,
        description="Objective value when parameter is decreased by variation_pct"
    )
    high_value: float = Field(
        ...,
        description="Objective value when parameter is increased by variation_pct"
    )
    spread: float = Field(
        ...,
        description="Absolute spread = |high_value - low_value|"
    )
    low_pct_change: float = Field(
        ...,
        description="% change in objective for the low variation"
    )
    high_pct_change: float = Field(
        ...,
        description="% change in objective for the high variation"
    )


class TornadoRequest(BaseModel):
    """Request for tornado analysis across multiple parameters."""
    scenario_id: int = Field(..., description="Base scenario ID")
    parameters: List[str] = Field(
        default=["DI", "CAP", "Cb", "Co", "Cs", "Cp"],
        description="Parameters to include in the tornado analysis"
    )
    variation_pct: float = Field(
        default=10.0,
        description="Symmetric variation percentage (e.g. 10 means +/-10%)"
    )
    solver: Optional[str] = Field(default="cbc", description="Solver to use")
    time_limit: Optional[int] = Field(default=300, description="Solver time limit (s)")
    mip_gap: Optional[float] = Field(default=0.01, description="MIP gap tolerance")
    sample_size: Optional[int] = Field(default=None, description="Stratified sample size (None = full 943 products)")
    class Config:
        json_schema_extra = {
            "example": {
                "scenario_id": 1,
                "parameters": ["DI", "CAP", "Cb", "Co"],
                "variation_pct": 10.0,
                "solver": "cbc",
                "time_limit": 300,
                "mip_gap": 0.01
            }
        }


class TornadoResult(BaseModel):
    """Result of a tornado analysis -- bars sorted by impact (spread)."""
    scenario_id: int = Field(..., description="Base scenario ID")
    variation_pct: float = Field(..., description="Variation percentage used")
    baseline_objective: float = Field(..., description="Baseline objective value")
    bars: List[TornadoBar] = Field(
        default_factory=list,
        description="Tornado bars sorted descending by spread"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "scenario_id": 1,
                "variation_pct": 10.0,
                "baseline_objective": 15000.0,
                "bars": [
                    {
                        "parameter_name": "DI",
                        "low_value": 13200.0,
                        "high_value": 17100.0,
                        "spread": 3900.0,
                        "low_pct_change": -12.0,
                        "high_pct_change": 14.0
                    },
                    {
                        "parameter_name": "CAP",
                        "low_value": 14500.0,
                        "high_value": 15800.0,
                        "spread": 1300.0,
                        "low_pct_change": -3.3,
                        "high_pct_change": 5.3
                    }
                ]
            }
        }
