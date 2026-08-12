"""Multi-project ownership and ProjectMember authorization tests."""
from __future__ import annotations

import io
import uuid
import zipfile

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.services.project_service import ProjectService
from app.schemas.project import ProjectCreate


@pytest_asyncio.fixture
async def user_a(db: AsyncSession) -> User:
    u = User(
        email="multi_a@lbro-test.com",
        username="multi_a",
        full_name="User A",
        hashed_password=hash_password("TestPass123!"),
        role="analyst",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def user_b(db: AsyncSession) -> User:
    u = User(
        email="multi_b@lbro-test.com",
        username="multi_b",
        full_name="User B",
        hashed_password=hash_password("TestPass123!"),
        role="analyst",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    await db.flush()
    return u


@pytest_asyncio.fixture
async def projects_a(
    db: AsyncSession, user_a: User
) -> tuple[Project, Project, str, str]:
    svc = ProjectService(db)
    p1, key1 = await svc.create(
        ProjectCreate(name="Project A1", environment="production"), user_a.id
    )
    p2, key2 = await svc.create(
        ProjectCreate(name="Project A2", environment="production"), user_a.id
    )
    await db.commit()
    return p1, p2, key1, key2


@pytest_asyncio.fixture
async def project_b(db: AsyncSession, user_b: User) -> tuple[Project, str]:
    svc = ProjectService(db)
    p, key = await svc.create(
        ProjectCreate(name="Project B1", environment="production"), user_b.id
    )
    await db.commit()
    return p, key


@pytest.mark.asyncio
async def test_user_can_own_multiple_projects(
    client: AsyncClient, user_a: User, projects_a
):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a.email, "password": "TestPass123!"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/projects", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    names = {p["name"] for p in data["items"]}
    assert names == {"Project A1", "Project A2"}
    for item in data["items"]:
        assert item["my_role"] == "admin"


@pytest.mark.asyncio
async def test_cross_user_project_access_denied(
    client: AsyncClient, user_a: User, user_b: User, projects_a, project_b
):
    p_a1, _, _, _ = projects_a
    p_b1, _ = project_b

    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a.email, "password": "TestPass123!"},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    login_b = await client.post(
        "/api/v1/auth/login",
        json={"email": user_b.email, "password": "TestPass123!"},
    )
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # User A can access A1, not B1
    assert (await client.get(f"/api/v1/projects/{p_a1.id}", headers=headers_a)).status_code == 200
    assert (await client.get(f"/api/v1/projects/{p_b1.id}", headers=headers_a)).status_code == 403

    # User B can access B1, not A1
    assert (await client.get(f"/api/v1/projects/{p_b1.id}", headers=headers_b)).status_code == 200
    assert (await client.get(f"/api/v1/projects/{p_a1.id}", headers=headers_b)).status_code == 403


@pytest.mark.asyncio
async def test_member_can_access_shared_project(
    db: AsyncSession,
    client: AsyncClient,
    user_a: User,
    user_b: User,
    project_b,
):
    p_b1, _ = project_b
    db.add(
        ProjectMember(
            project_id=p_b1.id,
            user_id=user_a.id,
            role="analyst",
            invited_by=user_b.id,
        )
    )
    await db.commit()

    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a.email, "password": "TestPass123!"},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    resp = await client.get(f"/api/v1/projects/{p_b1.id}", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["my_role"] == "analyst"


@pytest.mark.asyncio
async def test_viewer_cannot_regenerate_api_key(
    db: AsyncSession,
    client: AsyncClient,
    user_a: User,
    user_b: User,
    project_b,
):
    p_b1, _ = project_b
    db.add(
        ProjectMember(
            project_id=p_b1.id,
            user_id=user_a.id,
            role="viewer",
            invited_by=user_b.id,
        )
    )
    await db.commit()

    login_a = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a.email, "password": "TestPass123!"},
    )
    headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    resp = await client.post(
        f"/api/v1/projects/{p_b1.id}/regenerate-key", headers=headers_a
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_key_scoped_to_project(
    client: AsyncClient, projects_a, project_b
):
    _, _, key_a1, _ = projects_a
    p_b1, key_b1 = project_b

    # Key A1 ingests into A1 only
    r1 = await client.post(
        "/api/v1/events",
        json={"event_type": "auth_failure", "severity": "high", "message": "test a1"},
        headers={"Authorization": f"Bearer {key_a1}"},
    )
    assert r1.status_code == 202
    assert r1.json()["project_id"] == str(projects_a[0].id)

    r2 = await client.post(
        "/api/v1/events",
        json={"event_type": "auth_failure", "severity": "high", "message": "test b1"},
        headers={"Authorization": f"Bearer {key_b1}"},
    )
    assert r2.status_code == 202
    assert r2.json()["project_id"] == str(p_b1.id)

    # A1 key cannot read B1 events
    list_a = await client.get(
        "/api/v1/events",
        headers={"Authorization": f"Bearer {key_a1}"},
    )
    assert list_a.status_code == 200
    for ev in list_a.json()["items"]:
        assert ev["project_id"] == str(projects_a[0].id)


@pytest.mark.asyncio
async def test_sdk_download_no_secrets(
    client: AsyncClient, user_a: User, projects_a
):
    p_a1, _, key_a1, _ = projects_a
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": user_a.email, "password": "TestPass123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get(
        f"/api/v1/projects/{p_a1.id}/sdk/python", headers=headers
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        env_text = zf.read("lbro-sdk/.env.example").decode()
        assert "YOUR_PROJECT_API_KEY" in env_text
        assert key_a1 not in env_text


@pytest.mark.asyncio
async def test_registration_does_not_auto_create_project(
    client: AsyncClient, db: AsyncSession
):
    email = f"newuser_{uuid.uuid4().hex[:8]}@lbro-test.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPass123!",
            "full_name": "New User",
        },
    )
    assert resp.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "TestPass123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    projects = await client.get("/api/v1/projects", headers=headers)
    assert projects.status_code == 200
    assert projects.json()["total"] == 0
