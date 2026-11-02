"""G11: all notification send paths require approved status and dispatch RBAC."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.notification import Notification
from app.workers import notification_worker

pytest_plugins = ["tests.test_red_team_authorization"]


async def _create_incident_with_notification(client: AsyncClient, headers: dict) -> str:
    inc_resp = await client.post(
        "/api/v1/incidents",
        json={
            "title": "G11 notification gate",
            "severity": "high",
            "affected_jurisdictions": ["EU"],
            "personal_data_involved": True,
        },
        headers=headers,
    )
    assert inc_resp.status_code == 201
    incident_id = inc_resp.json()["id"]
    list_resp = await client.get(
        f"/api/v1/notifications?incident_id={incident_id}",
        headers=headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert items, "expected regulatory notification draft"
    return items[0]["id"]


@pytest.mark.asyncio
async def test_g11_send_endpoint_rejects_pending(client: AsyncClient, auth_headers: dict):
    notif_id = await _create_incident_with_notification(client, auth_headers)
    resp = await client.post(f"/api/v1/notifications/{notif_id}/send", headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_g11_worker_skips_pending(client: AsyncClient, auth_headers: dict, db, monkeypatch):
    notif_id = await _create_incident_with_notification(client, auth_headers)

    class _SessionCM:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, *exc):
            await self._session.commit()

    monkeypatch.setattr(
        "app.workers.notification_worker.AsyncSessionLocal",
        lambda: _SessionCM(db),
    )
    await notification_worker.send_notification(uuid.UUID(notif_id))
    n = (
        await db.execute(select(Notification).where(Notification.id == uuid.UUID(notif_id)))
    ).scalar_one()
    assert n.status == "pending"


@pytest.mark.asyncio
async def test_g11_viewer_cannot_dispatch(client: AsyncClient, viewer_a_h: dict, auth_headers: dict):
    notif_id = await _create_incident_with_notification(client, auth_headers)
    r = await client.post(f"/api/v1/notifications/{notif_id}/dispatch", headers=viewer_a_h)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_g11_dispatch_with_role_auto_approves_and_sends(client: AsyncClient, auth_headers: dict):
    notif_id = await _create_incident_with_notification(client, auth_headers)
    resp = await client.post(f"/api/v1/notifications/{notif_id}/dispatch", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] in ("sent", "failed")
