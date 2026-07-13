"""Extended auth endpoint tests: logout, refresh, API key rotate, lockout."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Logout ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_returns_204(client: AsyncClient, auth_headers: dict):
    """POST /auth/logout with a valid token returns 204."""
    resp = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_logout_revokes_token(client: AsyncClient, admin_token: str):
    """After logout the same token must be rejected with 401."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    logout_resp = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 204

    # Token should now be rejected
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_requires_auth(client: AsyncClient):
    """POST /auth/logout without a token returns 401."""
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


# ── Token refresh ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(client: AsyncClient, admin_user):
    """POST /auth/refresh with a valid refresh token returns a new access_token."""
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@lbro-test.com",
        "password": "TestPass123!",
    })
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    refresh_token = tokens["refresh_token"]

    refresh_resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    # New token must be usable
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_data['access_token']}"},
    )
    assert me_resp.status_code == 200


@pytest.mark.asyncio
async def test_refresh_with_invalid_token_returns_401(client: AsyncClient):
    """Garbage refresh token must be rejected."""
    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": "not.a.real.jwt.token",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_returns_401(client: AsyncClient, admin_user, admin_token: str):
    """An access token cannot be used as a refresh token (wrong type claim)."""
    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": admin_token,  # access token, not refresh token
    })
    assert resp.status_code == 401


# ── API key rotation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rotate_api_key_returns_new_key(client: AsyncClient, auth_headers: dict):
    """POST /auth/api-key/rotate returns an api_key with the lbro_ prefix."""
    resp = await client.post("/api/v1/auth/api-key/rotate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" in data
    assert data["api_key"].startswith("lbro_")


@pytest.mark.asyncio
async def test_rotated_api_key_is_immediately_usable(client: AsyncClient, auth_headers: dict):
    """The new api_key can authenticate requests right away."""
    rotate_resp = await client.post("/api/v1/auth/api-key/rotate", headers=auth_headers)
    assert rotate_resp.status_code == 200
    new_key = rotate_resp.json()["api_key"]

    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": new_key},
    )
    assert me_resp.status_code == 200


@pytest.mark.asyncio
async def test_old_api_key_invalidated_after_rotation(client: AsyncClient, auth_headers: dict):
    """Rotating twice: the key from the first rotation must be rejected after the second."""
    # First rotation — get key1
    first_resp = await client.post("/api/v1/auth/api-key/rotate", headers=auth_headers)
    assert first_resp.status_code == 200
    key1 = first_resp.json()["api_key"]

    # Second rotation using key1 — key1 is now invalid, use the JWT headers instead
    second_resp = await client.post("/api/v1/auth/api-key/rotate", headers=auth_headers)
    assert second_resp.status_code == 200

    # key1 should be rejected
    old_key_resp = await client.get(
        "/api/v1/auth/me",
        headers={"X-API-Key": key1},
    )
    assert old_key_resp.status_code == 401


@pytest.mark.asyncio
async def test_rotate_api_key_requires_auth(client: AsyncClient):
    """Unauthenticated rotation returns 401."""
    resp = await client.post("/api/v1/auth/api-key/rotate")
    assert resp.status_code == 401


# ── Invalid tokens ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_jwt_returns_401(client: AsyncClient):
    """A malformed JWT is rejected with 401."""
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this.is.not.a.jwt"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_auth_header_returns_401(client: AsyncClient):
    """No auth credentials at all → 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# ── Password complexity ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_weak_password_no_uppercase_422(client: AsyncClient):
    """Password without uppercase letter is rejected at schema validation (422)."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "weakpass@example.com",
        "full_name": "Weak Pass User",
        "password": "alllowercase1",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_weak_password_no_digit_422(client: AsyncClient):
    """Password without a digit is rejected (422)."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "nodigit@example.com",
        "full_name": "No Digit User",
        "password": "NoDigitPassword",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_too_short_password_422(client: AsyncClient):
    """Password under 8 characters is rejected (422)."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "short@example.com",
        "full_name": "Short Pass User",
        "password": "Ab1!",
    })
    assert resp.status_code == 422


# ── Account lockout ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_account_lockout_after_five_failures(client: AsyncClient, db: AsyncSession):
    """After MAX_LOGIN_ATTEMPTS (5) consecutive failures the account is locked (403)."""
    import uuid as _uuid
    from app.models.user import User
    from app.core.security import hash_password

    # Create a dedicated user so we don't pollute the shared admin fixture
    victim = User(
        id=_uuid.uuid4(),
        email="lockout-victim@lbro-test.com",
        username="lockoutvictim",
        full_name="Lockout Victim",
        hashed_password=hash_password("CorrectPass123!"),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db.add(victim)
    await db.flush()

    # 5 failed attempts (each returns 401, counter increments)
    for _ in range(5):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "lockout-victim@lbro-test.com",
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    # 6th attempt — account is now locked
    locked_resp = await client.post("/api/v1/auth/login", json={
        "email": "lockout-victim@lbro-test.com",
        "password": "WrongPassword!",
    })
    assert locked_resp.status_code == 403


# ── Profile update ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_profile_full_name(client: AsyncClient, auth_headers: dict):
    """PATCH /auth/profile can update the user's full_name."""
    resp = await client.patch("/api/v1/auth/profile", json={
        "full_name": "Patched Admin Name",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Patched Admin Name"


@pytest.mark.asyncio
async def test_update_profile_password(client: AsyncClient, admin_user, auth_headers: dict):
    """PATCH /auth/profile can change the password given the correct current_password."""
    resp = await client.patch("/api/v1/auth/profile", json={
        "current_password": "TestPass123!",
        "new_password": "NewAdminPass456!",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # Verify new password works for login
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@lbro-test.com",
        "password": "NewAdminPass456!",
    })
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_update_profile_wrong_current_password_400(client: AsyncClient, auth_headers: dict):
    """Providing the wrong current_password when changing password returns 400."""
    resp = await client.patch("/api/v1/auth/profile", json={
        "current_password": "WrongCurrentPass!",
        "new_password": "NewPass123!",
    }, headers=auth_headers)
    assert resp.status_code == 400
