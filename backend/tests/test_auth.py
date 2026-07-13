"""Auth endpoint tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "user@test.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "Password123!",
    })
    assert resp.status_code == 201
    data = resp.json()
    # /register returns TokenResponse (access_token, refresh_token, token_type, expires_in)
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, admin_user):
    # admin_user fixture creates admin@lbro-test.com; re-registering the same
    # email must be rejected with 409 Conflict.
    resp = await client.post("/api/v1/auth/register", json={
        "email": "admin@lbro-test.com",
        "username": "otheradmin",
        "full_name": "Other Admin",
        "password": "Password123!",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient, admin_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@lbro-test.com",
        "password": "TestPass123!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, admin_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@lbro-test.com",
        "password": "WrongPassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@lbro-test.com"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
