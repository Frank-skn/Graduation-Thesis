"""
Pydantic schemas for decision insights and recommendations.
Defines insight severity levels, individual insights, and response containers.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


class InsightSeverity(str, Enum):
    """Severity / priority level for a decision insight."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    OPPORTUNITY = "opportunity"


class InsightCategory(str, Enum):
    """Functional category of an insight."""
    SERVICE_LEVEL = "service_level"
    CAPACITY = "capacity"
    INVENTORY = "inventory"
    COST = "cost"
    BACKORDER = "backorder"
    OVERSTOCK = "overstock"
    SHORTAGE = "shortage"
    PENALTY = "penalty"


class Insight(BaseModel):
    """A single decision insight / recommendation."""
    insight_id: str = Field(..., description="Unique identifier for the insight")
    severity: InsightSeverity = Field(..., description="Severity level")
    category: InsightCategory = Field(..., description="Functional category")
    title: str = Field(..., description="Short headline of the insight")
    description: str = Field(
        ...,
        description="Detailed description of the finding"
    )
    recommendation: str = Field(
        "",
        description="Actionable recommendation to address the insight"
    )
    affected_products: List[str] = Field(
        default_factory=list,
        description="Products involved in this insight"
    )
    affected_warehouses: List[str] = Field(
        default_factory=list,
        description="Warehouses involved in this insight"
    )
    affected_periods: List[int] = Field(
        default_factory=list,
        description="Time periods involved in this insight"
    )
    metric_name: Optional[str] = Field(
        None, description="KPI or metric name this insight is based on"
    )
    metric_value: Optional[float] = Field(
        None, description="Current value of the metric"
    )
    threshold: Optional[float] = Field(
        None, description="Threshold that was breached (if applicable)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context or data for the insight"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "insight_id": "SL-001",
                "severity": "critical",
                "category": "service_level",
                "title": "Service level below 90%",
                "description": (
                    "The overall service level is at 85.3%, "
                    "which is below the 90% threshold."
                ),
                "recommendation": (
                    "Consider increasing safety stock bounds (U/L) "
                    "or reviewing demand forecasts."
                ),
                "affected_products": ["PROD001", "PROD003"],
                "affected_warehouses": ["WH02"],
                "affected_periods": [3, 4, 5],
                "metric_name": "service_level",
                "metric_value": 85.3,
                "threshold": 90.0,
                "metadata": {}
            }
        }


class InsightsRequest(BaseModel):
    """Request to generate insights from an optimization run."""
    scenario_id: int = Field(..., description="Scenario ID")
    run_id: Optional[int] = Field(
        None,
        description="Specific run ID; if None, uses the latest run"
    )
    kpis: Dict[str, float] = Field(
        default_factory=dict,
        description="KPIs dict from the optimization result"
    )
    results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Per-record optimization results"
    )
    thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "service_level_critical": 90.0,
            "service_level_warning": 95.0,
            "capacity_utilization_high": 90.0,
            "capacity_utilization_low": 30.0,
            "backorder_ratio_warning": 0.05,
            "overstock_ratio_warning": 0.10,
        },
        description="Configurable thresholds for insight generation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "scenario_id": 1,
                "run_id": 42,
                "kpis": {
                    "total_cost": 15000.0,
                    "service_level": 92.5,
                    "capacity_utilization": 78.0,
                    "total_backorder": 120.0,
                    "total_overstock": 45.0,
                    "total_shortage": 10.0,
                    "total_penalty": 3.0
                },
                "results": [],
                "thresholds": {
                    "service_level_critical": 90.0,
                    "service_level_warning": 95.0,
                    "capacity_utilization_high": 90.0,
                    "capacity_utilization_low": 30.0,
                    "backorder_ratio_warning": 0.05,
                    "overstock_ratio_warning": 0.10
                }
            }
        }


class InsightsResponse(BaseModel):
    """Collection of insights generated for a scenario/run."""
    scenario_id: int = Field(..., description="Scenario ID")
    run_id: Optional[int] = Field(None, description="Run ID (if applicable)")
    total_insights: int = Field(0, description="Total number of insights generated")
    critical_count: int = Field(0, description="Number of critical insights")
    warning_count: int = Field(0, description="Number of warning insights")
    info_count: int = Field(0, description="Number of informational insights")
    opportunity_count: int = Field(0, description="Number of opportunity insights")
    insights: List[Insight] = Field(
        default_factory=list,
        description="List of insights sorted by severity (critical first)"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when insights were generated"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "scenario_id": 1,
                "run_id": 42,
                "total_insights": 5,
                "critical_count": 1,
                "warning_count": 2,
                "info_count": 1,
                "opportunity_count": 1,
                "insights": [],
                "generated_at": "2024-06-15T14:30:00"
            }
        }
