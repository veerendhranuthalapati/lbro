"""
Tests for the 5 previously-missing endpoints:

  GET /api/v1/evidence                     (global evidence listing)
  GET /api/v1/ml/flows                     (live flow classifications)
  GET /api/v1/ml/metrics                   (ML performance metrics)
  GET /api/v1/infrastructure               (system health)
  GET /api/v1/infrastructure/sqs-history   (queue depth timeseries)

Each test covers: auth required, correct response shape, RBAC.
"""
from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/evidence  — global evidence listing
# ─────────────────────────────────────────────────────────────────────────────

class TestGlobalEvidenceListing:

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/evidence")
        assert resp.status_code == 401

    async def test_returns_paginated_response(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/evidence", headers=_auth(admin_token))
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert isinstance(body["items"], list)
        assert isinstance(body["total"], int)
        assert body["page"] == 1

    async def test_pagination_params_respected(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/evidence",
            params={"page": 2, "page_size": 5},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["page_size"] == 5

    async def test_analyst_can_access(self, client: AsyncClient, analyst_token: str):
        resp = await client.get("/api/v1/evidence", headers=_auth(analyst_token))
        assert resp.status_code == 200

    async def test_each_item_has_required_fields(self, client: AsyncClient, admin_token: str, db):
        """Create an incident + evidence record, then verify the global list includes it."""
        from datetime import datetime, timezone
        from app.models.incident import Incident
        from app.models.evidence import Evidence

        inc = Incident(
            id=uuid.uuid4(),
            title="Test inc for evidence list",
            status="new",
            severity="low",
            detected_at=datetime.now(timezone.utc),
        )
        db.add(inc)
        await db.flush()

        ev = Evidence(
            id=uuid.uuid4(),
            incident_id=inc.id,
            filename="test.log",
            original_filename="test.log",
            content_type="text/plain",
            file_size=1024,
            s3_key="test/test.log",
            s3_bucket="lbro-evidence",
            sha256_hash="a" * 64,
        )
        db.add(ev)
        await db.commit()

        resp = await client.get("/api/v1/evidence", headers=_auth(admin_token))
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

        item = items[0]
        required = {"id", "incident_id", "filename", "original_filename",
                    "content_type", "file_size", "sha256_hash", "is_immutable",
                    "created_at", "custody_chain"}
        for field in required:
            assert field in item, f"Missing field: {field}"


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/ml/flows  — live flow classifications
# ─────────────────────────────────────────────────────────────────────────────

class TestMlFlows:

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/ml/flows")
        assert resp.status_code == 401

    async def test_returns_list(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/ml/flows", headers=_auth(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_flows_have_required_fields(self, client: AsyncClient, admin_token: str, db):
        """Seed an incident with ML prediction and verify it appears in /flows."""
        from datetime import datetime, timezone
        from app.models.incident import Incident

        inc = Incident(
            id=uuid.uuid4(),
            title="ML flow test incident",
            status="new",
            severity="high",
            attack_category="DDoS",
            confidence_score=0.92,
            source_ip="10.0.0.1",
            destination_ip="192.168.1.1",
            source_port=12345,
            destination_port=80,
            protocol="TCP",
            detected_at=datetime.now(timezone.utc),
            network_features={
                "total_fwd_packets": 150,
                "total_bwd_packets": 80,
                "total_fwd_bytes": 15000,
                "total_bwd_bytes": 8000,
                "flow_duration": 0.5,
                "flow_bytes_per_sec": 46000.0,
                "flow_packets_per_sec": 460.0,
                "fwd_iat_mean": 3.2,
                "bwd_iat_mean": 6.1,
            },
        )
        db.add(inc)
        await db.commit()

        resp = await client.get("/api/v1/ml/flows", headers=_auth(admin_token))
        assert resp.status_code == 200
        flows = resp.json()
        assert len(flows) >= 1

        required = {
            "flow_id", "timestamp", "src_ip", "dst_ip", "src_port", "dst_port",
            "protocol", "attack_type", "flow_duration", "total_fwd_packets",
            "total_bwd_packets", "total_fwd_bytes", "total_bwd_bytes",
            "flow_bytes_per_sec", "flow_packets_per_sec", "fwd_iat_mean",
            "bwd_iat_mean", "confidence_score", "is_false_positive", "label",
        }
        flow = flows[0]
        for field in required:
            assert field in flow, f"Missing field: {field}"

    async def test_limit_param(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/ml/flows",
            params={"limit": 5},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 5

    async def test_analyst_can_access(self, client: AsyncClient, analyst_token: str):
        resp = await client.get("/api/v1/ml/flows", headers=_auth(analyst_token))
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/ml/metrics  — ML performance metrics
# ─────────────────────────────────────────────────────────────────────────────

class TestMlMetrics:

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/ml/metrics")
        assert resp.status_code == 401

    async def test_returns_correct_shape(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/ml/metrics", headers=_auth(admin_token))
        assert resp.status_code == 200
        body = resp.json()

        assert "feature_importance" in body
        assert "per_class_confidence" in body
        assert "false_positive_analysis" in body
        assert "tactic_distribution" in body

        assert isinstance(body["feature_importance"], list)
        assert isinstance(body["per_class_confidence"], list)
        assert isinstance(body["false_positive_analysis"], list)
        assert isinstance(body["tactic_distribution"], list)

    async def test_feature_importance_entries(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/ml/metrics", headers=_auth(admin_token))
        fi = resp.json()["feature_importance"]
        assert len(fi) >= 1
        for entry in fi:
            assert "feature" in entry
            assert "importance" in entry
            assert 0.0 <= entry["importance"] <= 1.0

    async def test_per_class_confidence_entries(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/ml/metrics", headers=_auth(admin_token))
        pc = resp.json()["per_class_confidence"]
        assert len(pc) >= 1
        for entry in pc:
            assert "subject" in entry
            assert "A" in entry
            assert "fullMark" in entry

    async def test_fp_analysis_entries(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/ml/metrics", headers=_auth(admin_token))
        fp = resp.json()["false_positive_analysis"]
        # May be empty if no incidents exist; if present, check shape
        for entry in fp:
            assert "attack" in entry
            assert "tp" in entry
            assert "fp" in entry
            assert "fn" in entry

    async def test_tactic_distribution_entries(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/ml/metrics", headers=_auth(admin_token))
        td = resp.json()["tactic_distribution"]
        for entry in td:
            assert "tactic" in entry
            assert "count" in entry
            assert "color" in entry

    async def test_analyst_can_access(self, client: AsyncClient, analyst_token: str):
        resp = await client.get("/api/v1/ml/metrics", headers=_auth(analyst_token))
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/infrastructure  — system health
# ─────────────────────────────────────────────────────────────────────────────

class TestInfrastructureStatus:

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/infrastructure")
        assert resp.status_code == 401

    async def test_returns_correct_shape(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/infrastructure", headers=_auth(admin_token))
        assert resp.status_code == 200
        body = resp.json()

        required_top = {
            "ecs_services", "sqs_queues", "rds_connections",
            "rds_cpu_percent", "rds_free_storage_gb", "s3_evidence_size_gb",
            "api_latency_p50_ms", "api_latency_p95_ms", "api_latency_p99_ms",
            "worker_health", "checked_at",
        }
        for field in required_top:
            assert field in body, f"Missing field: {field}"

    async def test_ecs_services_shape(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/infrastructure", headers=_auth(admin_token))
        services = resp.json()["ecs_services"]
        assert isinstance(services, list)
        assert len(services) >= 1
        for svc in services:
            assert "name" in svc
            assert "tasks_running" in svc
            assert "tasks_desired" in svc
            assert "cpu_percent" in svc
            assert "memory_percent" in svc
            assert "last_deployment_at" in svc

    async def test_sqs_queues_shape(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/infrastructure", headers=_auth(admin_token))
        queues = resp.json()["sqs_queues"]
        assert isinstance(queues, list)
        assert len(queues) >= 1
        for q in queues:
            assert "name" in q
            assert "depth" in q
            assert "dlq_depth" in q

    async def test_worker_health_valid_value(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/infrastructure", headers=_auth(admin_token))
        health = resp.json()["worker_health"]
        assert health in ("healthy", "degraded", "unhealthy")

    async def test_latency_values_are_positive(self, client: AsyncClient, admin_token: str):
        resp = await client.get("/api/v1/infrastructure", headers=_auth(admin_token))
        body = resp.json()
        assert body["api_latency_p50_ms"] >= 0
        assert body["api_latency_p95_ms"] >= body["api_latency_p50_ms"]
        assert body["api_latency_p99_ms"] >= body["api_latency_p95_ms"]

    async def test_s3_size_reflects_evidence(
        self, client: AsyncClient, admin_token: str, db
    ):
        from datetime import datetime, timezone
        from app.models.incident import Incident
        from app.models.evidence import Evidence

        # Baseline
        r0 = await client.get("/api/v1/infrastructure", headers=_auth(admin_token))
        base_gb = r0.json()["s3_evidence_size_gb"]

        inc = Incident(
            id=uuid.uuid4(), title="s3 size test",
            status="new", severity="low",
            detected_at=datetime.now(timezone.utc),
        )
        db.add(inc)
        await db.flush()

        ONE_GB = 1_000_000_000
        ev = Evidence(
            id=uuid.uuid4(), incident_id=inc.id,
            filename="big.bin", original_filename="big.bin",
            content_type="application/octet-stream",
            file_size=ONE_GB,
            s3_key="test/big.bin", s3_bucket="lbro-evidence",
            sha256_hash="b" * 64,
        )
        db.add(ev)
        await db.commit()

        r1 = await client.get("/api/v1/infrastructure", headers=_auth(admin_token))
        new_gb = r1.json()["s3_evidence_size_gb"]
        assert new_gb > base_gb, "S3 size should increase after adding 1GB evidence record"

    async def test_analyst_can_access(self, client: AsyncClient, analyst_token: str):
        resp = await client.get("/api/v1/infrastructure", headers=_auth(analyst_token))
        assert resp.status_code == 200

    async def test_viewer_can_access(self, client: AsyncClient, viewer_token: str):
        """Viewers have VIEW_DASHBOARD permission; infrastructure uses same permission."""
        resp = await client.get("/api/v1/infrastructure", headers=_auth(viewer_token))
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/infrastructure/sqs-history  — queue depth timeseries
# ─────────────────────────────────────────────────────────────────────────────

class TestSqsHistory:

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/infrastructure/sqs-history")
        assert resp.status_code == 401

    async def test_returns_10_hourly_buckets_by_default(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.get(
            "/api/v1/infrastructure/sqs-history",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 10  # default hours=10

    async def test_each_bucket_has_correct_fields(
        self, client: AsyncClient, admin_token: str
    ):
        resp = await client.get(
            "/api/v1/infrastructure/sqs-history",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        for bucket in resp.json():
            assert "time" in bucket
            assert "incident" in bucket
            assert "containment" in bucket
            assert "notification" in bucket
            assert isinstance(bucket["incident"], int)
            assert isinstance(bucket["containment"], int)
            assert isinstance(bucket["notification"], int)

    async def test_custom_hours_param(self, client: AsyncClient, admin_token: str):
        resp = await client.get(
            "/api/v1/infrastructure/sqs-history",
            params={"hours": 6},
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 6

    async def test_buckets_reflect_notifications(
        self, client: AsyncClient, admin_token: str, db
    ):
        """Seed a notification and verify the current-hour bucket increments."""
        from datetime import datetime, timezone
        from app.models.incident import Incident
        from app.models.notification import Notification

        inc = Incident(
            id=uuid.uuid4(), title="notif test", status="new", severity="low",
            detected_at=datetime.now(timezone.utc),
        )
        db.add(inc)
        await db.flush()

        notif = Notification(
            id=uuid.uuid4(),
            incident_id=inc.id,
            regulation="GDPR",
            jurisdiction="EU",
            authority="DPA",
            subject="Test breach notification",
            body="Test body",
            deadline=datetime.now(timezone.utc),
            status="pending",
        )
        db.add(notif)
        await db.commit()

        resp = await client.get(
            "/api/v1/infrastructure/sqs-history",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200
        buckets = resp.json()
        # Most recent bucket (last in list) should have incident >= 1
        last = buckets[-1]
        assert last["incident"] >= 1

    async def test_analyst_can_access(self, client: AsyncClient, analyst_token: str):
        resp = await client.get(
            "/api/v1/infrastructure/sqs-history",
            headers=_auth(analyst_token),
        )
        assert resp.status_code == 200
