"""Cross-project notification isolation regression tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident
from app.models.notification import Notification


@pytest.mark.asyncio
async def test_analyst_cannot_list_other_project_notifications(
    client: AsyncClient,
    bob_h: dict,
    alice_h: dict,
    portfolio_project: dict,
    sql_injection_incident: dict,
    db: AsyncSession,
):
    notif = Notification(
        id=uuid.uuid4(),
        incident_id=uuid.UUID(sql_injection_incident["id"]),
        regulation="GDPR",
        jurisdiction="EU",
        authority="DPA",
        subject="Portfolio breach",
        body="Test",
        deadline=datetime.now(timezone.utc),
        status="pending",
    )
    db.add(notif)
    await db.flush()

    bob_list = await client.get("/api/v1/notifications", headers=bob_h)
    assert bob_list.status_code == 200
    ids = {item["id"] for item in bob_list.json()["items"]}
    assert str(notif.id) not in ids

    alice_list = await client.get("/api/v1/notifications", headers=alice_h)
    assert alice_list.status_code == 200
    alice_ids = {item["id"] for item in alice_list.json()["items"]}
    assert str(notif.id) in alice_ids


@pytest.mark.asyncio
async def test_analyst_cannot_get_approve_or_send_other_project_notification(
    client: AsyncClient,
    bob_h: dict,
    sql_injection_incident: dict,
    db: AsyncSession,
):
    notif = Notification(
        id=uuid.uuid4(),
        incident_id=uuid.UUID(sql_injection_incident["id"]),
        regulation="HIPAA",
        jurisdiction="US",
        authority="HHS",
        subject="Portfolio HIPAA",
        body="Test",
        deadline=datetime.now(timezone.utc),
        status="pending",
    )
    db.add(notif)
    await db.flush()

    for method, path in [
        ("GET", f"/api/v1/notifications/{notif.id}"),
        ("POST", f"/api/v1/notifications/{notif.id}/approve"),
        ("POST", f"/api/v1/notifications/{notif.id}/send"),
        ("POST", f"/api/v1/notifications/{notif.id}/dispatch"),
    ]:
        if method == "GET":
            resp = await client.get(path, headers=bob_h)
        else:
            resp = await client.post(path, headers=bob_h)
        assert resp.status_code in (403, 404), f"{method} {path} returned {resp.status_code}"


@pytest.mark.asyncio
async def test_owner_sees_only_own_project_notifications(
    client: AsyncClient,
    bob_h: dict,
    hospital_project: dict,
    xss_incident: dict,
    sql_injection_incident: dict,
    db: AsyncSession,
):
    alice_notif = Notification(
        id=uuid.uuid4(),
        incident_id=uuid.UUID(sql_injection_incident["id"]),
        regulation="GDPR",
        jurisdiction="EU",
        authority="DPA",
        subject="Alice only",
        body="Test",
        deadline=datetime.now(timezone.utc),
        status="pending",
    )
    bob_notif = Notification(
        id=uuid.uuid4(),
        incident_id=uuid.UUID(xss_incident["id"]),
        regulation="HIPAA",
        jurisdiction="US",
        authority="HHS",
        subject="Bob only",
        body="Test",
        deadline=datetime.now(timezone.utc),
        status="pending",
    )
    db.add_all([alice_notif, bob_notif])
    await db.flush()

    resp = await client.get("/api/v1/notifications", headers=bob_h)
    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()["items"]}
    assert str(bob_notif.id) in ids
    assert str(alice_notif.id) not in ids
