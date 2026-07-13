"""User management endpoint tests."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


# ── List users ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_list_users(client: AsyncClient, auth_headers: dict):
    """Admin can GET /users — returns paginated list with at least the admin user."""
    resp = await client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_viewer_cannot_list_users(client: AsyncClient, viewer_headers: dict):
    """Viewer lacks MANAGE_USERS — must get 403."""
    resp = await client.get("/api/v1/users", headers=viewer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analyst_cannot_list_users(client: AsyncClient, analyst_headers: dict):
    """Analyst lacks MANAGE_USERS — must get 403."""
    resp = await client.get("/api/v1/users", headers=analyst_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_list_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 401


# ── Create user ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_create_user_returns_201(client: AsyncClient, auth_headers: dict):
    """Admin can create a new user with specified role."""
    resp = await client.post("/api/v1/users", json={
        "email": "newuser@example.com",
        "username": "newuser001",
        "full_name": "New User",
        "password": "NewPass123!",
        "role": "viewer",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "viewer"
    assert data["is_active"] is True
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_create_user_analyst_role(client: AsyncClient, auth_headers: dict):
    """Admin can create user with analyst role."""
    resp = await client.post("/api/v1/users", json={
        "email": "analyst2@example.com",
        "username": "analyst002",
        "full_name": "New Analyst",
        "password": "AnalystPass123!",
        "role": "analyst",
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["role"] == "analyst"


@pytest.mark.asyncio
async def test_duplicate_email_returns_409(client: AsyncClient, auth_headers: dict, admin_user):
    """Creating a user with an already-registered email returns 409."""
    resp = await client.post("/api/v1/users", json={
        "email": "admin@lbro-test.com",  # admin_user's email
        "username": "dup_admin",
        "full_name": "Duplicate Admin",
        "password": "DupPass123!",
        "role": "viewer",
    }, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_duplicate_username_returns_409(client: AsyncClient, auth_headers: dict, admin_user):
    """Creating a user with a taken username returns 409."""
    resp = await client.post("/api/v1/users", json={
        "email": "fresh@example.com",
        "username": "admin",  # admin_user's username
        "full_name": "Fresh User",
        "password": "FreshPass123!",
        "role": "viewer",
    }, headers=auth_headers)
    assert resp.status_code == 409


# ── Get single user ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_get_user_by_id(client: AsyncClient, auth_headers: dict, admin_user):
    """Admin can fetch a user by id."""
    resp = await client.get(f"/api/v1/users/{admin_user.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@lbro-test.com"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_nonexistent_user_returns_404(client: AsyncClient, auth_headers: dict):
    """Non-existent user id returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/users/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


# ── Update user ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_update_user_full_name(client: AsyncClient, auth_headers: dict, admin_user):
    """PATCH updates full_name."""
    resp = await client.patch(f"/api/v1/users/{admin_user.id}", json={
        "full_name": "Renamed Admin",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Renamed Admin"


@pytest.mark.asyncio
async def test_admin_change_user_role(client: AsyncClient, auth_headers: dict, analyst_user):
    """Admin can promote analyst to admin role."""
    resp = await client.patch(f"/api/v1/users/{analyst_user.id}", json={
        "role": "admin",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_deactivate_user(client: AsyncClient, auth_headers: dict, analyst_user):
    """Admin can set is_active=False."""
    resp = await client.patch(f"/api/v1/users/{analyst_user.id}", json={
        "is_active": False,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


# ── Delete user ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_delete_other_user(client: AsyncClient, auth_headers: dict, analyst_user):
    """Admin can delete another user — returns 204."""
    resp = await client.delete(f"/api/v1/users/{analyst_user.id}", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(client: AsyncClient, auth_headers: dict, admin_user):
    """Admin cannot delete their own account — returns 400."""
    resp = await client.delete(f"/api/v1/users/{admin_user.id}", headers=auth_headers)
    assert resp.status_code == 400
