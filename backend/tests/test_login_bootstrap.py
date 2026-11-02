"""Login response bootstrap payload — avoids an extra /auth/me round trip after sign-in."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_includes_user_bootstrap(client: AsyncClient, admin_user):  # noqa: ARG001
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@lbro-test.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    user = data.get("user")
    assert user is not None
    assert user["email"] == "admin@lbro-test.com"
    assert user["role"] == "admin"
    assert isinstance(user.get("permissions"), list)
    assert len(user["permissions"]) > 0
    assert user["id"]
    assert "hashed_password" not in data
    assert "hashed_password" not in user
