"""Project CRUD endpoint tests."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


# ── List ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_lists_all_projects(client: AsyncClient, auth_headers: dict):
    """Admin receives a list (may be empty) with items + total."""
    resp = await client.get("/api/v1/projects", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_unauthenticated_list_returns_401(client: AsyncClient):
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401


# ── Create ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_project_returns_201(client: AsyncClient, auth_headers: dict):
    """POST /projects creates a project and returns its details."""
    resp = await client.post("/api/v1/projects", json={
        "name": "My New Project",
        "description": "A brand-new test project",
        "environment": "staging",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My New Project"
    assert data["environment"] == "staging"
    assert data["status"] == "active"
    assert "id" in data
    assert "api_key" in data
    assert data["api_key"].startswith("proj_")


@pytest.mark.asyncio
async def test_create_project_production_environment(client: AsyncClient, auth_headers: dict):
    """Default environment is production if not specified."""
    resp = await client.post("/api/v1/projects", json={
        "name": "Production Project",
    }, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["environment"] == "production"


@pytest.mark.asyncio
async def test_create_project_invalid_environment_422(client: AsyncClient, auth_headers: dict):
    """Invalid environment value returns 422."""
    resp = await client.post("/api/v1/projects", json={
        "name": "Bad Env Project",
        "environment": "invalid_env",
    }, headers=auth_headers)
    assert resp.status_code == 422


# ── Get single ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_project_by_id(client: AsyncClient, auth_headers: dict):
    """GET /projects/{id} returns the project data."""
    create_resp = await client.post("/api/v1/projects", json={
        "name": "Fetch Me Project",
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project_id


@pytest.mark.asyncio
async def test_get_nonexistent_project_404(client: AsyncClient, auth_headers: dict):
    """Non-existent project id returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/projects/{fake_id}", headers=auth_headers)
    assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_project_name(client: AsyncClient, auth_headers: dict):
    """PATCH updates the project name."""
    create_resp = await client.post("/api/v1/projects", json={"name": "Old Name"}, headers=auth_headers)
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/v1/projects/{project_id}", json={
        "name": "Updated Name",
    }, headers=auth_headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_archive_project(client: AsyncClient, auth_headers: dict):
    """Setting status=archived changes project status."""
    create_resp = await client.post("/api/v1/projects", json={"name": "To Archive"}, headers=auth_headers)
    project_id = create_resp.json()["id"]

    patch_resp = await client.patch(f"/api/v1/projects/{project_id}", json={
        "status": "archived",
    }, headers=auth_headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "archived"


# ── Delete ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_can_delete_own_project(client: AsyncClient, auth_headers: dict):
    """Admin (owner) deleting their own project returns 204."""
    create_resp = await client.post("/api/v1/projects", json={"name": "Delete Me"}, headers=auth_headers)
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_viewer_cannot_delete_admins_project(
    client: AsyncClient, auth_headers: dict, viewer_headers: dict
):
    """Viewer is not the owner and not admin — delete returns 403."""
    create_resp = await client.post("/api/v1/projects", json={"name": "Admin Only Project"}, headers=auth_headers)
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/projects/{project_id}", headers=viewer_headers)
    assert delete_resp.status_code == 403


# ── API key regeneration ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_regenerate_project_api_key(client: AsyncClient, auth_headers: dict):
    """POST /projects/{id}/regenerate-key returns a new api_key."""
    create_resp = await client.post("/api/v1/projects", json={"name": "Key Regen Project"}, headers=auth_headers)
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]
    old_key = create_resp.json()["api_key"]

    regen_resp = await client.post(
        f"/api/v1/projects/{project_id}/regenerate-key",
        headers=auth_headers,
    )
    assert regen_resp.status_code == 200
    new_key = regen_resp.json()["api_key"]
    assert new_key != old_key
    assert new_key.startswith("proj_")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_project_dashboard(client: AsyncClient, auth_headers: dict):
    """GET /projects/{id}/dashboard returns aggregated stats."""
    create_resp = await client.post("/api/v1/projects", json={"name": "Dashboard Project"}, headers=auth_headers)
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    dash_resp = await client.get(f"/api/v1/projects/{project_id}/dashboard", headers=auth_headers)
    assert dash_resp.status_code == 200
    data = dash_resp.json()
    assert "security_score" in data
    assert "open_incidents" in data
    assert "evidence_count" in data
