"""
Pydantic schemas for optimization-related data
Implements Data Transfer Objects (DTOs)
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime


class OptimizationInput(BaseModel):
    """Input data structure for optimization model"""
    I: List[str] = Field(..., description="Set of products (items)")
    J: List[str] = Field(..., description="Set of warehouses (FGPs)")
    T: List[int] = Field(..., description="Set of time periods")
    
    BI: Dict[Tuple[str, str], int] = Field(..., description="Beginning inventory BI(i,j)")
    CP: Dict[Tuple[str, str], int] = Field(..., description="Case pack CP(i,j)")
    
    U: Dict[Tuple[str, str, int], int] = Field(..., description="Upper bound U(i,j,t)")
    L: Dict[Tuple[str, str, int], int] = Field(..., description="Lower bound L(i,j,t)")
    DI: Dict[Tuple[str, str, int], int] = Field(..., description="Delta inventory DI(i,j,t)")
    CAP: Dict[Tuple[str, int], int] = Field(..., description="Capacity CAP(i,t)")
    
    Cb: Dict[Tuple[str, str, int], float] = Field(..., description="Backorder cost Cb(i,j,t)")
    Co: Dict[Tuple[str, str, int], float] = Field(..., description="Overstock cost Co(i,j,t)")
    Cs: Dict[Tuple[str, str, int], float] = Field(..., description="Shortage cost Cs(i,j,t)")
    Cp: Dict[Tuple[str, str, int], float] = Field(..., description="Penalty cost Cp(i,j,t)")
    
    HV: float = Field(default=9999, description="High value constant")
    
    class Config:
        json_schema_extra = {
            "example": {
                "I": ["PROD001", "PROD002"],
                "J": ["WH01", "WH02"],
                "T": [1, 2, 3],
                "BI": {("PROD001", "WH01"): 100},
                "CP": {("PROD001", "WH01"): 50},
                "HV": 9999
            }
        }


class OptimizationResult(BaseModel):
    """Single result record"""
    product_id: str
    warehouse_id: str
    box_id: int
    time_period: int
    q_case_pack: int
    r_residual_units: int
    net_inventory: float
    backorder_qty: float
    overstock_qty: float
    shortage_qty: float
    penalty_flag: bool


class OptimizationOutput(BaseModel):
    """Output from optimization run"""
    results: List[Dict[str, Any]]
    
    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "product_id": "PROD001",
                        "warehouse_id": "WH01",
                        "box_id": 1,
                        "time_period": 1,
                        "q_case_pack": 10,
                        "r_residual_units": 5,
                        "net_inventory": 505,
                        "backorder_qty": 0,
                        "overstock_qty": 5,
                        "shortage_qty": 0,
                        "penalty_flag": True
                    }
                ]
            }
        }


class OptimizationRequest(BaseModel):
    """Request to run optimization"""
    scenario_id: int = Field(..., description="Scenario ID to optimize")
    solver: Optional[str] = Field(default="cbc", description="Solver to use (cbc, glpk)")
    time_limit: Optional[int] = Field(default=300, description="Time limit in seconds")
    mip_gap: Optional[float] = Field(default=0.01, description="MIP gap tolerance")


class OptimizationResponse(BaseModel):
    """Response from optimization run"""
    run_id: int
    scenario_id: int
    solver_status: str
    solve_time_seconds: float
    objective_value: float
    mip_gap: float
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "run_id": 42,
                "scenario_id": 1,
                "solver_status": "optimal",
                "solve_time_seconds": 12.5,
                "objective_value": 15420.75,
                "mip_gap": 0.005,
                "message": "Optimization completed successfully"
            }
        }


class KPISummary(BaseModel):
    """KPI summary for a run"""
    run_id: int
    total_cost: float
    total_backorder: float
    total_overstock: float
    total_shortage: float
    total_penalty: float
    service_level: float
    capacity_utilization: float
