"""Application settings, sourced from the environment with sane local defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Delivery Status Tracker"
    api_prefix: str = "/api/v1"
    environment: str = Field(default="local")
    debug: bool = False

    database_url: str = Field(
        default="postgresql+asyncpg://tracker:tracker@localhost:5432/tracker",
        description="SQLAlchemy async DSN.",
    )
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    lifecycle_config_path: Path = BACKEND_ROOT / "config" / "shipment_lifecycle.yaml"
    seed_csv_path: Path = BACKEND_ROOT / "data" / "shipments.csv"

    default_page_size: int = 20
    max_page_size: int = 100

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
        ]
    )

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        # A sync DSN silently deadlocks the async engine; fail loudly instead.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def sync_database_url(self) -> str:
        """Psycopg DSN for Alembic, which runs its migrations synchronously."""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
