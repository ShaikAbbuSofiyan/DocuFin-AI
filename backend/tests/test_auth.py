from datetime import timedelta
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token, reset_login_attempts


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    payload = {
        "email": "analyst.one@docufin.ai",
        "password": "StrongPassword123!",
        "full_name": "Jordan Bell",
        "organization_name": "Bell Financial Partners",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "analyst.one@docufin.ai"
    assert data["user"]["full_name"] == "Jordan Bell"

    # Verify HttpOnly cookie and CSRF cookie are set
    cookies = response.cookies
    assert "docufin_access_token" in cookies
    assert "docufin_csrf_token" in cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {
        "email": "duplicate@docufin.ai",
        "password": "StrongPassword123!",
        "full_name": "Original User",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second attempt with same email
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    err = res2.json()
    assert err["error"]["code"] == "RESOURCE_CONFLICT"


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient):
    payload = {
        "email": "short.pwd@docufin.ai",
        "password": "short",
        "full_name": "Test User",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    reg_payload = {
        "email": "login.test@docufin.ai",
        "password": "Password123!",
        "full_name": "Login Tester",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "login.test@docufin.ai",
        "password": "Password123!",
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "login.test@docufin.ai"
    assert "docufin_access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    reg_payload = {
        "email": "bad.password@docufin.ai",
        "password": "CorrectPassword123!",
        "full_name": "Tester",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "bad.password@docufin.ai", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "does.not.exist@docufin.ai", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    # Security requirement: generic message, identical error code to prevent user enumeration
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_rate_limiting(client: AsyncClient):
    email = "ratelimit.target@docufin.ai"
    # Ensure fresh state
    reset_login_attempts(f"testclient:{email}")

    # Exhaust allowed attempts (configured to 5)
    for _ in range(5):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        assert res.status_code in [401, 429]

    # Next attempt must trigger 429 Too Many Requests
    blocked_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword!"},
    )
    assert blocked_res.status_code == 429
    assert blocked_res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_get_current_user_me(client: AsyncClient):
    reg_payload = {
        "email": "me.endpoint@docufin.ai",
        "password": "Password123!",
        "full_name": "Profile Owner",
        "organization_name": "Owner Capital Corp",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    token = reg_res.json()["access_token"]

    # Request /auth/me with Bearer token
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["user"]["email"] == "me.endpoint@docufin.ai"
    assert len(data["memberships"]) == 1
    assert data["memberships"][0]["role"] == "Admin"
    assert data["active_role"] == "Admin"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_expired_token(client: AsyncClient):
    # Create expired token
    expired_token = create_access_token(
        subject="some-user-id",
        expires_delta=timedelta(seconds=-10),
    )
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["success"] is True
