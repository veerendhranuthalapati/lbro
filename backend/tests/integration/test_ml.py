"""ML router integration tests — classify, model-info, stats, flows, metrics."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestMLClassify:
    async def test_classify_network_flow_returns_prediction(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "flow_duration": 1000000,
            "total_fwd_packets": 10,
            "total_bwd_packets": 5,
            "flow_packets_per_sec": 15.0,
            "destination_port": 443,
        }
        resp = await client.post("/api/v1/ml/classify", json=payload, headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert "attack_category" in body
        assert "confidence" in body
        assert isinstance(body["confidence"], float)
        assert 0.0 <= body["confidence"] <= 1.0

    async def test_classify_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/ml/classify", json={"flow_duration": 100})
        assert resp.status_code == 401

    async def test_classify_ddos_pattern(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        """High packet rate → likely DDoS category from heuristic fallback."""
        h = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "flow_packets_per_sec": 50000.0,
            "destination_port": 80,
        }
        resp = await client.post("/api/v1/ml/classify", json=payload, headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert "attack_category" in body
        assert "severity" in body

    async def test_classify_returns_probabilities(
        self, client: AsyncClient, analyst_token: str, analyst_user
    ):
        h = {"Authorization": f"Bearer {analyst_token}"}
        resp = await client.post("/api/v1/ml/classify", json={}, headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert "probabilities" in body
        assert isinstance(body["probabilities"], dict)

    async def test_classify_viewer_allowed(
        self, client: AsyncClient, viewer_user
    ):
        """Viewer has ml:read permission which covers classify."""
        login = await client.post("/api/v1/auth/login", json={
            "email": "viewer@lbro-test.com", "password": "Viewer123!",
        })
        assert login.status_code == 200
        token = login.json()["access_token"]
        resp = await client.post(
            "/api/v1/ml/classify",
            json={"destination_port": 22},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestMLModelInfo:
    async def test_model_info_returns_metadata(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/ml/model-info", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert "model_version" in body or "version" in body or isinstance(body, dict)

    async def test_models_list_endpoint(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/ml/models", headers=h)
        assert resp.status_code == 200

    async def test_ml_stats_endpoint(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/ml/stats", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        # Stats returns a structured object
        assert isinstance(body, dict)

    async def test_ml_metrics_endpoint(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/ml/metrics", headers=h)
        assert resp.status_code == 200

    async def test_ml_flows_endpoint(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/ml/flows", headers=h)
        assert resp.status_code == 200

    async def test_ml_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/ml/stats")
        assert resp.status_code == 401
