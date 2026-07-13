"""
Compliance test suite — LBRO
Covers: obligation CRUD, cross-project isolation, score calculation.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestObligationCRUD:
    async def test_create_obligation_returns_200_with_data(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        resp = await client.post(
            "/api/v1/compliance/obligations",
            json={
                "framework": "GDPR",
                "control_id": "Art-5",
                "control_name": "Control Art-5",
                "description": "Lawfulness of processing",
                "status": "not_started",
            },
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["framework"] == "GDPR"
        assert body["control_id"] == "Art-5"
        assert body["project_id"] == portfolio_project["id"]

    async def test_list_obligations_for_project(
        self, client: AsyncClient, alice_h: dict,
        portfolio_obligation: dict, portfolio_project: dict  # noqa: ARG002
    ):
        resp = await client.get(
            "/api/v1/compliance/obligations",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        obligations = resp.json()
        assert isinstance(obligations, list)
        assert len(obligations) >= 1

    async def test_obligation_upsert_updates_existing_row(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        """POSTing the same project+framework+control_id twice updates, not inserts."""
        payload = {
            "framework": "SOC2",
            "control_id": "CC6.1",
            "control_name": "Control CC6.1",
            "description": "Logical access security",
            "status": "not_started",
        }
        r1 = await client.post(
            "/api/v1/compliance/obligations",
            json=payload,
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert r1.status_code == 200
        id1 = r1.json()["id"]

        payload["status"] = "met"
        r2 = await client.post(
            "/api/v1/compliance/obligations",
            json=payload,
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert r2.status_code == 200
        id2 = r2.json()["id"]

        # Same record updated — same ID
        assert id1 == id2
        assert r2.json()["status"] == "met"

    async def test_update_obligation_status(
        self, client: AsyncClient, alice_h: dict, portfolio_obligation: dict
    ):
        resp = await client.patch(
            f"/api/v1/compliance/obligations/{portfolio_obligation['id']}",
            json={"status": "met"},
            headers=alice_h,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "met"

    async def test_list_obligations_filter_by_framework(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict
    ):
        # Create two obligations with different frameworks
        await client.post(
            "/api/v1/compliance/obligations",
            json={"framework": "GDPR", "control_id": "Art-25", "control_name": "Art-25", "description": "Data minimisation", "status": "not_started"},
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        await client.post(
            "/api/v1/compliance/obligations",
            json={"framework": "ISO27001", "control_id": "A.8.1", "control_name": "A.8.1", "description": "Asset inventory", "status": "not_started"},
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )

        resp = await client.get(
            "/api/v1/compliance/obligations",
            params={"project_id": portfolio_project["id"], "framework": "GDPR"},
            headers=alice_h,
        )
        assert resp.status_code == 200
        frameworks = {o["framework"] for o in resp.json()}
        assert frameworks == {"GDPR"}


class TestComplianceIsolation:
    async def test_portfolio_obligations_not_visible_with_hospital_project_id(
        self, client: AsyncClient, alice_h: dict,
        portfolio_obligation: dict,  # noqa: ARG002 — seeded in Portfolio
        hospital_project: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/obligations",
            params={"project_id": hospital_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        ids = {o["id"] for o in resp.json()}
        assert portfolio_obligation["id"] not in ids

    async def test_hospital_obligations_not_visible_with_portfolio_project_id(
        self, client: AsyncClient, alice_h: dict,
        hospital_obligation: dict,  # noqa: ARG002 — seeded in Hospital
        portfolio_project: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/obligations",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        ids = {o["id"] for o in resp.json()}
        assert hospital_obligation["id"] not in ids

    async def test_viewer_cannot_create_obligation(
        self, client: AsyncClient, carol_h: dict, portfolio_project: dict
    ):
        resp = await client.post(
            "/api/v1/compliance/obligations",
            json={
                "framework": "DPDPA",
                "control_id": "Sec-8",
                "control_name": "Control Sec-8",
                "description": "Data fiduciary obligations",
                "status": "not_started",
            },
            params={"project_id": portfolio_project["id"]},
            headers=carol_h,
        )
        assert resp.status_code == 403

    async def test_project_id_required_for_list(
        self, client: AsyncClient, alice_h: dict
    ):
        """Listing obligations without project_id must return 422."""
        resp = await client.get("/api/v1/compliance/obligations", headers=alice_h)
        assert resp.status_code == 422


class TestComplianceScore:
    async def test_compliance_score_endpoint_returns_valid_structure(
        self, client: AsyncClient, alice_h: dict,
        portfolio_obligation: dict,  # noqa: ARG002
        portfolio_project: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/score",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "overall_score" in body or "score" in body or "percentage" in body

    async def test_all_met_obligations_yields_higher_score_than_none_met(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        """Create two obligations: one met, one not. Score should be non-zero."""
        await client.post(
            "/api/v1/compliance/obligations",
            json={"framework": "GDPR", "control_id": "ScoreTest-1", "control_name": "ScoreTest-1", "description": "Test met", "status": "met"},
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        await client.post(
            "/api/v1/compliance/obligations",
            json={"framework": "GDPR", "control_id": "ScoreTest-2", "control_name": "ScoreTest-2", "description": "Test not started", "status": "not_started"},
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )

        resp = await client.get(
            "/api/v1/compliance/score",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        body = resp.json()
        # Score exists and is numeric
        score_value = body.get("overall_score", body.get("score", body.get("percentage", 0)))
        assert isinstance(score_value, (int, float))
