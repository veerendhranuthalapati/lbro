"""Safety: inferred obligations never auto-dispatch notifications."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.compliance import ComplianceRecord
from app.models.notification import Notification
from tests.test_compliance import _create_project


@pytest.mark.asyncio
async def test_inferred_records_not_auto_notified(
    client: AsyncClient, analyst_headers: dict, db
):
    project_id = await _create_project(client, analyst_headers, "Exposure Safety Project")
    inc = await client.post(
        "/api/v1/incidents",
        json={
            "title": "SSH brute force on auth store",
            "description": "auth.demo.local",
            "severity": "high",
            "personal_data_involved": True,
            "network_features": {"destination_ip": "10.0.0.1"},
        },
        params={"project_id": project_id},
        headers=analyst_headers,
    )
    assert inc.status_code == 201
    incident_id = inc.json()["id"]
    iid = uuid.UUID(incident_id)

    await client.post(
        "/api/v1/assets",
        params={"project_id": project_id},
        json={
            "name": "Auth Store",
            "asset_type": "database",
            "classification": "confidential",
            "data_categories": ["authentication_credentials", "personal_identifiers"],
            "identifiers": [{"type": "hostname", "value": "auth.demo.local"}],
            "residency": [{"jurisdiction_code": "EU", "record_count": 50, "count_basis": "exact"}],
        },
        headers=analyst_headers,
    )

    recompute = await client.post(
        f"/api/v1/incidents/{incident_id}/exposure",
        headers=analyst_headers,
    )
    assert recompute.status_code == 200, recompute.text

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

    if inferred:
        assert not notifs or all(n.status == "pending" for n in notifs)
