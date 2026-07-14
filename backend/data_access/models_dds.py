"""
SQLAlchemy ORM models for DDS (Dimensional Data Store)
Schema: dds
"""
from sqlalchemy import Column, Integer, String, Date, Boolean, DateTime, Numeric, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from backend.core.database import BaseDDS
from datetime import datetime


class DimProduct(BaseDDS):
    """Product Dimension"""
    __tablename__ = "dim_product"

    product_sk = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(50), nullable=False, index=True)
    item_class = Column(String(50))
    product_series = Column(String(50))
    product_style = Column(String(50))
    product_size = Column(String(50))
    pack_kind = Column(String(50))
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)
    is_current = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    facts = relationship("FactInventorySMI", back_populates="product")


class DimWarehouse(BaseDDS):
    """Warehouse Dimension"""
    __tablename__ = "dim_warehouse"

    warehouse_sk = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(String(50), nullable=False, index=True)
    market_code = Column(String(50))
    # Thời gian giao hàng từ kho trung tâm đến nhà máy này (LT_OA, tuần).
    # Thuộc tính riêng của từng kho → đặt ở dimension, không phải fact.
    lt_oa_weeks = Column(Integer)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)
    is_current = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    facts = relationship("FactInventorySMI", back_populates="warehouse")


class DimTime(BaseDDS):
    """Time Dimension"""
    __tablename__ = "dim_time"

    time_period_sk = Column(Integer, primary_key=True, autoincrement=True)
    time_period = Column(Integer, nullable=False, unique=True, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    week = Column(Integer)
    month = Column(Integer)
    year = Column(Integer)
    quarter = Column(Integer)
    is_current = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    facts = relationship("FactInventorySMI", back_populates="time_period_dim")


class FactInventorySMI(BaseDDS):
    """Main Fact Table"""
    __tablename__ = "fact_inventory_smi"

    # SQLite chỉ autoincrement với INTEGER PRIMARY KEY (không phải BigInteger)
    fact_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Keys (SQLite: không dùng schema prefix "dds.")
    product_sk = Column(Integer, ForeignKey("dim_product.product_sk"), nullable=False, index=True)
    warehouse_sk = Column(Integer, ForeignKey("dim_warehouse.warehouse_sk"), nullable=False, index=True)
    time_period_sk = Column(Integer, ForeignKey("dim_time.time_period_sk"), nullable=False, index=True)

    # Inventory Measures
    beginning_inventory_qty = Column(Integer, nullable=False)
    delta_inventory_qty = Column(Integer, nullable=False)
    net_inventory_qty = Column(Numeric(18, 2))

    # Capacity & Packing
    firm_capacity_qty = Column(Integer, nullable=False)
    q_case_pack = Column(Integer, default=0)
    r_residual_units = Column(Integer, default=0)

    # Deviation Measures
    backorder_qty = Column(Numeric(18, 2), default=0)
    overstock_qty = Column(Numeric(18, 2), default=0)
    shortage_qty = Column(Numeric(18, 2), default=0)

    # Policy Flags
    penalty_flag = Column(Boolean, default=False)

    # Packing Info
    applied_box_code = Column(Integer)
    applied_pack_multiple = Column(Integer)

    # Bounds
    inventory_ceiling = Column(Integer, nullable=False)
    inventory_floor = Column(Integer, nullable=False)

    # Costs
    cost_backorder = Column(Numeric(10, 2))
    cost_overstock = Column(Numeric(10, 2))
    cost_shortage = Column(Numeric(10, 2))
    cost_penalty = Column(Numeric(10, 2))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("DimProduct", back_populates="facts")
    warehouse = relationship("DimWarehouse", back_populates="facts")
    time_period_dim = relationship("DimTime", back_populates="facts")


class DDSPackingConfig(BaseDDS):
    """Packing Configuration"""
    __tablename__ = "dds_packing_config"

    config_id = Column(Integer, primary_key=True, autoincrement=True)
    product_sk = Column(Integer, ForeignKey("dim_product.product_sk"), nullable=False)
    warehouse_sk = Column(Integer, ForeignKey("dim_warehouse.warehouse_sk"), nullable=False)
    box_id = Column(Integer, nullable=False)
    pack_multiple = Column(Integer, nullable=False)
    box_volume = Column(Numeric(10, 2))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships (để repository truy product_id/warehouse_id qua join)
    product = relationship("DimProduct")
    warehouse = relationship("DimWarehouse")


class DDSModelParameters(BaseDDS):
    """Model Parameters"""
    __tablename__ = "dds_model_parameters"

    param_id = Column(Integer, primary_key=True, autoincrement=True)
    param_name = Column(String(50), nullable=False, unique=True)
    param_value = Column(Numeric(18, 6))
    param_description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FactPltInput(BaseDDS):
    """
    FACT_PLT_INPUT (khớp Hình 5.8 luận văn) — dữ liệu điều chuyển ngang
    giữa các cặp nhà máy: thời gian vận chuyển (LT_PLT) và khoảng cách.
    Một dòng / cặp kho (from, to) có quan hệ điều chuyển ngang.
    """
    __tablename__ = "fact_plt_input"

    plt_input_id = Column(Integer, primary_key=True, autoincrement=True)
    from_warehouse_sk = Column(Integer, ForeignKey("dim_warehouse.warehouse_sk"), nullable=False, index=True)
    to_warehouse_sk = Column(Integer, ForeignKey("dim_warehouse.warehouse_sk"), nullable=False, index=True)
    lt_plt_weeks = Column(Integer, nullable=False)
    distance_km = Column(Numeric(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow)

    from_warehouse = relationship("DimWarehouse", foreign_keys=[from_warehouse_sk])
    to_warehouse = relationship("DimWarehouse", foreign_keys=[to_warehouse_sk])


# ══════════════════════════════════════════════════════════════════════
#  Nhóm bảng KẾT QUẢ tối ưu (khớp Hình 5.8 luận văn)
#  DIM_SCENARIO, DIM_RUN + FACT_MODEL_RESULT / FACT_PLT_RESULT / FACT_RUN_SUMMARY
#  Dữ liệu được ETL từ NDS (kết quả tối ưu) sang DDS sau mỗi lần chạy.
# ══════════════════════════════════════════════════════════════════════

class DimScenario(BaseDDS):
    """Chiều kịch bản — mỗi kịch bản tối ưu (cơ sở / what-if)."""
    __tablename__ = "dim_scenario"

    scenario_sk = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, nullable=False, index=True)   # nghiệp vụ (NDS scenario_id)
    scenario_name = Column(String(200))
    scenario_type = Column(String(50))                          # baseline / what-if type
    is_baseline = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    runs = relationship("DimRun", back_populates="scenario")


class DimRun(BaseDDS):
    """Chiều lần chạy — mỗi lần thực thi giải thuật tối ưu."""
    __tablename__ = "dim_run"

    run_sk = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, nullable=False, index=True)        # nghiệp vụ (NDS run_id)
    scenario_sk = Column(Integer, ForeignKey("dim_scenario.scenario_sk"), index=True)
    solver_status = Column(String(50))
    solver_name = Column(String(50), default="Memetic (GA-ALNS)")
    objective_value = Column(Numeric(18, 2))
    solve_time_seconds = Column(Numeric(10, 2))
    run_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    scenario = relationship("DimScenario", back_populates="runs")
    model_results = relationship("FactModelResult", back_populates="run")
    plt_results = relationship("FactPltResult", back_populates="run")
    summary = relationship("FactRunSummary", back_populates="run", uselist=False)


