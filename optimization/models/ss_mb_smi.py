"""
SS-MB-SMI Pyomo Optimization Model
Exactly implements the mathematical formulation provided
"""
from pyomo.environ import (
    ConcreteModel, Set, Param, Var,
    NonNegativeIntegers, NonNegativeReals, Binary,
    Objective, Constraint, minimize, value
)
from backend.schemas.optimization import OptimizationInput
from typing import Dict, Tuple, Any


def build_ss_mb_smi_model(data: OptimizationInput) -> ConcreteModel:
    """
    Build the SS-MB-SMI MILP model
    
    Args:
        data: OptimizationInput containing all parameters
    
    Returns:
        ConcreteModel ready to solve
    """
    model = ConcreteModel(name="SS_MB_SMI")

    # =========================
    # SETS
    # =========================
    model.I = Set(initialize=data.I, doc="Items (products)")
    model.J = Set(initialize=data.J, doc="FGPs (warehouses)")
    model.T = Set(initialize=data.T, doc="Time periods", ordered=True)

    # =========================
    # PARAMETERS
    # =========================
    model.BI = Param(model.I, model.J, initialize=data.BI, doc="Beginning inventory")
    model.CP = Param(model.I, model.J, initialize=data.CP, doc="Case pack quantity")

    model.Cb = Param(model.I, model.J, model.T, initialize=data.Cb, doc="Backorder cost")
    model.Co = Param(model.I, model.J, model.T, initialize=data.Co, doc="Overstock cost")
    model.Cs = Param(model.I, model.J, model.T, initialize=data.Cs, doc="Shortage cost")
    model.Cp = Param(model.I, model.J, model.T, initialize=data.Cp, doc="Penalty cost")

    model.U = Param(model.I, model.J, model.T, initialize=data.U, doc="Upper inventory bound")
    model.L = Param(model.I, model.J, model.T, initialize=data.L, doc="Lower inventory bound")

    model.CAP = Param(model.I, model.T, initialize=data.CAP, doc="Vendor capacity")
    model.DI = Param(model.I, model.J, model.T, initialize=data.DI, doc="Delta inventory")

    model.HV = Param(initialize=data.HV, doc="High value constant for linearization")

    # =========================
    # DECISION VARIABLES
    # =========================
    model.q = Var(
        model.I, model.J, model.T,
        domain=NonNegativeIntegers,
        doc="Number of case packs"
    )
    
    model.r = Var(
        model.I, model.J, model.T,
        domain=NonNegativeIntegers,
        doc="Residual units"
    )

    model.I_inv = Var(
        model.I, model.J, model.T,
        domain=NonNegativeReals,
        doc="Net inventory level"
    )

    model.bo = Var(
        model.I, model.J, model.T,
        domain=NonNegativeReals,
        doc="Backorder quantity"
    )
    
    model.o = Var(
        model.I, model.J, model.T,
        domain=NonNegativeReals,
        doc="Overstock quantity"
    )
    
    model.s = Var(
        model.I, model.J, model.T,
        domain=NonNegativeReals,
        doc="Shortage quantity"
    )

    model.p = Var(
        model.I, model.J, model.T,
        domain=Binary,
        doc="Penalty binary flag"
    )

    # =========================
    # OBJECTIVE FUNCTION (1)
    # =========================
    def total_cost_rule(m):
        """Minimize total cost"""
        return sum(
            m.Co[i, j, t] * m.o[i, j, t] +
            m.Cs[i, j, t] * m.s[i, j, t] +
            m.Cb[i, j, t] * m.bo[i, j, t] +
            m.Cp[i, j, t] * m.p[i, j, t]
            for i in m.I for j in m.J for t in m.T
        )

    model.OBJ = Objective(rule=total_cost_rule, sense=minimize, doc="Total cost objective")

    # =========================
    # CONSTRAINTS
    # =========================

    # (2) Inventory balance – t = 1 (first period)
    def inventory_init_rule(m, i, j):
        """Initial inventory balance"""
        t0 = m.T.first()
        return m.I_inv[i, j, t0] == (
            m.BI[i, j] +
            m.DI[i, j, t0] +
            m.q[i, j, t0] * m.CP[i, j] +
            m.r[i, j, t0]
        )
    
    model.InventoryInit = Constraint(
        model.I, model.J,
        rule=inventory_init_rule,
        doc="Inventory balance for t=1"
    )

    # (3) Inventory balance – t >= 2
    def inventory_flow_rule(m, i, j, t):
        """Inventory flow for subsequent periods"""
        if t == m.T.first():
            return Constraint.Skip
        t_prev = m.T.prev(t)
        return m.I_inv[i, j, t] == (
            m.I_inv[i, j, t_prev] +
            m.DI[i, j, t] +
            m.q[i, j, t] * m.CP[i, j] +
            m.r[i, j, t]
        )
    
    model.InventoryFlow = Constraint(
        model.I, model.J, model.T,
        rule=inventory_flow_rule,
        doc="Inventory flow for t>=2"
    )

    # (4) Capacity constraint
    def capacity_rule(m, i, t):
        """Vendor capacity must be met exactly"""
        return sum(
            m.q[i, j, t] * m.CP[i, j] + m.r[i, j, t]
            for j in m.J
        ) == m.CAP[i, t]
    
    model.CapacityConstraint = Constraint(
        model.I, model.T,
        rule=capacity_rule,
        doc="Capacity equality constraint"
    )

    # (5) Backorder linearization
    def backorder_rule(m, i, j, t):
        """Backorder >= -I (when inventory is negative)"""
        return m.bo[i, j, t] >= -m.I_inv[i, j, t]
    
    model.BackorderConstraint = Constraint(
        model.I, model.J, model.T,
        rule=backorder_rule,
        doc="Backorder linearization"
    )

    # (6) Overstock linearization
    def overstock_rule(m, i, j, t):
        """Overstock >= I - U (when above upper bound)"""
        return m.o[i, j, t] >= m.I_inv[i, j, t] - m.U[i, j, t]
    
    model.OverstockConstraint = Constraint(
        model.I, model.J, model.T,
        rule=overstock_rule,
        doc="Overstock linearization"
    )

    # (7) Shortage linearization
    def shortage_rule(m, i, j, t):
        """Shortage >= L - I (when below lower bound)"""
        return m.s[i, j, t] >= m.L[i, j, t] - m.I_inv[i, j, t]
    
    model.ShortageConstraint = Constraint(
        model.I, model.J, model.T,
        rule=shortage_rule,
        doc="Shortage linearization"
    )

    # (8) Linearization – upper bound for residual
    def residual_upper_rule(m, i, j, t):
        """r <= HV * p (if p=0, r must be 0)"""
        return m.r[i, j, t] <= m.HV * m.p[i, j, t]
    
    model.ResidualUpper = Constraint(
        model.I, model.J, model.T,
        rule=residual_upper_rule,
        doc="Residual upper bound linearization"
    )

    # (9) Linearization – lower bound for residual
    def residual_lower_rule(m, i, j, t):
        """r >= HV * (p - 1) + 1 (if p=1, r >= 1)"""
        return m.r[i, j, t] >= m.HV * (m.p[i, j, t] - 1) + 1
    
    model.ResidualLower = Constraint(
        model.I, model.J, model.T,
        rule=residual_lower_rule,
        doc="Residual lower bound linearization"
    )

    return model


def extract_solution(model: ConcreteModel, data: OptimizationInput) -> Dict[str, Any]:
    """
    Extract solution from solved model
    
    Args:
        model: Solved Pyomo model
        data: Original input data
    
    Returns:
        Dictionary with solution details
    """
    results = []
    
    for i in model.I:
        for j in model.J:
            for t in model.T:
                results.append({
                    "product_id": i,
                    "warehouse_id": j,
                    "box_id": 1,  # Default, should be mapped from CP
                    "time_period": t,
                    "q_case_pack": int(value(model.q[i, j, t])),
                    "r_residual_units": int(value(model.r[i, j, t])),
                    "net_inventory": float(value(model.I_inv[i, j, t])),
                    "backorder_qty": float(value(model.bo[i, j, t])),
                    "overstock_qty": float(value(model.o[i, j, t])),
                    "shortage_qty": float(value(model.s[i, j, t])),
                    "penalty_flag": bool(value(model.p[i, j, t]) > 0.5)
                })
    
    return {
        "results": results,
        "objective_value": value(model.OBJ),
        "num_variables": model.nvariables(),
        "num_constraints": model.nconstraints()
    }
