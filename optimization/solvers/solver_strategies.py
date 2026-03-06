"""
Solver configuration and execution
Implements Strategy Pattern for different solvers
"""
from abc import ABC, abstractmethod
from pyomo.environ import SolverFactory, SolverStatus, TerminationCondition
from pyomo.opt import SolverResults
from typing import Optional, Dict, Any


class ISolverStrategy(ABC):
    """
    Abstract solver strategy
    Implements Open/Closed Principle - open for extension
    """
    
    @abstractmethod
    def solve(self, model, **kwargs) -> SolverResults:
        """Execute solver on model"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get solver name"""
        pass


class CBCSolverStrategy(ISolverStrategy):
    """CBC (COIN-OR Branch and Cut) Solver"""
    
    def __init__(self):
        self.solver = SolverFactory('cbc')
    
    def solve(self, model, time_limit: int = 300, mip_gap: float = 0.01, **kwargs) -> SolverResults:
        """
        Solve with CBC
        
        Args:
            model: Pyomo model
            time_limit: Maximum time in seconds
            mip_gap: MIP gap tolerance
        """
        options = {
            'sec': time_limit,
            'ratio': mip_gap,
            'threads': 4
        }
        
        return self.solver.solve(model, tee=True, options=options)
    
    def get_name(self) -> str:
        return "cbc"


class GLPKSolverStrategy(ISolverStrategy):
    """GLPK (GNU Linear Programming Kit) Solver"""
    
    def __init__(self):
        self.solver = SolverFactory('glpk')
    
    def solve(self, model, time_limit: int = 300, mip_gap: float = 0.01, **kwargs) -> SolverResults:
        """
        Solve with GLPK
        
        Args:
            model: Pyomo model
            time_limit: Maximum time in seconds
            mip_gap: MIP gap tolerance
        """
        options = {
            'tmlim': time_limit,
            'mipgap': mip_gap
        }
        
        return self.solver.solve(model, tee=True, options=options)
    
    def get_name(self) -> str:
        return "glpk"


class GurobiSolverStrategy(ISolverStrategy):
    """Gurobi Solver (commercial, optional)"""
    
    def __init__(self):
        self.solver = SolverFactory('gurobi')
    
    def solve(self, model, time_limit: int = 300, mip_gap: float = 0.01, **kwargs) -> SolverResults:
        """Solve with Gurobi"""
        self.solver.options['TimeLimit'] = time_limit
        self.solver.options['MIPGap'] = mip_gap
        self.solver.options['Threads'] = 4
        
        return self.solver.solve(model, tee=True)
    
    def get_name(self) -> str:
        return "gurobi"


class SolverFactory:
    """
    Factory for creating solver strategies
    Implements Factory Pattern
    """
    
    _strategies = {
        'cbc': CBCSolverStrategy,
        'glpk': GLPKSolverStrategy,
        'gurobi': GurobiSolverStrategy
    }
    
    @classmethod
    def create_solver(cls, solver_name: str) -> ISolverStrategy:
        """
        Create solver strategy by name
        
        Args:
            solver_name: Name of solver (cbc, glpk, gurobi)
        
        Returns:
            Solver strategy instance
        
        Raises:
            ValueError: If solver not supported
        """
        solver_class = cls._strategies.get(solver_name.lower())
        if not solver_class:
            raise ValueError(
                f"Solver '{solver_name}' not supported. "
                f"Available: {list(cls._strategies.keys())}"
            )
        
        return solver_class()
    
    @classmethod
    def list_available_solvers(cls) -> list[str]:
        """Get list of available solver names"""
        return list(cls._strategies.keys())


def interpret_solver_status(results: SolverResults) -> Dict[str, Any]:
    """
    Interpret solver results
    
    Returns:
        Dictionary with status information
    """
    solver_status = results.solver.status
    termination_condition = results.solver.termination_condition
    
    status_info = {
        "solver_status": str(solver_status),
        "termination_condition": str(termination_condition),
        "is_optimal": False,
        "is_feasible": False,
        "message": ""
    }
    
    if solver_status == SolverStatus.ok:
        if termination_condition == TerminationCondition.optimal:
            status_info["is_optimal"] = True
            status_info["is_feasible"] = True
            status_info["message"] = "Optimal solution found"
        elif termination_condition == TerminationCondition.feasible:
            status_info["is_feasible"] = True
            status_info["message"] = "Feasible solution found (not proven optimal)"
        else:
            status_info["message"] = f"Solver terminated: {termination_condition}"
    elif solver_status == SolverStatus.warning:
        status_info["message"] = "Solver finished with warnings"
    elif solver_status == SolverStatus.error:
        status_info["message"] = "Solver encountered an error"
    else:
        status_info["message"] = f"Unknown solver status: {solver_status}"
    
    return status_info
