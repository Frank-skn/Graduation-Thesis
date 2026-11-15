"""
Application configuration using Pydantic Settings
Implements Dependency Inversion Principle - configurations are injected
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional
from urllib.parse import quote_plus


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars (e.g. VITE_* frontend vars)
    )

    # Database Configuration (kept for backwards compat; not used for PostgreSQL)
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "YourStrong@Passw0rd"
    db_name: str = "SMI_DSS"
    db_schema_nds: str = "nds"
    db_schema_dds: str = "dds"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    api_title: str = "SS-MB-SMI Decision Support System"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # Optimization Configuration
    default_solver: str = "cbc"
    solver_time_limit: int = 300
    mip_gap: float = 0.01

    # Data source configuration
    # Path to CSV data directory (relative to project root or absolute)
    data_dir: str = "data"
    # Path to SQLite database file for NDS (scenarios, results)
    sqlite_db_path: str = "data/nds.db"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Environment
    environment: str = "development"

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection string (kept for reference)."""
        encoded_password = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg2://{self.db_user}:{encoded_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings instance
    Implements Singleton pattern for configuration
    """
    return Settings()
