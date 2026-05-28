"""
LBRO — Integration tests. Uses real Postgres via DATABASE_URL.
NullPool prevents asyncpg from binding connections to the wrong event loop.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    # NullPool: no connection reuse, so no loop conflicts
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(test_engine):
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


TEST_API_KEY = "ci-test-api-key-for-tests-only"

@pytest_asyncio.fixture
async def client(test_engine):
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Patch API_KEY on the live settings singleton so verify_api_key passes
    from app.core import config as _cfg
    original_key = _cfg.settings.API_KEY
    _cfg.settings.API_KEY = TEST_API_KEY

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-LBRO-API-Key": TEST_API_KEY},
    ) as c:
        yield c
    app.dependency_overrides.clear()
    _cfg.settings.API_KEY = original_key


@pytest.fixture
def mock_sqs(monkeypatch):
    mock = MagicMock()
    mock.send_message.return_value = {"MessageId": "test-msg-id-123"}
    # SQS client is now a singleton in app.core.aws_clients; patch get_sqs there
    monkeypatch.setattr("app.core.aws_clients.get_sqs", lambda: mock)
    return mock


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestHealthEndpoints:
    async def test_liveness(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_readiness_with_db(self, client):
        # SQS_QUEUE_URL is not configured in test env — readiness returns 503.
        # What matters is that the DB check passes and the response is structured.
        resp = await client.get("/health/ready")
        data = resp.json()
        assert data["checks"]["database"] == "ok"
        # Either fully ready (200) or degraded due to missing SQS config (503)
        assert resp.status_code in (200, 503)


class TestIncidentIngestion:
    async def test_create_incident_minimal(self, client, mock_sqs):
        resp = await client.post("/api/v1/incidents", json={
            "title": "Unauthorized access on prod-db-01",
            "severity": "HIGH", "source_system": "guardduty", "contains_pii": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "HIGH"
        assert data["status"] in ("detected", "triaging")

    async def test_pii_detects_gdpr_dpdpa(self, client, mock_sqs):
        resp = await client.post("/api/v1/incidents", json={
            "title": "PII exfil", "severity": "CRITICAL", "source_system": "siem",
            "contains_pii": True, "affected_records_count": 50000,
        })
        assert resp.status_code == 201
        jx = resp.json()["jurisdictions"]
        assert "GDPR" in jx and "DPDPA" in jx

    async def test_phi_detects_hipaa(self, client, mock_sqs):
        resp = await client.post("/api/v1/incidents", json={
            "title": "Medical records accessed", "severity": "CRITICAL",
            "source_system": "splunk", "contains_phi": True,
        })
        assert resp.status_code == 201
        assert "HIPAA" in resp.json()["jurisdictions"]

    async def test_creates_notification_records(self, client, mock_sqs):
        create_resp = await client.post("/api/v1/incidents", json={
            "title": "Ransomware", "severity": "CRITICAL",
            "source_system": "crowdstrike", "contains_pii": True,
        })
        iid = create_resp.json()["id"]
        notif_resp = await client.get(f"/api/v1/incidents/{iid}/notifications")
        assert notif_resp.status_code == 200
        notes = notif_resp.json()
        assert len(notes) >= 1
        assert all(n["hours_remaining"] > 0 for n in notes)

    async def test_enqueues_to_sqs(self, client, mock_sqs):
        with patch("app.core.config.settings.SQS_QUEUE_URL", "https://sqs.test/queue"):
            resp = await client.post("/api/v1/incidents", json={
                "title": "SQS test", "severity": "MEDIUM", "source_system": "test",
            })
        assert resp.status_code == 201
        mock_sqs.send_message.assert_called_once()
        msg = json.loads(mock_sqs.send_message.call_args[1]["MessageBody"])
        assert msg["incident_id"] == resp.json()["id"]

    async def test_get_incident_detail_with_timeline(self, client, mock_sqs):
        create_resp = await client.post("/api/v1/incidents", json={
            "title": "Detail test", "severity": "LOW", "source_system": "test-detector",
        })
        iid = create_resp.json()["id"]
        detail_resp = await client.get(f"/api/v1/incidents/{iid}")
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert len(data["timeline"]) >= 1
        assert data["timeline"][0]["event_type"] == "incident.created"

    async def test_list_incidents_pagination(self, client, mock_sqs):
        for i in range(5):
            await client.post("/api/v1/incidents", json={
                "title": f"Incident {i}", "severity": "LOW", "source_system": "test",
            })
        resp = await client.get("/api/v1/incidents?page=1&page_size=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3

    async def test_list_filter_by_severity(self, client, mock_sqs):
        await client.post("/api/v1/incidents", json={"title": "Crit", "severity": "CRITICAL", "source_system": "t"})
        await client.post("/api/v1/incidents", json={"title": "Low",  "severity": "LOW",      "source_system": "t"})
        resp = await client.get("/api/v1/incidents?severity=CRITICAL")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["severity"] == "CRITICAL"

    async def test_update_status_to_contained(self, client, mock_sqs):
        create_resp = await client.post("/api/v1/incidents", json={
            "title": "Status test", "severity": "HIGH", "source_system": "test",
        })
        iid = create_resp.json()["id"]
        update_resp = await client.patch(f"/api/v1/incidents/{iid}", json={"status": "contained"})
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["status"] == "contained"
        assert data["contained_at"] is not None
        assert data["response_time_seconds"] is not None

    async def test_404_on_missing_incident(self, client):
        resp = await client.get("/api/v1/incidents/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
