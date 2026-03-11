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

    # --- Safe column migrations (idempotent) ---
    _migrations = {
        "dss_kpi": [
            ("cost_backorder", "NUMERIC"),
            ("cost_overstock", "NUMERIC"),
            ("cost_shortage",  "NUMERIC"),
            ("cost_penalty",   "NUMERIC"),
        ],
        "dss_run_summary": [
            ("prop_cost",        "NUMERIC"),
            ("savings_vs_prop",  "NUMERIC"),
            ("savings_pct_prop", "NUMERIC"),
        ],
    }
    with engine.connect() as conn:
        for table, cols in _migrations.items():
            try:
                rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                existing = {r[1] for r in rows}
                for col_name, col_type in cols:
                    if col_name not in existing:
                        conn.execute(text(
                            f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type} DEFAULT 0"
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
                param_description="High value constant for binary linearization",
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
