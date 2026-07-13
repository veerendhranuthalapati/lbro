"""Integration tests — Event ingestion pipeline.

Covers:
  - POST /api/v1/events: valid proj_* key -> 202 Accepted
  - POST /api/v1/events: user JWT -> 401 (wrong token type)
  - POST /api/v1/events: missing/wrong API key -> 401
  - POST /api/v1/events: invalid event_type -> 422
  - Project isolation: API key from project A cannot submit to project B
  - project_id is always resolved from the authenticated API key (never from body)
  - Batch endpoint: POST /api/v1/events/batch
  - GET /api/v1/events: lists only events for the authenticated project
  - High/critical severity events trigger auto-incident creation
  - Ingested event has correct project_id from the API key
"""
from __future__ import annotations

import uuid as _uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def project_alpha(client: AsyncClient, admin_user: User, admin_token: str) -> dict:
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Alpha"},
        headers=_auth(admin_token),
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


@pytest_asyncio.fixture
async def project_beta(client: AsyncClient, analyst_user: User, analyst_token: str) -> dict:
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Beta"},
        headers=_auth(analyst_token),
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


@pytest_asyncio.fixture
def alpha_key(project_alpha: dict) -> str:
    return project_alpha["api_key"]


@pytest_asyncio.fixture
def beta_key(project_beta: dict) -> str:
    return project_beta["api_key"]


def _event_payload(
    event_type: str = "auth_failure",
    severity: str = "medium",
    source_ip: str = "10.0.0.1",
    message: str = "test event",
    **extra,
) -> dict:
    return {"event_type": event_type, "severity": severity,
            "source_ip": source_ip, "message": message, **extra}


# ─────────────────────────────────────────────────────────────────────────────
# 1. AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

class TestEventIngestionAuth:

    @pytest.mark.asyncio
    async def test_valid_project_key_returns_202(self, client: AsyncClient, alpha_key: str):
        resp = await client.post("/api/v1/events", json=_event_payload(), headers=_auth(alpha_key))
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_missing_auth_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/events", json=_event_payload())
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_user_jwt_on_events_endpoint_returns_401(
        self, client: AsyncClient, admin_user: User, admin_token: str
    ):
        resp = await client.post("/api/v1/events", json=_event_payload(), headers=_auth(admin_token))
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_api_key_returns_401(self, client: AsyncClient):
        fake_key = "proj_" + "x" * 32
        resp = await client.post("/api/v1/events", json=_event_payload(), headers=_auth(fake_key))
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_non_proj_prefixed_key_returns_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/events", json=_event_payload(), headers=_auth("not_a_proj_key_abc123")
        )
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# 2. VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

