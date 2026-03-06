"""
Concrete repository implementations
Implements Repository Pattern - encapsulates data access logic
Follows Single Responsibility Principle
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.data_access.interfaces import (
    IOptimizationDataRepository,
    IScenarioRepository,
    IResultRepository
)
from backend.data_access.models_dds import (
    DimProduct, DimWarehouse, DimTime, FactInventorySMI, DDSPackingConfig, DDSModelParameters
)
from backend.data_access.models_nds import Scenario, OptimizationRun, OptimizationResult, DssKPI, DssRunSummary
from backend.schemas.optimization import OptimizationInput, OptimizationOutput


class OptimizationDataRepository(IOptimizationDataRepository):
    """Repository for fetching optimization data from DDS"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def get_products(self) -> List[str]:
        """Get active product IDs"""
        products = self.db.query(DimProduct.product_id).filter(
            DimProduct.is_current == True
        ).all()
        return [p[0] for p in products]
    
    def get_warehouses(self) -> List[str]:
        """Get active warehouse IDs"""
        warehouses = self.db.query(DimWarehouse.warehouse_id).filter(
            DimWarehouse.is_current == True
        ).all()
        return [w[0] for w in warehouses]
    
    def get_time_periods(self) -> List[int]:
        """Get time periods in order"""
        periods = self.db.query(DimTime.time_period).order_by(DimTime.time_period).all()
        return [t[0] for t in periods]
    
    def get_optimization_input(self) -> OptimizationInput:
        """
        Fetch all optimization input data from DDS
        Returns structured data matching Pyomo model requirements
        """
        # Get sets
        I = self.get_products()
        J = self.get_warehouses()
        T = self.get_time_periods()
        
        # Get parameters from fact table
        facts = self.db.query(FactInventorySMI).join(
            DimProduct, FactInventorySMI.product_sk == DimProduct.product_sk
        ).join(
            DimWarehouse, FactInventorySMI.warehouse_sk == DimWarehouse.warehouse_sk
        ).join(
            DimTime, FactInventorySMI.time_period_sk == DimTime.time_period_sk
        ).filter(
            DimProduct.is_current == True,
            DimWarehouse.is_current == True
        ).all()
        
        # Get packing configuration (CP values)
        packing = self.db.query(DDSPackingConfig).join(
            DimProduct, DDSPackingConfig.product_sk == DimProduct.product_sk
        ).join(
            DimWarehouse, DDSPackingConfig.warehouse_sk == DimWarehouse.warehouse_sk
        ).filter(
            DDSPackingConfig.is_active == True
        ).all()
        
        # Build parameter dictionaries
        BI = {}  # Beginning inventory
        CP = {}  # Case pack
        U = {}   # Upper bound
        L = {}   # Lower bound
        DI = {}  # Delta inventory
        CAP = {}  # Capacity
        Cb = {}  # Backorder cost
        Co = {}  # Overstock cost
        Cs = {}  # Shortage cost
        Cp = {}  # Penalty cost
        
        # Process facts
        for fact in facts:
            i = fact.product.product_id
            j = fact.warehouse.warehouse_id
            t = fact.time_period.time_period
            
            BI[(i, j)] = fact.beginning_inventory_qty
            U[(i, j, t)] = fact.inventory_ceiling
            L[(i, j, t)] = fact.inventory_floor
            DI[(i, j, t)] = fact.delta_inventory_qty
            CAP[(i, t)] = fact.firm_capacity_qty
            Cb[(i, j, t)] = float(fact.cost_backorder or 0)
            Co[(i, j, t)] = float(fact.cost_overstock or 0)
            Cs[(i, j, t)] = float(fact.cost_shortage or 0)
            Cp[(i, j, t)] = float(fact.cost_penalty or 0)
        
        # Process packing
        for pack in packing:
            i = pack.product.product_id
            j = pack.warehouse.warehouse_id
            CP[(i, j)] = pack.pack_multiple
        
        # Get HV parameter
        hv_param = self.db.query(DDSModelParameters).filter(
            DDSModelParameters.param_name == "HV"
        ).first()
        HV = float(hv_param.param_value) if hv_param else 9999
        
        return OptimizationInput(
            I=I, J=J, T=T,
            BI=BI, CP=CP, U=U, L=L, DI=DI, CAP=CAP,
            Cb=Cb, Co=Co, Cs=Cs, Cp=Cp, HV=HV
        )


class ScenarioRepository(IScenarioRepository):
    """Repository for scenario management"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_scenario(self, name: str, description: str, created_by: str) -> int:
        """Create new scenario"""
        scenario = Scenario(
            scenario_name=name,
            description=description,
            created_by=created_by
        )
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        return scenario.scenario_id
    
    def get_scenario(self, scenario_id: int) -> Optional[Dict[str, Any]]:
        """Get scenario by ID"""
        scenario = self.db.query(Scenario).filter(Scenario.scenario_id == scenario_id).first()
        if not scenario:
            return None
        return {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.scenario_name,
            "description": scenario.description,
            "created_at": scenario.created_at,
            "created_by": scenario.created_by,
            "is_baseline": scenario.is_baseline
        }
    
    def list_scenarios(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all scenarios"""
        scenarios = self.db.query(Scenario).order_by(
            Scenario.created_at.desc()
        ).limit(limit).all()
        
        return [{
            "scenario_id": s.scenario_id,
            "scenario_name": s.scenario_name,
            "description": s.description,
            "created_at": s.created_at,
            "created_by": s.created_by,
            "is_baseline": s.is_baseline
        } for s in scenarios]
    
    def delete_scenario(self, scenario_id: int) -> bool:
        """Delete scenario"""
        scenario = self.db.query(Scenario).filter(Scenario.scenario_id == scenario_id).first()
        if not scenario:
            return False
        self.db.delete(scenario)
        self.db.commit()
        return True


