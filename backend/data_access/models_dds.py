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

    fact_id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Foreign Keys
    product_sk = Column(Integer, ForeignKey("dds.dim_product.product_sk"), nullable=False, index=True)
    warehouse_sk = Column(Integer, ForeignKey("dds.dim_warehouse.warehouse_sk"), nullable=False, index=True)
    time_period_sk = Column(Integer, ForeignKey("dds.dim_time.time_period_sk"), nullable=False, index=True)

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
    product_sk = Column(Integer, ForeignKey("dds.dim_product.product_sk"), nullable=False)
    warehouse_sk = Column(Integer, ForeignKey("dds.dim_warehouse.warehouse_sk"), nullable=False)
    box_id = Column(Integer, nullable=False)
    pack_multiple = Column(Integer, nullable=False)
    box_volume = Column(Numeric(10, 2))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DDSModelParameters(BaseDDS):
    """Model Parameters"""
    __tablename__ = "dds_model_parameters"

    param_id = Column(Integer, primary_key=True, autoincrement=True)
    param_name = Column(String(50), nullable=False, unique=True)
    param_value = Column(Numeric(18, 6))
    param_description = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
