"""Realistic integration payloads — ML coverage, incident network fields, evidence capture."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.flow_profiles import build_dealership_scenario
from app.models.evidence import Evidence
from app.models.incident import Incident
from app.models.security_event import SecurityEvent


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


@pytest.mark.asyncio
async def test_realistic_sql_injection_ingestion_full_capture(
    client: AsyncClient,
    admin_token: str,
    db: AsyncSession,
):
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "Realistic ingest test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert proj.status_code in (200, 201)
    api_key = proj.json()["api_key"]
    body = build_dealership_scenario("sql_injection", seed=99)

    resp = await client.post("/api/v1/events", json=body, headers=_auth(api_key))
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data.get("destination_port") == body["payload"]["network"]["destination_port"]
    assert data.get("incident_id")
    assert data.get("ml_feature_coverage", 0) >= 0.99

    event_id = uuid.UUID(data["id"])
    ev = (
        await db.execute(select(SecurityEvent).where(SecurityEvent.id == event_id))
    ).scalar_one()
    assert ev.payload.get("network_features")
    assert len(ev.payload["network_features"]) >= 70

    inc_id = uuid.UUID(data["incident_id"])
    inc = (await db.execute(select(Incident).where(Incident.id == inc_id))).scalar_one()
    assert inc.destination_ip is not None
    assert inc.destination_port is not None
    assert inc.protocol == "TCP"
    assert inc.integration_context
    assert inc.integration_context.get("user_agent")

    ir = await client.get(
        f"/api/v1/incidents/{inc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ir.status_code == 200
    body = ir.json()
    assert body.get("destination_ip")
    assert body.get("user_agent")
    assert body.get("application")
    assert body.get("mitre_techniques")

    evidence = (
        await db.execute(select(Evidence).where(Evidence.incident_id == inc_id))
    ).scalars().all()
    assert len(evidence) >= 2
    names = {e.filename for e in evidence}
    assert any(n.startswith("ingestion-event-") for n in names)
    assert any(n.startswith("network-flow-") for n in names)

    detail = await client.get(f"/api/v1/events/{event_id}", headers=_auth(api_key))
    assert detail.status_code == 200
    assert detail.json()["payload"]["http"]
