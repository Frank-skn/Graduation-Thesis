"""
FastAPI application main file
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import get_settings
from backend.api.v1 import api_router

settings = get_settings()

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Decision Support System for Single-Supplier Multi-Buyer SMI Optimization",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.api_prefix)


@app.on_event("startup")
def startup_event():
    """
    On startup:
    1. Import all NDS models so SQLAlchemy discovers them.
    2. Create SQLite tables if they don't exist.
    3. Migrate: add any missing columns (safe ALTER TABLE).
    4. Seed default model parameters (HV).
    """
    # Import models to register with BaseNDS metadata
    from backend.data_access import models_nds  # noqa: F401
    from backend.core.database import engine, BaseNDS, SessionLocal
    from sqlalchemy import text

    # Create all tables in SQLite
    BaseNDS.metadata.create_all(bind=engine)

    # --- DDS (kho dữ liệu chiều) — tạo bảng star schema trong dds.db ---
    from backend.data_access import models_dds  # noqa: F401
    from backend.core.database import engine_dds, BaseDDS
    BaseDDS.metadata.create_all(bind=engine_dds)

    # --- ETL: nạp CSV → DDS (idempotent). Chạy nếu DDS rỗng. ---
    try:
        from backend.core.database import SessionLocalDDS
        from backend.data_access.models_dds import FactInventorySMI
        from backend.data_access.dds_etl import run_etl
        _dds_db = SessionLocalDDS()
        try:
            n_fact = _dds_db.query(FactInventorySMI).count()
        finally:
            _dds_db.close()
        if n_fact == 0:
            from backend.core.database import _project_root
            _data_path = str(_project_root / settings.data_dir)
            run_etl(_data_path)
            print("[startup] DDS ETL nạp dữ liệu lần đầu xong.")
        else:
            print(f"[startup] DDS đã có {n_fact} bản ghi fact, bỏ qua ETL.")
    except Exception as exc:
        print(f"[startup] DDS ETL warning: {exc}")

    # --- ETL kết quả: NDS → DDS (backfill nếu nhóm bảng kết quả rỗng) ---
    try:
        from backend.core.database import SessionLocalDDS
        from backend.data_access.models_dds import DimRun
        from backend.data_access.dds_etl import run_result_etl
        _dds_db = SessionLocalDDS()
        try:
            n_run = _dds_db.query(DimRun).count()
        finally:
            _dds_db.close()
        if n_run == 0:
            counts = run_result_etl(None)  # backfill toàn bộ run có sẵn
            print(f"[startup] DDS Result ETL backfill xong: {counts}")
        else:
            print(f"[startup] DDS đã có {n_run} lần chạy trong dim_run, bỏ qua backfill.")
    except Exception as exc:
        print(f"[startup] DDS Result ETL warning: {exc}")

    # --- Safe column migrations (idempotent) ---
    # Each entry: (column_name, column_type, default_sql)
    _migrations = {
        "dss_kpi": [
            ("cost_backorder", "NUMERIC", "0"),
            ("cost_overstock", "NUMERIC", "0"),
            ("cost_shortage",  "NUMERIC", "0"),
            ("cost_penalty",   "NUMERIC", "0"),
            ("cost_transport", "NUMERIC", "0"),
        ],
        "dss_run_summary": [
            ("prop_cost",        "NUMERIC", "0"),
            ("savings_vs_prop",  "NUMERIC", "0"),
            ("savings_pct_prop", "NUMERIC", "0"),
        ],
        "sensitivity_run": [
            ("scenario_id",   "INTEGER", "NULL"),
            ("analysis_type", "TEXT",    "'oat'"),
        ],
        "optimization_run": [
            ("version_id", "INTEGER", "NULL"),
        ],
    }
    with engine.connect() as conn:
        for table, cols in _migrations.items():
            try:
                rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                existing = {r[1] for r in rows}
                for col_name, col_type, col_default in cols:
                    if col_name not in existing:
                        conn.execute(text(
                            f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type} DEFAULT {col_default}"
                        ))
                conn.commit()
            except Exception as exc:
                print(f"[startup] migration warning for {table}: {exc}")

    # Seed default model parameters
    from backend.data_access.models_nds import ModelParameter
    db = SessionLocal()
    try:
        existing = db.query(ModelParameter).filter(
            ModelParameter.param_name == "HV"
        ).first()
        if not existing:
            db.add(ModelParameter(
                param_name="HV",
                param_value=9999,
                param_description="Big-M linearization constant (a sufficiently large value used in the Big-M constraint)",
            ))
            db.commit()
    finally:
        db.close()


@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "service": "SS-MB-SMI DSS",
        "version": settings.api_version,
        "status": "running"
    }


@app.get("/health")
def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "data_source": "CSV files + SQLite",
        "data_dir": settings.data_dir,
        "sqlite_db": settings.sqlite_db_path,
    }
