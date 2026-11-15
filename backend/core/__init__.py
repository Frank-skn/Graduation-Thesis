"""
Core package initialization
"""
from backend.core.config import get_settings
from backend.core.database import get_db_nds, get_db_dds

__all__ = ["get_settings", "get_db_nds", "get_db_dds"]
