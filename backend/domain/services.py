"""
Optimization service orchestration
Implements business logic for optimization workflows
Follows Single Responsibility Principle
"""
from dataclasses import dataclass
from typing import Dict, Any
from backend.schemas.optimization import OptimizationInput, OptimizationOutput
from optimization.models.ss_mb_smi import build_ss_mb_smi_model, extract_solution
from optimization.solvers.solver_strategies import SolverFactory, interpret_solver_status


@dataclass
class OptimizationResult:
    """Container for optimization results"""
    solver_status: str
    solve_time: float
    objective_value: float
    mip_gap: float
    output: OptimizationOutput
    kpis: Dict[str, float]
    is_optimal: bool
    is_feasible: bool
    message: str


class OptimizationService:
    """
    Service for executing optimization
    Orchestrates model building, solving, and result extraction
    """
    
    def __init__(
        self,
        solver: str = "cbc",
        time_limit: int = 300,
        mip_gap: float = 0.01
    ):
        """
        Initialize optimization service
        
        Args:
            solver: Solver name (cbc, glpk, gurobi)
            time_limit: Time limit in seconds
            mip_gap: MIP gap tolerance
        """
        self.solver_strategy = SolverFactory.create_solver(solver)
        self.time_limit = time_limit
        self.mip_gap = mip_gap
    
    def solve(self, data: OptimizationInput) -> OptimizationResult:
        """
        Execute optimization workflow
        
        Args:
            data: Optimization input data
        
        Returns:
            OptimizationResult with solution and metadata
        
        Raises:
            RuntimeError: If optimization fails
        """
        # Step 1: Build model
        print(f"Building SS-MB-SMI model...")
        model = build_ss_mb_smi_model(data)
        print(f"Model built: {model.nvariables()} variables, {model.nconstraints()} constraints")
        
        # Step 2: Solve model
        print(f"Solving with {self.solver_strategy.get_name()}...")
        results = self.solver_strategy.solve(
            model,
            time_limit=self.time_limit,
            mip_gap=self.mip_gap
        )
        
        # Step 3: Interpret results
        status_info = interpret_solver_status(results)
        
        if not status_info["is_feasible"]:
            raise RuntimeError(
                f"Optimization failed: {status_info['message']}"
            )
        
        # Step 4: Extract solution
        print("Extracting solution...")
        solution = extract_solution(model, data)
        
        # Step 5: Calculate KPIs
        kpis = self._calculate_kpis(solution["results"], data)
        
        # Step 6: Get solve time and gap
        solve_time = getattr(results.solver, 'time', 0.0)
        actual_gap = self._extract_mip_gap(results)
        
        return OptimizationResult(
            solver_status=status_info["solver_status"],
            solve_time=solve_time,
            objective_value=solution["objective_value"],
            mip_gap=actual_gap,
            output=OptimizationOutput(results=solution["results"]),
            kpis=kpis,
            is_optimal=status_info["is_optimal"],
            is_feasible=status_info["is_feasible"],
            message=status_info["message"]
        )
    
    def _calculate_kpis(
        self,
        results: list[Dict[str, Any]],
        data: OptimizationInput
    ) -> Dict[str, float]:
        """
        Calculate KPIs from solution
        
        Args:
            results: List of result records
            data: Original optimization input
        
        Returns:
            Dictionary of KPIs
        """
        total_backorder = sum(r["backorder_qty"] for r in results)
        total_overstock = sum(r["overstock_qty"] for r in results)
        total_shortage = sum(r["shortage_qty"] for r in results)
        total_penalty = sum(1 if r["penalty_flag"] else 0 for r in results)
        
        # Calculate costs
        total_cost_backorder = 0
        total_cost_overstock = 0
        total_cost_shortage = 0
        total_cost_penalty = 0
        
        for r in results:
            i = r["product_id"]
            j = r["warehouse_id"]
            t = r["time_period"]
            
            if (i, j, t) in data.Cb:
                total_cost_backorder += data.Cb[(i, j, t)] * r["backorder_qty"]
            if (i, j, t) in data.Co:
                total_cost_overstock += data.Co[(i, j, t)] * r["overstock_qty"]
            if (i, j, t) in data.Cs:
                total_cost_shortage += data.Cs[(i, j, t)] * r["shortage_qty"]
            if (i, j, t) in data.Cp:
                total_cost_penalty += data.Cp[(i, j, t)] * (1 if r["penalty_flag"] else 0)
        
        total_cost = (
            total_cost_backorder +
            total_cost_overstock +
            total_cost_shortage +
            total_cost_penalty
        )
        
        # Service level (simplified: % of periods without backorder)
        periods_without_backorder = sum(
            1 for r in results if r["backorder_qty"] == 0
        )
        service_level = (periods_without_backorder / len(results) * 100) if results else 0
        
        # Capacity utilization
        total_capacity = sum(data.CAP.values())
        total_used = sum(
            r["q_case_pack"] * data.CP.get((r["product_id"], r["warehouse_id"]), 1) +
            r["r_residual_units"]
            for r in results
        )
        capacity_utilization = (total_used / total_capacity * 100) if total_capacity > 0 else 0
        
        return {
            "total_cost": total_cost,
            "total_backorder": total_backorder,
            "total_overstock": total_overstock,
            "total_shortage": total_shortage,
            "total_penalty": total_penalty,
            "service_level": service_level,
            "capacity_utilization": capacity_utilization
        }
    
    def _extract_mip_gap(self, results) -> float:
        """Extract MIP gap from solver results"""
        try:
            if hasattr(results.solution, 'gap'):
                return float(results.solution.gap)
            return self.mip_gap
        except:
            return self.mip_gap
