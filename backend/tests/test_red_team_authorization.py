"""Red-team authorization regression suite.

Assumes every control is broken until proven otherwise.
Tests horizontal (cross-project) and vertical (privilege) escalation via direct API.
"""
from __future__ import annotations

import io
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.incident import Incident
from app.models.project import Project
from app.models.user import User


# ── Actors ────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def super_admin_user(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="sa@redteam.test",
        username="super_admin_rt",
        full_name="Super Admin",
        hashed_password=hash_password("SuperAdmin1!"),
        role="super_admin",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def owner_a(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="owner_a@redteam.test",
        username="owner_a",
        full_name="Project Admin A",
        hashed_password=hash_password("OwnerA1!"),
        role="analyst",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def viewer_a(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="viewer_a@redteam.test",
        username="viewer_a",
        full_name="Viewer A",
        hashed_password=hash_password("ViewerA1!"),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def owner_b(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="owner_b@redteam.test",
        username="owner_b",
        full_name="Project Admin B",
        hashed_password=hash_password("OwnerB1!"),
        role="analyst",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def viewer_b(db: AsyncSession) -> User:
    u = User(
        id=uuid.uuid4(),
        email="viewer_b@redteam.test",
        username="viewer_b",
        full_name="Viewer B",
        hashed_password=hash_password("ViewerB1!"),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


async def _login(client: AsyncClient, email: str, password: str) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest_asyncio.fixture
async def owner_a_h(client: AsyncClient, owner_a: User) -> dict:
    return await _login(client, "owner_a@redteam.test", "OwnerA1!")


@pytest_asyncio.fixture
async def viewer_a_h(client: AsyncClient, viewer_a: User) -> dict:
    return await _login(client, "viewer_a@redteam.test", "ViewerA1!")


@pytest_asyncio.fixture
async def owner_b_h(client: AsyncClient, owner_b: User) -> dict:
    return await _login(client, "owner_b@redteam.test", "OwnerB1!")


@pytest_asyncio.fixture
async def viewer_b_h(client: AsyncClient, viewer_b: User) -> dict:
    return await _login(client, "viewer_b@redteam.test", "ViewerB1!")


@pytest_asyncio.fixture
async def super_admin_h(client: AsyncClient, super_admin_user: User) -> dict:
    return await _login(client, "sa@redteam.test", "SuperAdmin1!")


@pytest_asyncio.fixture
async def project_a(client: AsyncClient, owner_a_h: dict) -> dict:
    r = await client.post(
        "/api/v1/projects",
        json={"name": "Project A", "environment": "development"},
        headers=owner_a_h,
    )
    assert r.status_code == 201
    return r.json()


@pytest_asyncio.fixture
async def project_b(client: AsyncClient, owner_b_h: dict) -> dict:
    r = await client.post(
        "/api/v1/projects",
        json={"name": "Project B", "environment": "development"},
        headers=owner_b_h,
    )
    assert r.status_code == 201
    return r.json()


@pytest_asyncio.fixture
async def incident_a(client: AsyncClient, owner_a_h: dict, project_a: dict) -> dict:
    r = await client.post(
        "/api/v1/incidents",
        json={"title": "Incident A", "severity": "high", "project_id": project_a["id"]},
        headers=owner_a_h,
    )
    assert r.status_code == 201
    return r.json()


@pytest_asyncio.fixture
async def evidence_a(
    client: AsyncClient, owner_a_h: dict, incident_a: dict, project_a: dict
) -> dict:
    r = await client.post(
        f"/api/v1/incidents/{incident_a['id']}/evidence",
        files={"file": ("secret-a.txt", io.BytesIO(b"project-a-secret"), "text/plain")},
        headers=owner_a_h,
    )
    assert r.status_code == 201
    body = r.json()
    body["_project_id"] = project_a["id"]
    return body


# ── Horizontal escalation (cross-project) ───────────────────────────────────

@pytest.mark.asyncio
async def test_cross_project_get_project_denied(
    client: AsyncClient, owner_b_h: dict, project_a: dict
):
    r = await client.get(f"/api/v1/projects/{project_a['id']}", headers=owner_b_h)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cross_project_dashboard_denied(
    client: AsyncClient, owner_b_h: dict, project_a: dict
):
    r = await client.get(f"/api/v1/projects/{project_a['id']}/dashboard", headers=owner_b_h)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cross_project_incident_get_denied(
    client: AsyncClient, owner_b_h: dict, incident_a: dict, project_a: dict
):
    r = await client.get(
        f"/api/v1/incidents/{incident_a['id']}",
        params={"project_id": project_a["id"]},
        headers=owner_b_h,
    )
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_cross_project_incident_stats_denied(
    client: AsyncClient, owner_b_h: dict, project_a: dict
):
    r = await client.get(
        "/api/v1/incidents/stats",
        params={"project_id": project_a["id"]},
        headers=owner_b_h,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cross_project_compliance_obligations_denied(
    client: AsyncClient, owner_b_h: dict, project_a: dict
):
    r = await client.get(
        "/api/v1/compliance/obligations",
        params={"project_id": project_a["id"]},
        headers=owner_b_h,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cross_project_compliance_score_denied(
    client: AsyncClient, owner_b_h: dict, project_a: dict
):
    r = await client.get(
        "/api/v1/compliance/score",
        params={"project_id": project_a["id"]},
        headers=owner_b_h,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cross_project_evidence_download_denied(
    client: AsyncClient, owner_b_h: dict, evidence_a: dict, project_a: dict
):
    r = await client.get(
        f"/api/v1/evidence/{evidence_a['id']}/download",
        params={"project_id": project_a["id"]},
        headers=owner_b_h,
    )
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_cross_project_regenerate_api_key_denied(
    client: AsyncClient, owner_b_h: dict, project_a: dict
):
    r = await client.post(
        f"/api/v1/projects/{project_a['id']}/regenerate-key",
        headers=owner_b_h,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cross_project_demo_events_denied(
    client: AsyncClient, owner_b_h: dict, project_a: dict
):
    r = await client.post(
        "/api/v1/demo/events",
        json={"project_id": project_a["id"], "count": 1},
        headers=owner_b_h,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_cross_project_evidence_upload_denied(
    client: AsyncClient, owner_b_h: dict, incident_a: dict
):
    r = await client.post(
        f"/api/v1/incidents/{incident_a['id']}/evidence",
        files={"file": ("evil.txt", io.BytesIO(b"pwn"), "text/plain")},
        headers=owner_b_h,
    )
    assert r.status_code in (403, 404)


# ── Vertical escalation ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_viewer_cannot_create_incident(
    client: AsyncClient, viewer_a_h: dict, project_a: dict
):
    r = await client.post(
        "/api/v1/incidents",
        json={"title": "Viewer escalation", "severity": "low", "project_id": project_a["id"]},
        headers=viewer_a_h,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_manage_users(
    client: AsyncClient, viewer_a_h: dict
):
    assert (await client.get("/api/v1/users", headers=viewer_a_h)).status_code == 403


@pytest.mark.asyncio
async def test_analyst_cannot_access_platform(
    client: AsyncClient, owner_a_h: dict
):
    assert (await client.get("/api/v1/platform/dashboard", headers=owner_a_h)).status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_upsert_compliance(
    client: AsyncClient, viewer_a_h: dict, project_a: dict
):
    r = await client.post(
        "/api/v1/compliance/obligations",
        json={"framework": "GDPR", "control_id": "x", "control_name": "X", "status": "compliant"},
        params={"project_id": project_a["id"]},
        headers=viewer_a_h,
    )
    assert r.status_code == 403


# ── Positive controls (owner access works) ───────────────────────────────────

@pytest.mark.asyncio
async def test_owner_can_access_own_project(
    client: AsyncClient, owner_a_h: dict, project_a: dict
):
    r = await client.get(f"/api/v1/projects/{project_a['id']}", headers=owner_a_h)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_owner_can_download_own_evidence(
    client: AsyncClient, owner_a_h: dict, evidence_a: dict, project_a: dict
):
    r = await client.get(
        f"/api/v1/evidence/{evidence_a['id']}/download",
        params={"project_id": project_a["id"]},
        headers=owner_a_h,
    )
    assert r.status_code == 200
