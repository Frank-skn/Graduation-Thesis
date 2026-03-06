"""
Database initialization script
Run this to initialize databases and load sample data
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import engine_nds, engine_dds, BaseNDS, BaseDDS
from backend.data_access.models_nds import Scenario, OptimizationRun, OptimizationResult, DssKPI
from backend.data_access.models_dds import (
    DimProduct, DimWarehouse, DimTime, FactInventorySMI,
    DDSPackingConfig, DDSModelParameters
)


def init_databases():
    """Initialize database tables"""
    print("Creating NDS tables...")
    BaseNDS.metadata.create_all(bind=engine_nds)
    print("NDS tables created successfully")
    
    print("Creating DDS tables...")
    BaseDDS.metadata.create_all(bind=engine_dds)
    print("DDS tables created successfully")
    
    print("\nDatabase initialization complete!")
    print("\nNext steps:")
    print("1. Run SQL scripts in database/nds/ and database/dds/ for full schema")
    print("2. Load operational data into NDS")
    print("3. Run ETL: EXEC SMI_DDS.dbo.SP_RUN_FULL_ETL")


if __name__ == "__main__":
    init_databases()
