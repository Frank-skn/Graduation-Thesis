"""
Database connection and session management
Single database with nds/dds schemas
"""
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator
from backend.core.config import get_settings

settings = get_settings()

# Single engine for the unified database
engine = create_engine(
    settings.database_url,
    echo=settings.environment == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base classes with schema metadata
BaseNDS = declarative_base(metadata=MetaData(schema="nds"))
BaseDDS = declarative_base(metadata=MetaData(schema="dds"))


def get_db() -> Generator[Session, None, None]:
    """Provides database session - single session for both schemas"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Backwards compatibility aliases
def get_db_nds() -> Generator[Session, None, None]:
    yield from get_db()

def get_db_dds() -> Generator[Session, None, None]:
    yield from get_db()
