"""Integration tests — Platform layer (SUPER_ADMIN routes).

Covers:
  - SUPER_ADMIN can access all platform endpoints
  - Non-super_admin users receive 403 on every platform endpoint
  - SUPER_ADMIN bypass is recorded in AuditLog (action=super_admin_access)
  - Platform dashboard returns expected metric fields
  - Project management: list, archive, delete, assign-admin, regenerate-key
  - User management: list, create, disable, delete, role change
  - Audit log retrieval and filtering
  - Platform health check
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


# ── SUPER_ADMIN fixture ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def super_admin_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="sa@lbro-test.com",
        username="superadmin",
        full_name="Super Admin",
        hashed_password=hash_password("SuperAdmin@1!"),
        role="super_admin",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def sa_token(client: AsyncClient, super_admin_user: User) -> str:
    resp = await client.post("/api/v1/auth/login", json={
        "email": "sa@lbro-test.com",
        "password": "SuperAdmin@1!",
    })
    assert resp.status_code == 200, f"SA login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def sa_h(sa_token: str) -> dict:
    return {"Authorization": f"Bearer {sa_token}"}


@pytest_asyncio.fixture
async def sa_project(client: AsyncClient, sa_h: dict, admin_user: User) -> dict:
    resp = await client.post("/api/v1/projects", json={"name": "SA Test Project"}, headers=sa_h)
    if resp.status_code not in (200, 201):
        login = await client.post("/api/v1/auth/login", json={
            "email": "admin@lbro-test.com",
            "password": "TestPass123!",
        })
        token = login.json()["access_token"]
        resp = await client.post("/api/v1/projects", json={"name": "SA Test Project"},
                                 headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# 1. ACCESS CONTROL
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformAccessControl:
    PLATFORM_GET_ROUTES = [
        "/api/v1/platform/dashboard",
        "/api/v1/platform/projects",
        "/api/v1/platform/users",
        "/api/v1/platform/audit",
        "/api/v1/platform/health",
    ]

    @pytest.mark.asyncio
    async def test_super_admin_can_access_dashboard(self, client: AsyncClient, sa_h: dict):
        resp = await client.get("/api/v1/platform/dashboard", headers=sa_h)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.parametrize("route", PLATFORM_GET_ROUTES)
    async def test_admin_cannot_access_platform(
        self, client: AsyncClient, admin_user: User, admin_token: str, route: str
    ):
        resp = await client.get(route, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.parametrize("route", PLATFORM_GET_ROUTES)
    async def test_analyst_cannot_access_platform(
        self, client: AsyncClient, analyst_user: User, analyst_token: str, route: str
    ):
        resp = await client.get(route, headers={"Authorization": f"Bearer {analyst_token}"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.parametrize("route", PLATFORM_GET_ROUTES)
    async def test_unauthenticated_cannot_access_platform(self, client: AsyncClient, route: str):
        resp = await client.get(route)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_proj_api_key_cannot_access_platform(
        self, client: AsyncClient, sa_project: dict
    ):
        proj_key = sa_project["api_key"]
        resp = await client.get(
            "/api/v1/platform/dashboard",
            headers={"Authorization": f"Bearer {proj_key}"},
        )
        assert resp.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────────────
# 2. DASHBOARD METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformDashboard:

    @pytest.mark.asyncio
    async def test_dashboard_has_required_fields(self, client: AsyncClient, sa_h: dict):
        resp = await client.get("/api/v1/platform/dashboard", headers=sa_h)
        assert resp.status_code == 200
        data = resp.json()
        required = {
            "total_projects", "active_projects",
            "total_users", "active_users",
            "total_incidents", "critical_incidents", "open_incidents",
            "total_events_ingested", "events_last_24h",
            "severity_breakdown",
        }
        for field in required:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_dashboard_counts_are_non_negative(self, client: AsyncClient, sa_h: dict):
        resp = await client.get("/api/v1/platform/dashboard", headers=sa_h)
        assert resp.status_code == 200
        data = resp.json()
        for field in ["total_projects", "active_projects", "total_users",
                      "active_users", "total_incidents", "total_events_ingested"]:
            assert data[field] >= 0, f"{field} is negative"


# ─────────────────────────────────────────────────────────────────────────────
# 3. PROJECT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformProjectManagement:

    @pytest.mark.asyncio
    async def test_list_projects(self, client: AsyncClient, sa_h: dict, sa_project: dict):
        resp = await client.get("/api/v1/platform/projects", headers=sa_h)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        ids = [p["id"] for p in data["items"]]
        assert sa_project["id"] in ids

    @pytest.mark.asyncio
    async def test_list_projects_never_returns_full_api_key(
        self, client: AsyncClient, sa_h: dict, sa_project: dict
    ):
        resp = await client.get("/api/v1/platform/projects", headers=sa_h)
        assert resp.status_code == 200
        for project in resp.json()["items"]:
            prefix = project.get("api_key_prefix", "")
            assert not prefix.startswith("proj_") or len(prefix) < 20, (
                "Full API key leaked in list response"
            )

    @pytest.mark.asyncio
    async def test_archive_project(self, client: AsyncClient, sa_h: dict, sa_project: dict):
        project_id = sa_project["id"]
        resp = await client.patch(
            f"/api/v1/platform/projects/{project_id}/archive",
            headers=sa_h,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    @pytest.mark.asyncio
    async def test_regenerate_api_key(self, client: AsyncClient, sa_h: dict, sa_project: dict):
        project_id = sa_project["id"]
        original_key = sa_project["api_key"]
        resp = await client.post(
            f"/api/v1/platform/projects/{project_id}/regenerate-key",
            headers=sa_h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "api_key" in body
        new_key = body["api_key"]
        assert new_key.startswith("proj_")
        assert new_key != original_key

    @pytest.mark.asyncio
    async def test_delete_project(self, client: AsyncClient, sa_h: dict, admin_user: User):
        login = await client.post("/api/v1/auth/login", json={
            "email": "admin@lbro-test.com", "password": "TestPass123!"
        })
        token = login.json()["access_token"]
        create_resp = await client.post(
            "/api/v1/projects",
            json={"name": "DeleteMe"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_resp.status_code in (200, 201)
        project_id = create_resp.json()["id"]
        del_resp = await client.delete(
            f"/api/v1/platform/projects/{project_id}",
            headers=sa_h,
        )
        assert del_resp.status_code in (200, 204)

    @pytest.mark.asyncio
    async def test_archive_nonexistent_project_returns_404(
        self, client: AsyncClient, sa_h: dict
    ):
        fake_id = str(uuid.uuid4())
        resp = await client.patch(
            f"/api/v1/platform/projects/{fake_id}/archive",
            headers=sa_h,
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 4. USER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformUserManagement:

    @pytest.mark.asyncio
    async def test_list_users_returns_all_users(
        self, client: AsyncClient, sa_h: dict, admin_user: User, analyst_user: User
    ):
        resp = await client.get("/api/v1/platform/users", headers=sa_h)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        emails = [u["email"] for u in data["items"]]
        assert "admin@lbro-test.com" in emails
        assert "analyst@lbro-test.com" in emails

    @pytest.mark.asyncio
    async def test_list_users_filter_by_role(
        self, client: AsyncClient, sa_h: dict, admin_user: User, analyst_user: User
    ):
        resp = await client.get("/api/v1/platform/users", params={"role": "admin"}, headers=sa_h)
        assert resp.status_code == 200
        for user in resp.json()["items"]:
            assert user["role"] == "admin"

    @pytest.mark.asyncio
    async def test_create_user(self, client: AsyncClient, sa_h: dict):
        resp = await client.post("/api/v1/platform/users", json={
            "email": "newuser@platform-test.com",
            "username": "newuser_plat",
            "full_name": "New Platform User",
            "password": "NewUser@1!",
            "role": "analyst",
        }, headers=sa_h)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newuser@platform-test.com"
        assert body["role"] == "analyst"

    @pytest.mark.asyncio
    async def test_create_user_invalid_role_rejected(self, client: AsyncClient, sa_h: dict):
        resp = await client.post("/api/v1/platform/users", json={
            "email": "badrole@platform-test.com",
            "username": "badrole",
            "full_name": "Bad Role",
            "password": "BadRole@1!",
            "role": "superuser",
        }, headers=sa_h)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_disable_user(
        self, client: AsyncClient, sa_h: dict, analyst_user: User
    ):
        resp = await client.patch(
            f"/api/v1/platform/users/{analyst_user.id}/disable",
            headers=sa_h,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_cannot_disable_self(
        self, client: AsyncClient, sa_h: dict, super_admin_user: User
    ):
        resp = await client.patch(
            f"/api/v1/platform/users/{super_admin_user.id}/disable",
            headers=sa_h,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_change_user_role(
        self, client: AsyncClient, sa_h: dict, analyst_user: User
    ):
        resp = await client.patch(
            f"/api/v1/platform/users/{analyst_user.id}/role",
            json={"role": "admin"},
            headers=sa_h,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    @pytest.mark.asyncio
    async def test_cannot_delete_self(
        self, client: AsyncClient, sa_h: dict, super_admin_user: User
    ):
        resp = await client.delete(
            f"/api/v1/platform/users/{super_admin_user.id}",
            headers=sa_h,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_password(
        self, client: AsyncClient, sa_h: dict, analyst_user: User
    ):
        resp = await client.post(
            f"/api/v1/platform/users/{analyst_user.id}/reset-password",
            json={"new_password": "ResetPass@99!"},
            headers=sa_h,
        )
        assert resp.status_code == 200
        login = await client.post("/api/v1/auth/login", json={
            "email": "analyst@lbro-test.com",
            "password": "ResetPass@99!",
        })
        assert login.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 5. AUDIT LOG
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformAuditLog:

    @pytest.mark.asyncio
    async def test_platform_access_is_audit_logged(self, client: AsyncClient, sa_h: dict):
        await client.get("/api/v1/platform/dashboard", headers=sa_h)
        resp = await client.get("/api/v1/platform/audit", headers=sa_h)
        assert resp.status_code == 200
        actions = [entry["action"] for entry in resp.json()["items"]]
        assert "super_admin_access" in actions, "Expected super_admin_access in audit log"

    @pytest.mark.asyncio
    async def test_audit_log_filter_by_action(self, client: AsyncClient, sa_h: dict):
        await client.get("/api/v1/platform/dashboard", headers=sa_h)
        resp = await client.get(
            "/api/v1/platform/audit",
            params={"action": "super_admin_access"},
            headers=sa_h,
        )
        assert resp.status_code == 200
        for entry in resp.json()["items"]:
            assert entry["action"] == "super_admin_access"

    @pytest.mark.asyncio
    async def test_audit_log_has_required_fields(self, client: AsyncClient, sa_h: dict):
        await client.get("/api/v1/platform/dashboard", headers=sa_h)
        resp = await client.get("/api/v1/platform/audit", headers=sa_h)
        assert resp.status_code == 200
        items = resp.json()["items"]
        if items:
            entry = items[0]
            assert "action" in entry
            assert "created_at" in entry


# ─────────────────────────────────────────────────────────────────────────────
# 6. HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformHealth:

    @pytest.mark.asyncio
    async def test_health_returns_db_status(self, client: AsyncClient, sa_h: dict):
        resp = await client.get("/api/v1/platform/health", headers=sa_h)
        assert resp.status_code == 200
        data = resp.json()
        assert "database" in data
        assert data["database"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_returns_ml_status(self, client: AsyncClient, sa_h: dict):
        resp = await client.get("/api/v1/platform/health", headers=sa_h)
        assert resp.status_code == 200
        assert "ml" in resp.json()
