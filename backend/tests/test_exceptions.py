import pytest
from httpx import AsyncClient
from app.core.exceptions import NotFoundError
from app.main import create_application


@pytest.mark.asyncio
async def test_custom_exception_handling():
    """Verify that DocuFinException subclasses return standardized JSON error envelopes."""
    app = create_application()

    @app.get("/test-not-found")
    async def trigger_not_found():
        raise NotFoundError("FinancialDocument", "doc-1234")

    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-not-found")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
        assert "FinancialDocument 'doc-1234' was not found" in data["error"]["message"]
        assert data["error"]["details"]["resource"] == "FinancialDocument"
