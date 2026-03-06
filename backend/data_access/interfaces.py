"""
Repository interfaces (Abstract Base Classes)
Implements Interface Segregation Principle - small, focused interfaces
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from backend.schemas.optimization import OptimizationInput, OptimizationOutput


class IOptimizationDataRepository(ABC):
    """
    Interface for fetching optimization input data from DDS
    Follows Dependency Inversion - depend on abstraction
    """
    
    @abstractmethod
    def get_optimization_input(self) -> OptimizationInput:
        """Fetch all required data for optimization model"""
        pass
    
    @abstractmethod
    def get_products(self) -> List[str]:
        """Get list of product IDs (I set)"""
        pass
    
    @abstractmethod
    def get_warehouses(self) -> List[str]:
        """Get list of warehouse IDs (J set)"""
        pass
    
    @abstractmethod
    def get_time_periods(self) -> List[int]:
        """Get list of time periods (T set)"""
        pass


class IScenarioRepository(ABC):
    """Interface for scenario management"""
    
    @abstractmethod
    def create_scenario(self, name: str, description: str, created_by: str) -> int:
        """Create new scenario and return scenario_id"""
        pass
    
    @abstractmethod
    def get_scenario(self, scenario_id: int) -> Optional[Dict[str, Any]]:
        """Get scenario by ID"""
        pass
    
    @abstractmethod
    def list_scenarios(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all scenarios"""
        pass
    
    @abstractmethod
    def delete_scenario(self, scenario_id: int) -> bool:
        """Delete a scenario"""
        pass


class IResultRepository(ABC):
    """Interface for storing and retrieving optimization results"""
    
    @abstractmethod
    def save_optimization_run(
        self,
        scenario_id: int,
        solver_status: str,
        solve_time: float,
        objective_value: float,
        mip_gap: float
    ) -> int:
        """Save optimization run metadata and return run_id"""
        pass
    
    @abstractmethod
    def save_results(self, run_id: int, results: OptimizationOutput) -> None:
        """Save detailed optimization results"""
        pass
    
    @abstractmethod
    def get_results(self, run_id: int) -> Optional[OptimizationOutput]:
        """Retrieve results by run_id"""
        pass
    
    @abstractmethod
    def save_kpis(self, run_id: int, kpis: Dict[str, float]) -> None:
        """Save aggregated KPIs"""
        pass
    
    @abstractmethod
    def get_kpis(self, run_id: int) -> Optional[Dict[str, float]]:
        """Get KPIs for a run"""
        pass
