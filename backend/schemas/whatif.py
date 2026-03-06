"""
Pydantic schemas for What-If scenario analysis.
Defines scenario templates, creation requests, responses, and comparisons.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


class ScenarioType(str, Enum):
    """Enumeration of supported what-if scenario types."""
    DEMAND_SURGE = "demand_surge"
    DEMAND_DROP = "demand_drop"
    CAPACITY_DISRUPTION = "capacity_disruption"
    CAPACITY_EXPANSION = "capacity_expansion"
    COST_INCREASE = "cost_increase"
    COST_DECREASE = "cost_decrease"
    SAFETY_STOCK_TIGHTEN = "safety_stock_tighten"
    SAFETY_STOCK_LOOSEN = "safety_stock_loosen"
    NEW_PRODUCT_INTRODUCTION = "new_product_introduction"
    WAREHOUSE_CLOSURE = "warehouse_closure"
    CUSTOM = "custom"


class ScenarioTemplate(BaseModel):
    """Predefined template describing a what-if scenario type."""
    scenario_type: ScenarioType = Field(..., description="Type of what-if scenario")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field("", description="Detailed description of what this scenario does")
    affected_parameters: List[str] = Field(
        default_factory=list,
        description="List of parameter names this scenario modifies (e.g. DI, CAP, U, L)"
    )
    default_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Default override values (e.g. {'factor': 1.2, 'products': []})"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "scenario_type": "demand_surge",
                "display_name": "Demand Surge (+20%)",
                "description": "Increases demand (DI) by a multiplicative factor",
                "affected_parameters": ["DI"],
                "default_overrides": {"factor": 1.2, "products": [], "periods": []}
            }
        }


class WhatIfCreate(BaseModel):
    """Request to create and run a what-if scenario."""
    base_scenario_id: int = Field(..., description="ID of the base scenario to modify")
    scenario_type: ScenarioType = Field(..., description="Type of what-if modification")
    label: str = Field("", description="User-defined label for this what-if run")
    overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Parameter overrides. Common keys: "
            "'factor' (float multiplier), "
            "'products' (list of product IDs to scope, empty = all), "
            "'periods' (list of periods to scope, empty = all), "
            "'warehouses' (list of warehouse IDs to scope, empty = all), "
            "'absolute_value' (set parameter to this exact value)"
        )
    )
    solver: Optional[str] = Field(default="cbc", description="Solver to use")
    time_limit: Optional[int] = Field(default=300, description="Solver time limit (s)")
    mip_gap: Optional[float] = Field(default=0.01, description="MIP gap tolerance")

    class Config:
        json_schema_extra = {
            "example": {
                "base_scenario_id": 1,
                "scenario_type": "demand_surge",
                "label": "Q2 demand +30%",
                "overrides": {
                    "factor": 1.3,
                    "products": ["PROD001", "PROD002"],
                    "periods": [4, 5, 6]
                },
                "solver": "cbc",
                "time_limit": 300,
                "mip_gap": 0.01
            }
        }


class WhatIfKPIs(BaseModel):
    """KPIs produced by a what-if scenario run."""
    total_cost: float = Field(0.0, description="Total objective cost")
    total_backorder: float = Field(0.0, description="Total backorder quantity")
    total_overstock: float = Field(0.0, description="Total overstock quantity")
    total_shortage: float = Field(0.0, description="Total shortage quantity")
    total_penalty: float = Field(0.0, description="Total penalty count")
    cost_backorder: float = Field(0.0, description="Cost component: backorder")
    cost_overstock: float = Field(0.0, description="Cost component: overstock")
    cost_shortage:  float = Field(0.0, description="Cost component: shortage")
    cost_penalty:   float = Field(0.0, description="Cost component: penalty")
    service_level: float = Field(0.0, description="Service level (%)")
    capacity_utilization: float = Field(0.0, description="Capacity utilization (%)")


class WhatIfResponse(BaseModel):
    """Response from a what-if scenario execution."""
    whatif_id: int = Field(..., description="Unique ID for this what-if run")
    base_scenario_id: int = Field(..., description="Base scenario ID")
    scenario_type: ScenarioType = Field(..., description="Type of modification applied")
    label: str = Field("", description="User-defined label")
    solver_status: str = Field(..., description="Solver termination status")
    solve_time_seconds: float = Field(..., description="Solver wall-clock time")
    objective_value: float = Field(..., description="Objective function value")
    kpis: WhatIfKPIs = Field(..., description="KPI summary")
    parameters_modified: List[str] = Field(
        default_factory=list,
        description="Which parameters were changed"
    )
    # Extended savings metrics (mirrored from DssRunSummary)
    baseline_cost: float = Field(0.0, description="Do-nothing baseline cost")
    savings: float = Field(0.0, description="Absolute savings vs baseline")
    savings_pct: float = Field(0.0, description="Savings as % of baseline")
    n_changes: int = Field(0, description="Rows with reorder action")
    si_mean: float = Field(0.0, description="Mean Safety Index")
    ss_below_count: int = Field(0, description="Rows where inventory < safety floor")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this run was executed"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "whatif_id": 5,
                "base_scenario_id": 1,
                "scenario_type": "demand_surge",
                "label": "Q2 demand +30%",
                "solver_status": "optimal",
                "solve_time_seconds": 8.2,
                "objective_value": 18500.0,
                "kpis": {
                    "total_cost": 18500.0,
                    "total_backorder": 120.0,
                    "total_overstock": 45.0,
                    "total_shortage": 10.0,
                    "total_penalty": 3.0,
                    "service_level": 92.5,
                    "capacity_utilization": 78.3
                },
                "parameters_modified": ["DI"],
                "created_at": "2024-06-15T14:30:00"
            }
        }


class KPIDelta(BaseModel):
    """Change in a single KPI between two scenarios."""
    kpi_name: str = Field(..., description="Name of the KPI")
    base_value: float = Field(..., description="Value in the base scenario")
    whatif_value: float = Field(..., description="Value in the what-if scenario")
    absolute_change: float = Field(..., description="whatif_value - base_value")
    percent_change: Optional[float] = Field(
        None,
        description="Percentage change; None if base_value is 0"
    )


class WhatIfComparison(BaseModel):
    """Side-by-side comparison of base vs. what-if scenario KPIs."""
    base_scenario_id: int = Field(..., description="Base scenario ID")
    whatif_id: int = Field(..., description="What-if run ID")
    scenario_type: ScenarioType = Field(..., description="Type of what-if")
    label: str = Field("", description="What-if label")
    deltas: List[KPIDelta] = Field(
        default_factory=list,
        description="Per-KPI comparison deltas"
    )
    summary: str = Field(
        "",
        description="Human-readable summary of the comparison"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "base_scenario_id": 1,
                "whatif_id": 5,
                "scenario_type": "demand_surge",
                "label": "Q2 demand +30%",
                "deltas": [
                    {
                        "kpi_name": "total_cost",
                        "base_value": 15000.0,
                        "whatif_value": 18500.0,
                        "absolute_change": 3500.0,
                        "percent_change": 23.33
                    }
                ],
                "summary": "Demand surge increases total cost by 23.3%"
            }
        }
