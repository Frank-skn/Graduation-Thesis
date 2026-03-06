"""
Load sample data for testing
"""
import sys
from pathlib import Path
from datetime import date, timedelta
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import SessionLocalNDS, SessionLocalDDS
from backend.data_access.models_nds import Scenario
from backend.data_access.models_dds import (
    DimProduct, DimWarehouse, DimTime, FactInventorySMI,
    DDSPackingConfig, DDSModelParameters
)


def load_sample_data():
    """Load minimal sample data for testing"""
    
    # DDS Session
    db_dds = SessionLocalDDS()
    
    try:
        print("Loading sample data into DDS...")
        
        # Products
        products = [
            DimProduct(product_id="PROD001", item_class="A", product_series="S1",
                      product_style="ST1", product_size="M", pack_kind="STANDARD",
                      effective_date=date.today(), is_current=True),
            DimProduct(product_id="PROD002", item_class="B", product_series="S1",
                      product_style="ST2", product_size="L", pack_kind="STANDARD",
                      effective_date=date.today(), is_current=True)
        ]
        db_dds.add_all(products)
        db_dds.commit()
        print("Products loaded")
        
        # Warehouses
        warehouses = [
            DimWarehouse(warehouse_id="WH01", market_code="NORTH",
                        effective_date=date.today(), is_current=True),
            DimWarehouse(warehouse_id="WH02", market_code="SOUTH",
                        effective_date=date.today(), is_current=True)
        ]
        db_dds.add_all(warehouses)
        db_dds.commit()
        print("Warehouses loaded")
        
        # Time periods
        start_date = date.today()
        time_periods = []
        for t in range(1, 7):
            period_start = start_date + timedelta(days=(t-1)*7)
            period_end = period_start + timedelta(days=6)
            time_periods.append(
                DimTime(
                    time_period=t,
                    start_date=period_start,
                    end_date=period_end,
                    week=t,
                    month=period_start.month,
                    year=period_start.year,
                    quarter=(period_start.month - 1) // 3 + 1
                )
            )
        db_dds.add_all(time_periods)
        db_dds.commit()
        print("Time periods loaded")
        
        # Model parameters
        param = DDSModelParameters(param_name="HV", param_value=9999,
                                   param_description="High value for linearization")
        db_dds.add(param)
        db_dds.commit()
        print("Model parameters loaded")
        
        # Fact data (sample)
        for product in products:
            for warehouse in warehouses:
                for time_period in time_periods:
                    fact = FactInventorySMI(
                        product_sk=product.product_sk,
                        warehouse_sk=warehouse.warehouse_sk,
                        time_period_sk=time_period.time_period_sk,
                        beginning_inventory_qty=100,
                        delta_inventory_qty=-10,
                        firm_capacity_qty=500,
                        inventory_ceiling=200,
                        inventory_floor=50,
                        cost_backorder=10.0,
                        cost_overstock=2.0,
                        cost_shortage=5.0,
                        cost_penalty=50.0
                    )
                    db_dds.add(fact)
        db_dds.commit()
        print("Fact data loaded")
        
        # Packing config
        for product in products:
            for warehouse in warehouses:
                config = DDSPackingConfig(
                    product_sk=product.product_sk,
                    warehouse_sk=warehouse.warehouse_sk,
                    box_id=1,
                    pack_multiple=50,
                    box_volume=1000.0,
                    is_active=True
                )
                db_dds.add(config)
        db_dds.commit()
        print("Packing config loaded")
        
        print("\nSample data loaded successfully!")
        
    finally:
        db_dds.close()
    
    # NDS Session
    db_nds = SessionLocalNDS()
    
    try:
        print("\nLoading sample scenarios into NDS...")
        
        # Baseline scenario
        baseline = Scenario(
            scenario_name="Baseline Scenario",
            description="Initial baseline for testing",
            created_by="system",
            is_baseline=True
        )
        db_nds.add(baseline)
        db_nds.commit()
        print("Baseline scenario created")
        
    finally:
        db_nds.close()


if __name__ == "__main__":
    load_sample_data()
