"""G11: inferred obligations must not auto-dispatch; dispatch path requires explicit action."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.compliance import ComplianceRecord
from app.models.notification import Notification
from tests.test_compliance import _create_project


@pytest.mark.asyncio
async def test_g11_inferred_compliance_never_auto_sent(
    client: AsyncClient, analyst_headers: dict, db
):
    """Exposure → inferred compliance records; dispatch only via POST .../dispatch (notifications.py)."""
    project_id = await _create_project(client, analyst_headers, "G11 Dispatch Gate")
    inc = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Credential stuffing on auth",
            "description": "auth.g11.local",
            "severity": "high",
            "personal_data_involved": True,
            "network_features": {"destination_ip": "10.0.0.2"},
        },
        params={"project_id": project_id},
        headers=analyst_headers,
    )
    assert inc.status_code == 201
    iid = uuid.UUID(inc.json()["id"])

    await client.post(
        "/api/v1/assets",
        params={"project_id": project_id},
        json={
            "name": "Auth DB",
            "asset_type": "database",
            "classification": "confidential",
            "data_categories": ["authentication_credentials"],
            "identifiers": [{"type": "hostname", "value": "auth.g11.local"}],
            "residency": [{"jurisdiction_code": "EU", "record_count": 10, "count_basis": "exact"}],
        },
        headers=analyst_headers,
    )
    assert (await client.post(f"/api/v1/incidents/{iid}/exposure", headers=analyst_headers)).status_code == 200

    inferred = (
        await db.execute(
            select(ComplianceRecord).where(
                ComplianceRecord.incident_id == iid,
                ComplianceRecord.source == "inferred",
            )
        )
    ).scalars().all()
    notifs = (
        await db.execute(select(Notification).where(Notification.incident_id == iid))
    ).scalars().all()

    for n in notifs:
        assert n.status in ("pending", "draft"), f"notification {n.id} must not be sent without approval"
    if inferred:
        assert all(n.status != "sent" for n in notifs), "inferred path must not auto-dispatch"
