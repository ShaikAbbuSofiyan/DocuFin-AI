import json
from functools import lru_cache
from typing import Any, List, Optional, Union
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

    # Security, JWT & Cookies
    secret_key: str = "development-secret-key-change-in-production-32bytes"
    jwt_secret_key: str = "development-jwt-secret-key-change-in-production-32bytes"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    auth_cookie_name: str = "docufin_access_token"
    csrf_cookie_name: str = "docufin_csrf_token"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_cookie_domain: Optional[str] = None

    # Rate Limiting Controls
    rate_limit_login_attempts: int = 5
    rate_limit_lockout_seconds: int = 300

    cors_origins: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ]
    allowed_hosts: Union[str, List[str]] = ["*"]

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

    # Celery & Asynchronous Task Processing (Phase 4)
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    max_document_pages: int = 100
    processing_timeout_seconds: int = 300
    ocr_min_words_threshold: int = 20

    # Financial Document Intelligence & Structured Extraction (Phase 5)
    llm_provider: str = "mock"  # "mock", "openai", "gemini"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: Optional[str] = None
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    llm_temperature: float = 0.0
    extraction_confidence_threshold: float = 0.75

    # Storage Settings
    upload_dir: str = "./storage/documents"
    storage_dir: str = "./storage/documents"
    max_upload_size_mb: int = 50
    allowed_upload_extensions: List[str] = [".pdf", ".png", ".jpg", ".jpeg"]
    allowed_upload_mime_types: List[str] = ["application/pdf", "image/png", "image/jpeg"]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
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

    @property
    def celery_broker_connection_url(self) -> str:
        """Returns Celery message broker URL."""
        if self.celery_broker_url:
            return self.celery_broker_url
        base = self.redis_connection_url.rsplit("/", 1)[0]
        return f"{base}/1"

    @property
    def celery_result_connection_url(self) -> str:
        """Returns Celery result backend URL."""
        if self.celery_result_backend:
            return self.celery_result_backend
        base = self.redis_connection_url.rsplit("/", 1)[0]
        return f"{base}/2"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton provider."""
    return Settings()
