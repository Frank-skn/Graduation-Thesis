"""
Pydantic schemas for scenario management
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ScenarioCreate(BaseModel):
    """Request to create a scenario"""
    scenario_name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    created_by: str = Field(..., min_length=1, max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "scenario_name": "Q1 2024 Baseline",
                "description": "Baseline scenario for Q1 2024 planning",
                "created_by": "analyst@company.com"
            }
        }


class ScenarioResponse(BaseModel):
    """Scenario details"""
    scenario_id: int
    scenario_name: str
    description: Optional[str]
    created_at: datetime
    created_by: str
    is_baseline: bool
    
    class Config:
        from_attributes = True


class ScenarioList(BaseModel):
    """List of scenarios"""
    scenarios: list[ScenarioResponse]
    total: int
