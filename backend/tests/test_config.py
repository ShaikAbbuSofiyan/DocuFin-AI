from app.core.config import Settings


def test_settings_defaults():
    """Verify default application settings are properly initialized."""
    settings = Settings()
    assert settings.app_name == "DocuFin AI"
    assert settings.app_version == "0.1.0"
    assert settings.port == 8000
    assert "postgresql" in settings.async_database_url
    assert "redis://" in settings.redis_connection_url


def test_settings_cors_origins_parsing():
    """Verify comma-separated and JSON string CORS origins are properly parsed."""
    settings = Settings(cors_origins="http://example.com,http://test.com")
    assert "http://example.com" in settings.cors_origins
    assert "http://test.com" in settings.cors_origins

    settings_json = Settings(cors_origins='["http://sub.domain.com"]')
    assert settings_json.cors_origins == ["http://sub.domain.com"]


def test_database_sync_url_conversion():
    """Verify sync database URL replaces asyncpg with psycopg2 for Alembic."""
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/testdb"
    )
    assert settings.sync_database_url == "postgresql://user:pass@localhost:5432/testdb"