class TestEventIngestionValidation:

    @pytest.mark.asyncio
    async def test_invalid_event_type_returns_422(self, client: AsyncClient, alpha_key: str):
        resp = await client.post(
            "/api/v1/events",
            json=_event_payload(event_type="not_a_real_type"),
            headers=_auth(alpha_key),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_severity_returns_422(self, client: AsyncClient, alpha_key: str):
        resp = await client.post(
            "/api/v1/events",
            json=_event_payload(severity="catastrophic"),
            headers=_auth(alpha_key),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_event_type_returns_422(self, client: AsyncClient, alpha_key: str):
        resp = await client.post(
            "/api/v1/events",
            json={"severity": "high", "message": "no event type"},
            headers=_auth(alpha_key),
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.parametrize("event_type", [
        "auth_failure", "sql_injection", "xss", "brute_force", "port_scan",
        "suspicious_request", "system_log", "application_log", "nginx_log",
        "apache_log", "firewall_event", "windows_event", "linux_audit", "custom",
    ])
    async def test_all_valid_event_types_accepted(
        self, client: AsyncClient, alpha_key: str, event_type: str
    ):
        resp = await client.post(
            "/api/v1/events",
            json=_event_payload(event_type=event_type),
            headers=_auth(alpha_key),
        )
        assert resp.status_code == 202, f"event_type={event_type} rejected: {resp.text}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. PROJECT ISOLATION
# ─────────────────────────────────────────────────────────────────────────────

class TestEventProjectIsolation:

    @pytest.mark.asyncio
    async def test_project_id_is_resolved_from_api_key(
        self, client: AsyncClient, alpha_key: str, project_alpha: dict, db: AsyncSession
    ):
        """Events submitted with Alpha key must belong to Alpha, regardless of body."""
        resp = await client.post(
            "/api/v1/events",
            json={**_event_payload(), "project_id": "00000000-0000-0000-0000-000000000000"},
            headers=_auth(alpha_key),
        )
        assert resp.status_code == 202

        from app.models.security_event import SecurityEvent
        alpha_uuid = _uuid.UUID(project_alpha["id"])
        result = await db.execute(
            select(SecurityEvent)
            .where(SecurityEvent.project_id == alpha_uuid)
            .order_by(SecurityEvent.created_at.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        assert event is not None
        assert event.project_id == alpha_uuid, (
            "project_id was taken from the request body instead of the API key"
        )

    @pytest.mark.asyncio
    async def test_alpha_key_cannot_read_beta_events(
        self, client: AsyncClient, alpha_key: str, beta_key: str
    ):
        ingest = await client.post(
            "/api/v1/events",
            json=_event_payload(message="beta only event"),
            headers=_auth(beta_key),
        )
        assert ingest.status_code == 202

        list_resp = await client.get("/api/v1/events", headers=_auth(alpha_key))
        assert list_resp.status_code == 200
        messages = [e["message"] for e in list_resp.json().get("events", [])]
        assert "beta only event" not in messages, (
            "Alpha API key returned an event belonging to Beta"
        )

    @pytest.mark.asyncio
    async def test_list_events_scoped_to_authenticated_project(
        self, client: AsyncClient, alpha_key: str, project_alpha: dict, db: AsyncSession
    ):
        for i in range(3):
            await client.post(
                "/api/v1/events",
                json=_event_payload(message=f"alpha event {i}"),
                headers=_auth(alpha_key),
            )
        resp = await client.get("/api/v1/events", headers=_auth(alpha_key))
        assert resp.status_code == 200
        alpha_id = project_alpha["id"]
        for event in resp.json().get("events", []):
            assert str(event["project_id"]) == alpha_id, (
                "Event from a different project leaked into Alpha list"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 4. BATCH INGESTION
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchIngestion:

    @pytest.mark.asyncio
    async def test_batch_accepted(self, client: AsyncClient, alpha_key: str):
        events = [_event_payload(message=f"batch event {i}") for i in range(5)]
        resp = await client.post(
            "/api/v1/events/batch", json={"events": events}, headers=_auth(alpha_key)
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "accepted" in body
        assert body["accepted"] == 5

    @pytest.mark.asyncio
    async def test_batch_partial_success_on_invalid_events(
        self, client: AsyncClient, alpha_key: str
    ):
        events = [
            _event_payload(message="valid event"),
            {"event_type": "INVALID_TYPE", "severity": "high"},
            _event_payload(message="another valid"),
        ]
        resp = await client.post(
            "/api/v1/events/batch", json={"events": events}, headers=_auth(alpha_key)
        )
        assert resp.status_code in (202, 207)
        body = resp.json()
        assert body.get("accepted", 0) >= 2
        assert body.get("rejected", 0) >= 1

    @pytest.mark.asyncio
    async def test_batch_over_1000_rejected(self, client: AsyncClient, alpha_key: str):
        events = [_event_payload() for _ in range(1001)]
        resp = await client.post(
            "/api/v1/events/batch", json={"events": events}, headers=_auth(alpha_key)
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_batch_rejected(self, client: AsyncClient, alpha_key: str):
        resp = await client.post(
            "/api/v1/events/batch", json={"events": []}, headers=_auth(alpha_key)
        )
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# 5. AUTO-INCIDENT CREATION
# ─────────────────────────────────────────────────────────────────────────────

class TestAutoIncidentCreation:

    @pytest.mark.asyncio
    async def test_critical_event_creates_incident(
        self, client: AsyncClient, alpha_key: str, project_alpha: dict, db: AsyncSession
    ):
        resp = await client.post(
            "/api/v1/events",
            json=_event_payload(event_type="sql_injection", severity="critical",
                                message="Critical SQL injection detected"),
            headers=_auth(alpha_key),
        )
        assert resp.status_code == 202

        from app.models.incident import Incident
        alpha_uuid = _uuid.UUID(project_alpha["id"])
        result = await db.execute(
            select(Incident)
            .where(Incident.project_id == alpha_uuid)
            .order_by(Incident.created_at.desc())
            .limit(1)
        )
        incident = result.scalar_one_or_none()
        assert incident is not None, "No incident auto-created for critical event"
        assert incident.needs_analyst_review is True

    @pytest.mark.asyncio
    async def test_high_severity_event_creates_incident(
        self, client: AsyncClient, alpha_key: str, project_alpha: dict, db: AsyncSession
    ):
        resp = await client.post(
            "/api/v1/events",
            json=_event_payload(event_type="brute_force", severity="high",
                                message="High severity brute force"),
            headers=_auth(alpha_key),
        )
        assert resp.status_code == 202

        from app.models.incident import Incident
        alpha_uuid = _uuid.UUID(project_alpha["id"])
        result = await db.execute(
            select(Incident)
            .where(Incident.project_id == alpha_uuid)
            .order_by(Incident.created_at.desc())
            .limit(1)
        )
        incident = result.scalar_one_or_none()
        assert incident is not None, "No incident auto-created for high event"

    @pytest.mark.asyncio
    async def test_low_severity_event_does_not_create_incident(
        self, client: AsyncClient, alpha_key: str, project_alpha: dict, db: AsyncSession
    ):
        from app.models.incident import Incident
        from sqlalchemy import func

        alpha_uuid = _uuid.UUID(project_alpha["id"])
        count_before = (await db.execute(
            select(func.count(Incident.id)).where(Incident.project_id == alpha_uuid)
        )).scalar()

        await client.post(
            "/api/v1/events",
            json=_event_payload(event_type="system_log", severity="info"),
            headers=_auth(alpha_key),
        )

        count_after = (await db.execute(
            select(func.count(Incident.id)).where(Incident.project_id == alpha_uuid)
        )).scalar()
        assert count_after == count_before, (
            "Incident incorrectly created for info severity event"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. SECURITY EVENT PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityEventPersistence:

    @pytest.mark.asyncio
    async def test_ingested_event_stored_in_db(
        self, client: AsyncClient, alpha_key: str, project_alpha: dict, db: AsyncSession
    ):
        resp = await client.post(
            "/api/v1/events",
            json=_event_payload(event_type="port_scan", severity="medium",
                                source_ip="192.168.1.55",
                                message="Port scan from known attacker"),
            headers=_auth(alpha_key),
        )
        assert resp.status_code == 202

        from app.models.security_event import SecurityEvent
        alpha_uuid = _uuid.UUID(project_alpha["id"])
        result = await db.execute(
            select(SecurityEvent)
            .where(SecurityEvent.project_id == alpha_uuid)
            .where(SecurityEvent.message == "Port scan from known attacker")
            .limit(1)
        )
        event = result.scalar_one_or_none()
        assert event is not None
        assert event.event_type == "port_scan"
        assert event.severity == "medium"
        assert event.source_ip == "192.168.1.55"
        assert event.project_id == alpha_uuid

    @pytest.mark.asyncio
    async def test_processing_status_set_to_processed(
        self, client: AsyncClient, alpha_key: str, project_alpha: dict, db: AsyncSession
    ):
        await client.post(
            "/api/v1/events",
            json=_event_payload(message="status check event"),
            headers=_auth(alpha_key),
        )
        from app.models.security_event import SecurityEvent
        alpha_uuid = _uuid.UUID(project_alpha["id"])
        result = await db.execute(
            select(SecurityEvent)
            .where(SecurityEvent.project_id == alpha_uuid)
            .where(SecurityEvent.message == "status check event")
            .limit(1)
        )
        event = result.scalar_one_or_none()
        assert event is not None
        assert event.processing_status == "processed"

    @pytest.mark.asyncio
    async def test_event_response_contains_event_id(
        self, client: AsyncClient, alpha_key: str
    ):
        resp = await client.post(
            "/api/v1/events", json=_event_payload(), headers=_auth(alpha_key)
        )
        assert resp.status_code == 202
        body = resp.json()
        assert "id" in body or "event_id" in body, "Response must include the new event ID"
