"""
Pydantic schemas for data overview, parameter inspection, and dataset versioning.
Provides DTOs for the DSS data exploration layer.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class ParameterSummary(BaseModel):
    """Statistical summary of a single optimization parameter."""
    name: str = Field(..., description="Parameter name (e.g. DI, CAP, U, L)")
    num_entries: int = Field(..., description="Number of entries in the parameter dict")
    min_value: float = Field(..., description="Minimum value across all entries")
    max_value: float = Field(..., description="Maximum value across all entries")
    mean_value: float = Field(..., description="Mean value across all entries")
    std_value: float = Field(0.0, description="Standard deviation of values")
    zero_count: int = Field(0, description="Number of entries with value == 0")
    sample_keys: List[str] = Field(
        default_factory=list,
        description="Sample of dictionary keys for inspection (up to 5)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "DI",
                "num_entries": 360,
                "min_value": -500.0,
                "max_value": 2000.0,
                "mean_value": 150.5,
                "std_value": 245.3,
                "zero_count": 12,
                "sample_keys": [
                    "('PROD001', 'WH01', 1)",
                    "('PROD001', 'WH01', 2)"
                ]
            }
        }


class DataOverview(BaseModel):
    """High-level overview of the loaded optimization dataset."""
    num_products: int = Field(..., description="Number of unique products |I|")
    num_warehouses: int = Field(..., description="Number of unique warehouses |J|")
    num_periods: int = Field(..., description="Number of time periods |T|")
    products: List[str] = Field(..., description="List of product IDs")
    warehouses: List[str] = Field(..., description="List of warehouse IDs")
    periods: List[int] = Field(..., description="List of time periods")
    parameters: List[ParameterSummary] = Field(
        default_factory=list,
        description="Summary statistics for each parameter"
    )
    total_combinations: int = Field(
        0,
        description="Total theoretical (i,j,t) combinations = |I|*|J|*|T|"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "num_products": 10,
                "num_warehouses": 6,
                "num_periods": 12,
                "products": ["PROD001", "PROD002"],
                "warehouses": ["WH01", "WH02"],
                "periods": [1, 2, 3],
                "parameters": [],
                "total_combinations": 720
            }
        }


class DatasetVersionInfo(BaseModel):
    """Metadata about a dataset version / snapshot."""
    version_id: int = Field(..., description="Auto-increment version identifier")
    scenario_id: int = Field(..., description="Parent scenario ID")
    label: str = Field("", description="Human-readable label for this version")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when this version was created"
    )
    created_by: str = Field("system", description="User or system that created this version")
    num_products: int = Field(0, description="Product count at this version")
    num_warehouses: int = Field(0, description="Warehouse count at this version")
    num_periods: int = Field(0, description="Period count at this version")
    checksum: Optional[str] = Field(
        None,
        description="SHA-256 hash of serialized input data for integrity"
    )
    notes: Optional[str] = Field(None, description="Optional version notes")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "version_id": 3,
                "scenario_id": 1,
                "label": "After demand adjustment",
                "created_at": "2024-06-15T10:30:00",
                "created_by": "analyst@company.com",
                "num_products": 10,
                "num_warehouses": 6,
                "num_periods": 12,
                "checksum": "abc123def456...",
                "notes": "Demand increased by 15% for PROD001"
            }
        }


class DatasetVersionList(BaseModel):
    """Collection of dataset versions."""
    versions: List[DatasetVersionInfo] = Field(default_factory=list)
    total: int = Field(0, description="Total number of versions")
