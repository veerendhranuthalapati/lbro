"""G11: regulatory dispatch blocked until inferred obligations accepted and assessment confirmed."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.compliance import ComplianceRecord
from app.models.asset import IncidentExposureAssessment
from tests.test_compliance import _create_project


@pytest.mark.asyncio
async def test_g11_dispatch_refused_while_inferred_obligations_pending(
    client: AsyncClient, analyst_headers: dict, auth_headers: dict, db
):
    project_id = await _create_project(client, analyst_headers, "G11 Dispatch Block")
    inc = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Exposure blocks dispatch",
            "description": "auth.block.local",
            "severity": "high",
            "personal_data_involved": True,
            "affected_jurisdictions": ["EU"],
            "network_features": {"destination_ip": "10.0.0.9"},
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
            "name": "Auth",
            "asset_type": "database",
            "classification": "confidential",
            "data_categories": ["authentication_credentials"],
            "identifiers": [{"type": "hostname", "value": "auth.block.local"}],
            "residency": [{"jurisdiction_code": "EU", "record_count": 5, "count_basis": "exact"}],
        },
        headers=analyst_headers,
    )
    assert (await client.post(f"/api/v1/incidents/{iid}/exposure", headers=analyst_headers)).status_code == 200

    inferred = (
        await db.execute(
            select(ComplianceRecord).where(
                ComplianceRecord.incident_id == iid,
                ComplianceRecord.source == "inferred",
                ComplianceRecord.analyst_decision == "pending",
            )
        )
    ).scalars().all()
    notifs = await client.get(f"/api/v1/notifications?incident_id={iid}", headers=auth_headers)
    assert notifs.status_code == 200
    items = notifs.json()["items"]
    if not inferred or not items:
        pytest.skip("Need both inferred obligations and regulatory notification drafts")

    dispatch = await client.post(
        f"/api/v1/notifications/{items[0]['id']}/dispatch",
        headers=auth_headers,
    )
    assert dispatch.status_code == 409
    assert "inferred" in dispatch.json()["detail"].lower() or "provisional" in dispatch.json()["detail"].lower()


@pytest.mark.asyncio
async def test_g11_dispatch_allowed_after_obligations_accepted_and_confirmed(
    client: AsyncClient, analyst_headers: dict, auth_headers: dict, db
):
    project_id = await _create_project(client, analyst_headers, "G11 Dispatch Allow")
    inc = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Accept then dispatch",
            "description": "auth.allow.local",
            "severity": "high",
            "personal_data_involved": True,
            "affected_jurisdictions": ["EU"],
            "network_features": {"destination_ip": "10.0.0.8"},
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
            "name": "Auth2",
            "asset_type": "database",
            "classification": "confidential",
            "data_categories": ["authentication_credentials"],
            "identifiers": [{"type": "hostname", "value": "auth.allow.local"}],
            "residency": [{"jurisdiction_code": "EU", "record_count": 5, "count_basis": "exact"}],
        },
        headers=analyst_headers,
    )
    assert (await client.post(f"/api/v1/incidents/{iid}/exposure", headers=analyst_headers)).status_code == 200

    records = (
        await db.execute(
            select(ComplianceRecord).where(
                ComplianceRecord.incident_id == iid,
                ComplianceRecord.source == "inferred",
            )
        )
    ).scalars().all()
    for rec in records:
        rec.analyst_decision = "accepted"
        rec.provisional = False
    assessment = (
        await db.execute(
            select(IncidentExposureAssessment)
            .where(IncidentExposureAssessment.incident_id == iid)
            .order_by(IncidentExposureAssessment.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if assessment:
        assessment.status = "confirmed"
    await db.flush()

    notifs = await client.get(f"/api/v1/notifications?incident_id={iid}", headers=auth_headers)
    if not notifs.json()["items"]:
        pytest.skip("No regulatory notifications")
    dispatch = await client.post(
        f"/api/v1/notifications/{notifs.json()['items'][0]['id']}/dispatch",
        headers=auth_headers,
    )
    assert dispatch.status_code == 200
