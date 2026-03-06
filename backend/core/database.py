"""
Database connection and session management.

NDS  → SQLite (file-based, no PostgreSQL required)
DDS  → CSV files (see CsvOptimizationDataRepository)
"""
from __future__ import annotations

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from backend.core.config import get_settings

settings = get_settings()

# ── Resolve SQLite path relative to project root ─────────────────────
_project_root = Path(__file__).resolve().parent.parent.parent
_sqlite_path = _project_root / settings.sqlite_db_path
_sqlite_path.parent.mkdir(parents=True, exist_ok=True)

# ── SQLite engine for NDS ─────────────────────────────────────────────
engine = create_engine(
    f"sqlite:///{_sqlite_path}",
    connect_args={"check_same_thread": False},
    echo=(settings.environment == "development"),
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement in SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocalNDS = SessionLocal  # explicit alias used by background tasks

# NDS base – no schema prefix (SQLite does not support schemas)
BaseNDS = declarative_base()

# DDS base – kept for import compatibility, not bound to any DB engine
BaseDDS = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Provide a SQLite/NDS session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_nds() -> Generator[Session, None, None]:
    """NDS session (SQLite)."""
    yield from get_db()


def get_db_dds() -> Generator[Session, None, None]:
    """Legacy alias – yields an NDS/SQLite session.
    DDS input data is now served by CsvOptimizationDataRepository.
    """
    yield from get_db()


# ── CSV repository dependency ─────────────────────────────────────────
from backend.data_access.csv_repository import get_csv_repo, CsvOptimizationDataRepository  # noqa: E402

_data_dir = str(_project_root / settings.data_dir)


def get_csv_data() -> CsvOptimizationDataRepository:
    """FastAPI dependency: returns the shared CSV data repository."""
    return get_csv_repo(_data_dir)
