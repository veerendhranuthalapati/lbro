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
    assert data["email"] == "user@test.com"
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, admin_user):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "admin@lbro.test",
        "username": "otheradmin",
        "full_name": "Other Admin",
        "password": "Password123!",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient, admin_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": "admin@lbro.test",
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
        "email": "admin@lbro.test",
        "password": "WrongPassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@lbro.test"
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
