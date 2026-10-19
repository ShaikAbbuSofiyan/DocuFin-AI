from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test root endpoint returns API metadata and health links."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DocuFin AI"
    assert data["status"] == "operational"
    assert "health" in data


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient):
    """Test /health/live probe returns 200 OK and valid health payload."""
    response = await client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "DocuFin AI"
    assert "timestamp" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_readiness_probe_all_healthy(client: AsyncClient):
    """Test /health/ready probe when both Database and Redis dependencies are available."""
    # Mock Redis connection to succeed
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    mock_redis.aclose.return_value = None

    with patch("redis.asyncio.from_url", return_value=mock_redis):
        response = await client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "database" in data["components"]
        assert "redis" in data["components"]
        assert data["components"]["database"]["status"] == "connected"
        assert data["components"]["redis"]["status"] == "connected"
        assert data["components"]["database"]["latency_ms"] is not None
        assert data["components"]["redis"]["latency_ms"] is not None


@pytest.mark.asyncio
async def test_readiness_probe_redis_down(client: AsyncClient):
    """Test /health/ready probe returns 503 when Redis is unavailable."""
    with patch("redis.asyncio.from_url", side_effect=ConnectionError("Redis connection refused")):
        response = await client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["components"]["redis"]["status"] == "error"
        assert "Redis connection refused" in data["components"]["redis"]["details"]
        # Database should still report connected in our test fixture
        assert data["components"]["database"]["status"] == "connected"


@pytest.mark.asyncio
async def test_api_v1_versioned_health_routes(client: AsyncClient):
    """Test versioned routes /api/v1/health/live are also accessible."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