class ResultRepository(IResultRepository):
    """Repository for optimization results"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def save_optimization_run(
        self,
        scenario_id: int,
        solver_status: str,
        solve_time: float,
        objective_value: float,
        mip_gap: float
    ) -> int:
        """Save optimization run metadata"""
        run = OptimizationRun(
            scenario_id=scenario_id,
            solver_status=solver_status,
            solve_time_seconds=solve_time,
            objective_value=objective_value,
            mip_gap=mip_gap
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run.run_id
    
    def save_results(self, run_id: int, results: OptimizationOutput) -> None:
        """Save detailed optimization results"""
        for result_dict in results.results:
            result = OptimizationResult(
                run_id=run_id,
                **result_dict
            )
            self.db.add(result)
        self.db.commit()
    
    def get_results(self, run_id: int) -> Optional[OptimizationOutput]:
        """Retrieve results"""
        results = self.db.query(OptimizationResult).filter(
            OptimizationResult.run_id == run_id
        ).all()
        
        if not results:
            return None
        
        results_list = [{
            "product_id": r.product_id,
            "warehouse_id": r.warehouse_id,
            "box_id": r.box_id,
            "time_period": r.time_period,
            "q_case_pack": r.q_case_pack,
            "r_residual_units": r.r_residual_units,
            "net_inventory": float(r.net_inventory or 0),
            "backorder_qty": float(r.backorder_qty or 0),
            "overstock_qty": float(r.overstock_qty or 0),
            "shortage_qty": float(r.shortage_qty or 0),
            "penalty_flag": r.penalty_flag
        } for r in results]
        
        return OptimizationOutput(results=results_list)
    
    def save_kpis(self, run_id: int, kpis: Dict[str, float]) -> None:
        """Save KPIs"""
        kpi = DssKPI(run_id=run_id, **kpis)
        self.db.add(kpi)
        self.db.commit()
    
    def get_kpis(self, run_id: int) -> Optional[Dict[str, float]]:
        """Get KPIs"""
        kpi = self.db.query(DssKPI).filter(DssKPI.run_id == run_id).first()
        if not kpi:
            return None
        return {
            "total_cost": float(kpi.total_cost or 0),
            "total_backorder": float(kpi.total_backorder or 0),
            "total_overstock": float(kpi.total_overstock or 0),
            "total_shortage": float(kpi.total_shortage or 0),
            "total_penalty": float(kpi.total_penalty or 0),
            "cost_backorder": float(kpi.cost_backorder or 0),
            "cost_overstock": float(kpi.cost_overstock or 0),
            "cost_shortage":  float(kpi.cost_shortage  or 0),
            "cost_penalty":   float(kpi.cost_penalty   or 0),
            "service_level": float(kpi.service_level or 0),
            "capacity_utilization": float(kpi.capacity_utilization or 0)
        }

    def save_run_summary(
        self,
        run_id: int,
        baseline_cost: float,
        opt_cost: float,
        savings: float,
        savings_pct: float,
        n_changes: int,
        si_mean: float,
        ss_below_count: int,
    ) -> None:
        """Persist the extended run summary (baseline cost, savings, SI/SS)."""
        existing = self.db.query(DssRunSummary).filter(DssRunSummary.run_id == run_id).first()
        if existing:
            existing.baseline_cost = baseline_cost
            existing.opt_cost = opt_cost
            existing.savings = savings
            existing.savings_pct = savings_pct
            existing.n_changes = n_changes
            existing.si_mean = si_mean
            existing.ss_below_count = ss_below_count
        else:
            summary = DssRunSummary(
                run_id=run_id,
                baseline_cost=baseline_cost,
                opt_cost=opt_cost,
                savings=savings,
                savings_pct=savings_pct,
                n_changes=n_changes,
                si_mean=si_mean,
                ss_below_count=ss_below_count,
            )
            self.db.add(summary)
        self.db.commit()

    def get_run_summary(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get the extended run summary."""
        s = self.db.query(DssRunSummary).filter(DssRunSummary.run_id == run_id).first()
        if not s:
            return None
        return {
            "run_id": run_id,
            "baseline_cost": float(s.baseline_cost or 0),
            "opt_cost": float(s.opt_cost or 0),
            "savings": float(s.savings or 0),
            "savings_pct": float(s.savings_pct or 0),
            "n_changes": int(s.n_changes or 0),
            "si_mean": float(s.si_mean or 0),
            "ss_below_count": int(s.ss_below_count or 0),
        }
