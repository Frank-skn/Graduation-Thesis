"""
SQLAlchemy ORM models for NDS (Normalized Data Store)
Schema: nds
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.core.database import BaseNDS
from datetime import datetime


class Scenario(BaseNDS):
    """Scenario Management"""
    __tablename__ = "scenario"

    scenario_id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100))
    is_baseline = Column(Boolean, default=False)

    # Relationships
    optimization_runs = relationship("OptimizationRun", back_populates="scenario")
    what_if_scenarios = relationship("WhatIfScenario", back_populates="scenario")


class OptimizationRun(BaseNDS):
    """Optimization Run History"""
    __tablename__ = "optimization_run"

    run_id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey("scenario.scenario_id"), nullable=False, index=True)
    run_time = Column(DateTime, default=datetime.utcnow)
    solver_status = Column(String(50))
    solve_time_seconds = Column(Numeric(10, 2))
    objective_value = Column(Numeric(18, 2))
    mip_gap = Column(Numeric(10, 6))

    # Relationships
    scenario = relationship("Scenario", back_populates="optimization_runs")
    results = relationship("OptimizationResult", back_populates="run")
    kpis = relationship("DssKPI", back_populates="run", uselist=False)


class OptimizationResult(BaseNDS):
    """Optimization Results"""
    __tablename__ = "optimization_result"

    result_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("optimization_run.run_id"), nullable=False, index=True)
    product_id = Column(String(50), nullable=False)
    warehouse_id = Column(String(50), nullable=False)
    box_id = Column(Integer, nullable=False)
    time_period = Column(Integer, nullable=False)
    q_case_pack = Column(Integer, nullable=False)
    r_residual_units = Column(Integer, nullable=False)
    net_inventory = Column(Numeric(18, 2))
    backorder_qty = Column(Numeric(18, 2))
    overstock_qty = Column(Numeric(18, 2))
    shortage_qty = Column(Numeric(18, 2))
    penalty_flag = Column(Boolean)

    # Relationships
    run = relationship("OptimizationRun", back_populates="results")


class DssKPI(BaseNDS):
    """DSS KPIs Summary"""
    __tablename__ = "dss_kpi"

    kpi_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("optimization_run.run_id"), nullable=False, unique=True)
    total_cost = Column(Numeric(18, 2))
    total_backorder = Column(Numeric(18, 2))
    total_overstock = Column(Numeric(18, 2))
    total_shortage = Column(Numeric(18, 2))
    total_penalty = Column(Numeric(18, 2))
    cost_backorder = Column(Numeric(18, 2), default=0)
    cost_overstock = Column(Numeric(18, 2), default=0)
    cost_shortage  = Column(Numeric(18, 2), default=0)
    cost_penalty   = Column(Numeric(18, 2), default=0)
    service_level = Column(Numeric(5, 2))
    capacity_utilization = Column(Numeric(5, 2))

    # Relationships
    run = relationship("OptimizationRun", back_populates="kpis")


class WhatIfScenario(BaseNDS):
    """What-If Scenario tracking"""
    __tablename__ = "what_if_scenario"

    whatif_id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey("scenario.scenario_id"), nullable=False, index=True)
    whatif_type = Column(String(50), nullable=False, index=True)
    parameter_overrides = Column(Text)  # JSON
    status = Column(String(20), default='pending')
    run_id = Column(Integer, ForeignKey("optimization_run.run_id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    scenario = relationship("Scenario", back_populates="what_if_scenarios")
    optimization_run = relationship("OptimizationRun")


class SensitivityRun(BaseNDS):
    """Sensitivity Analysis Run"""
    __tablename__ = "sensitivity_run"

    sensitivity_id = Column(Integer, primary_key=True, autoincrement=True)
    base_run_id = Column(Integer, ForeignKey("optimization_run.run_id"), nullable=False, index=True)
    parameter_name = Column(String(50), nullable=False)
    variation_points = Column(Text)  # JSON
    results = Column(Text)  # JSON
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    base_run = relationship("OptimizationRun")


class DatasetVersion(BaseNDS):
    """Dataset Version Tracking"""
    __tablename__ = "dataset_version"

    version_id = Column(Integer, primary_key=True, autoincrement=True)
    version_name = Column(String(200), nullable=False)
    description = Column(Text)
    snapshot_data = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100))
    is_active = Column(Boolean, default=True)


class ModelParameter(BaseNDS):
    """Model Parameters stored in SQLite (replaces DDSModelParameters)."""
    __tablename__ = "model_parameter"

    param_id = Column(Integer, primary_key=True, autoincrement=True)
    param_name = Column(String(50), nullable=False, unique=True)
    param_value = Column(Numeric(18, 6))
    param_description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DssRunSummary(BaseNDS):
    """Extended run summary: baseline cost, savings, SI/SS metrics."""
    __tablename__ = "dss_run_summary"

    summary_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("optimization_run.run_id"), unique=True, nullable=False)
    baseline_cost = Column(Numeric(18, 2), default=0)
    opt_cost = Column(Numeric(18, 2), default=0)
    savings = Column(Numeric(18, 2), default=0)
    savings_pct = Column(Numeric(5, 2), default=0)
    n_changes = Column(Integer, default=0)          # rows with p=1
    si_mean = Column(Numeric(10, 4), default=0)     # mean Safety Index
    ss_below_count = Column(Integer, default=0)     # rows where I < L

    run = relationship("OptimizationRun")
