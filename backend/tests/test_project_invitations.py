"""Project invitations, member management, and last-admin protection tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.invitation_tokens import hash_invitation_token, normalize_invitation_email
from app.core.security import hash_password
from app.models.project import Project
from app.models.project_invitation import ProjectInvitation
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService


async def _register_and_token(client: AsyncClient, email: str, username: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "full_name": username.title(),
            "password": "TestPass123!",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def _auth(client: AsyncClient, token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def owner_token(client: AsyncClient) -> str:
    return await _register_and_token(client, "owner_inv@lbro-test.com", "owner_inv")


@pytest_asyncio.fixture
async def invitee_token(client: AsyncClient) -> str:
    return await _register_and_token(client, "invitee@lbro-test.com", "invitee")


@pytest_asyncio.fixture
async def project_id(client: AsyncClient, owner_token: str) -> str:
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Invite Test Project", "environment": "production"},
        headers=await _auth(client, owner_token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_and_list_invitation(
    client: AsyncClient, owner_token: str, project_id: str
):
    headers = await _auth(client, owner_token)
    resp = await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"email": "invitee@lbro-test.com", "role": "analyst"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["invited_email"] == "invitee@lbro-test.com"
    assert body["role"] == "analyst"
    assert body["invite_token"].startswith("inv_")

    listed = await client.get(
        f"/api/v1/projects/{project_id}/invitations", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


@pytest.mark.asyncio
async def test_invitee_sees_pending_and_accepts(
    client: AsyncClient, owner_token: str, invitee_token: str, project_id: str
):
    owner_headers = await _auth(client, owner_token)
    create = await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"email": "invitee@lbro-test.com", "role": "viewer"},
        headers=owner_headers,
    )
    invitation_id = create.json()["id"]
    token = create.json()["invite_token"]

    invitee_headers = await _auth(client, invitee_token)
    pending = await client.get("/api/v1/invitations/pending", headers=invitee_headers)
    assert pending.status_code == 200
    assert pending.json()["total"] == 1

    accept = await client.post(
        f"/api/v1/invitations/{invitation_id}/accept",
        json={"token": token},
        headers=invitee_headers,
    )
    assert accept.status_code == 200, accept.text
    assert accept.json()["role"] == "viewer"

    projects = await client.get("/api/v1/projects", headers=invitee_headers)
    assert projects.status_code == 200
    ids = [p["id"] for p in projects.json()["items"]]
    assert project_id in ids


@pytest.mark.asyncio
async def test_wrong_email_cannot_accept(
    client: AsyncClient, owner_token: str, project_id: str, db: AsyncSession
):
    other_token = await _register_and_token(client, "other@lbro-test.com", "other")
    owner_headers = await _auth(client, owner_token)
    create = await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"email": "invitee@lbro-test.com", "role": "analyst"},
        headers=owner_headers,
    )
    invitation_id = create.json()["id"]
    token = create.json()["invite_token"]

    bad = await client.post(
        f"/api/v1/invitations/{invitation_id}/accept",
        json={"token": token},
        headers=await _auth(client, other_token),
    )
    assert bad.status_code == 403


@pytest.mark.asyncio
async def test_expired_invitation_rejected(
    client: AsyncClient, owner_token: str, invitee_token: str, project_id: str, db: AsyncSession
):
    owner_headers = await _auth(client, owner_token)
    create = await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"email": "invitee@lbro-test.com", "role": "analyst"},
        headers=owner_headers,
    )
    invitation_id = uuid.UUID(create.json()["id"])
    token = create.json()["invite_token"]

    inv = (
        await db.execute(
            __import__("sqlalchemy").select(ProjectInvitation).where(
                ProjectInvitation.id == invitation_id
            )
        )
    ).scalar_one()
    inv.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db.commit()

    resp = await client.post(
        f"/api/v1/invitations/{invitation_id}/accept",
        json={"token": token},
        headers=await _auth(client, invitee_token),
    )
    assert resp.status_code == 410


@pytest.mark.asyncio
async def test_non_admin_cannot_invite(
    client: AsyncClient, owner_token: str, invitee_token: str, project_id: str
):
    owner_headers = await _auth(client, owner_token)
    await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"email": "invitee@lbro-test.com", "role": "analyst"},
        headers=owner_headers,
    )
    accept = await client.get(
        "/api/v1/invitations/pending",
        headers=await _auth(client, invitee_token),
    )
    # accept pending first via list
    pending = accept.json()["items"][0]
    await client.post(
        f"/api/v1/invitations/{pending['id']}/accept",
        json={},
        headers=await _auth(client, invitee_token),
    )

    forbidden = await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"email": "other@lbro-test.com", "role": "viewer"},
        headers=await _auth(client, invitee_token),
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_update_member_role_and_last_admin_protection(
    client: AsyncClient, db: AsyncSession
):
    owner_token = await _register_and_token(client, "admin_prot@lbro-test.com", "admin_prot")
    headers = await _auth(client, owner_token)
    project = await client.post(
        "/api/v1/projects",
        json={"name": "Admin Protection", "environment": "production"},
        headers=headers,
    )
    project_id = project.json()["id"]
    members = await client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    owner_member = members.json()["items"][0]

    demote = await client.patch(
        f"/api/v1/projects/{project_id}/members/{owner_member['id']}",
        json={"role": "viewer"},
        headers=headers,
    )
    assert demote.status_code == 400


@pytest.mark.asyncio
async def test_member_incident_access_after_invite(
    client: AsyncClient, owner_token: str, invitee_token: str, project_id: str
):
    owner_headers = await _auth(client, owner_token)
    create = await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"email": "invitee@lbro-test.com", "role": "analyst"},
        headers=owner_headers,
    )
    inv_id = create.json()["id"]
    await client.post(
        f"/api/v1/invitations/{inv_id}/accept",
        json={"token": create.json()["invite_token"]},
        headers=await _auth(client, invitee_token),
    )

    inc = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Member visible incident",
            "severity": "medium",
            "project_id": project_id,
        },
        headers=owner_headers,
    )
    assert inc.status_code == 201

    listed = await client.get(
        "/api/v1/incidents",
        params={"project_id": project_id},
        headers=await _auth(client, invitee_token),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


@pytest.mark.asyncio
async def test_viewer_cannot_create_incident(
    client: AsyncClient, owner_token: str, invitee_token: str, project_id: str
):
    owner_headers = await _auth(client, owner_token)
    create = await client.post(
        f"/api/v1/projects/{project_id}/invitations",
        json={"email": "invitee@lbro-test.com", "role": "viewer"},
        headers=owner_headers,
    )
    await client.post(
        f"/api/v1/invitations/{create.json()['id']}/accept",
        json={"token": create.json()["invite_token"]},
        headers=await _auth(client, invitee_token),
    )

    denied = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Viewer attempt",
            "severity": "low",
            "project_id": project_id,
        },
        headers=await _auth(client, invitee_token),
    )
    assert denied.status_code == 403
