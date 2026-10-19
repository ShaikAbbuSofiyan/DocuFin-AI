import json
from functools import lru_cache
from typing import Any, List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DocuFin AI Application Settings configured via environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Application Settings
    app_name: str = "DocuFin AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Security & CORS
    secret_key: str = "development-secret-key-change-in-production-32bytes"
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]
    allowed_hosts: List[str] = ["*"]

    # Database Configuration (PostgreSQL)
    postgres_user: str = "docufin_user"
    postgres_password: str = "docufin_password_placeholder"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "docufin_db"
    database_url: str | None = None
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0
    redis_url: str | None = None

    # Storage Settings
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        elif isinstance(v, list):
            return v
        return []

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        elif isinstance(v, list):
            return v
        return ["*"]

    @property
    def async_database_url(self) -> str:
        """Returns the async SQLAlchemy database connection string."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Returns the sync SQLAlchemy database connection string (used by Alembic migrations)."""
        if self.database_url:
            # Replace asyncpg driver with standard psycopg2 if present
            return self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_connection_url(self) -> str:
        """Returns the Redis connection URL."""
        if self.redis_url:
            return self.redis_url
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton provider."""
    return Settings()
