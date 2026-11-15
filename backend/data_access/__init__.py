"""
Data access package
Implements Repository Pattern for database abstraction
"""
from backend.data_access.interfaces import (
    IOptimizationDataRepository,
    IScenarioRepository,
    IResultRepository
)
from backend.data_access.repositories import (
    OptimizationDataRepository,
    ScenarioRepository,
    ResultRepository
)

__all__ = [
    "IOptimizationDataRepository",
    "IScenarioRepository",
    "IResultRepository",
    "OptimizationDataRepository",
    "ScenarioRepository",
    "ResultRepository"
]