class FactModelResult(BaseDDS):
    """Sự kiện: kết quả phân bổ (OA) theo sản phẩm × kho × kỳ × lần chạy."""
    __tablename__ = "fact_model_result"

    result_sk = Column(Integer, primary_key=True, autoincrement=True)
    run_sk = Column(Integer, ForeignKey("dim_run.run_sk"), nullable=False, index=True)
    product_sk = Column(Integer, ForeignKey("dim_product.product_sk"), index=True)
    warehouse_sk = Column(Integer, ForeignKey("dim_warehouse.warehouse_sk"), index=True)
    time_period_sk = Column(Integer, ForeignKey("dim_time.time_period_sk"), index=True)

    # Biến quyết định & trạng thái
    q_case_pack = Column(Integer, default=0)
    r_residual_units = Column(Integer, default=0)
    net_inventory = Column(Numeric(18, 2))
    backorder_qty = Column(Numeric(18, 2), default=0)
    overstock_qty = Column(Numeric(18, 2), default=0)
    shortage_qty = Column(Numeric(18, 2), default=0)
    penalty_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("DimRun", back_populates="model_results")
    product = relationship("DimProduct")
    warehouse = relationship("DimWarehouse")
    time_period_dim = relationship("DimTime")


class FactPltResult(BaseDDS):
    """Sự kiện: kết quả điều chuyển ngang (PLT) theo cặp kho × kỳ × lần chạy."""
    __tablename__ = "fact_plt_result"

    plt_result_sk = Column(Integer, primary_key=True, autoincrement=True)
    run_sk = Column(Integer, ForeignKey("dim_run.run_sk"), nullable=False, index=True)
    product_sk = Column(Integer, ForeignKey("dim_product.product_sk"), index=True)
    from_warehouse_sk = Column(Integer, ForeignKey("dim_warehouse.warehouse_sk"), index=True)
    to_warehouse_sk = Column(Integer, ForeignKey("dim_warehouse.warehouse_sk"), index=True)
    time_period_sk = Column(Integer, ForeignKey("dim_time.time_period_sk"), index=True)
    qty = Column(Numeric(18, 4), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("DimRun", back_populates="plt_results")
    product = relationship("DimProduct")
    from_warehouse = relationship("DimWarehouse", foreign_keys=[from_warehouse_sk])
    to_warehouse = relationship("DimWarehouse", foreign_keys=[to_warehouse_sk])
    time_period_dim = relationship("DimTime")


class FactRunSummary(BaseDDS):
    """Sự kiện: chỉ tiêu tổng hợp của mỗi lần chạy (chi phí, tiết kiệm, SI/SS)."""
    __tablename__ = "fact_run_summary"

    summary_sk = Column(Integer, primary_key=True, autoincrement=True)
    run_sk = Column(Integer, ForeignKey("dim_run.run_sk"), nullable=False, unique=True, index=True)

    total_cost = Column(Numeric(18, 2))
    baseline_cost = Column(Numeric(18, 2))
    opt_cost = Column(Numeric(18, 2))
    savings = Column(Numeric(18, 2))
    savings_pct = Column(Numeric(6, 2))
    total_backorder = Column(Numeric(18, 2))
    total_overstock = Column(Numeric(18, 2))
    total_shortage = Column(Numeric(18, 2))
    total_penalty = Column(Numeric(18, 2))
    si_mean = Column(Numeric(10, 4))
    ss_below_count = Column(Integer)
    n_changes = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    run = relationship("DimRun", back_populates="summary")
