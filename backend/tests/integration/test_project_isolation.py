"""
Project & incident isolation tests — LBRO

Covers:
  - Project list filtered by ownership (analyst sees only own; admin sees all)
  - Incident list filtered by project_id
  - IDOR gap: GET /incidents/{id} without project_id (documented known gap)
  - Cross-project evidence access
  - Project API key regeneration ownership enforcement
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestProjectListIsolation:
    async def test_admin_alice_sees_all_three_projects(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict, ecommerce_project: dict, hospital_project: dict
    ):
        resp = await client.get("/api/v1/projects", headers=alice_h)
        assert resp.status_code == 200
        ids = {p["id"] for p in resp.json()["items"]}
        assert portfolio_project["id"] in ids
        assert ecommerce_project["id"] in ids
        assert hospital_project["id"] in ids

    async def test_analyst_bob_sees_only_own_project(
        self, client: AsyncClient, bob_h: dict,
        portfolio_project: dict, ecommerce_project: dict, hospital_project: dict
    ):
        """Analyst (non-admin) only sees projects he owns."""
        resp = await client.get("/api/v1/projects", headers=bob_h)
        assert resp.status_code == 200
        ids = {p["id"] for p in resp.json()["items"]}
        # Bob owns Hospital
        assert hospital_project["id"] in ids
        # Bob does NOT own Portfolio or Ecommerce
        assert portfolio_project["id"] not in ids
        assert ecommerce_project["id"] not in ids

    async def test_viewer_carol_sees_no_projects(
        self, client: AsyncClient, carol_h: dict,
        portfolio_project: dict, hospital_project: dict  # noqa: ARG002 — create them
    ):
        """Viewer (non-admin, non-owner) sees only projects she owns — none."""
        resp = await client.get("/api/v1/projects", headers=carol_h)
        assert resp.status_code == 200
        assert resp.json()["items"] == []


class TestIncidentIsolation:
    async def test_list_incidents_with_portfolio_project_id_returns_only_portfolio_incidents(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict,
        sql_injection_incident: dict, port_scan_incident: dict, xss_incident: dict
    ):
        resp = await client.get(
            "/api/v1/incidents",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        body = resp.json()
        ids = {i["id"] for i in body["items"]}

        assert sql_injection_incident["id"] in ids
        assert port_scan_incident["id"] in ids
        # XSS belongs to Hospital — must NOT appear
        assert xss_incident["id"] not in ids

    async def test_list_incidents_with_hospital_project_id_returns_only_hospital_incidents(
        self, client: AsyncClient, bob_h: dict,
        hospital_project: dict,
        sql_injection_incident: dict, xss_incident: dict, malware_incident: dict
    ):
        resp = await client.get(
            "/api/v1/incidents",
            params={"project_id": hospital_project["id"]},
            headers=bob_h,
        )
        assert resp.status_code == 200
        ids = {i["id"] for i in resp.json()["items"]}

        assert xss_incident["id"] in ids
        assert malware_incident["id"] in ids
        # Portfolio incident must NOT appear
        assert sql_injection_incident["id"] not in ids

    async def test_get_incident_with_correct_project_id_succeeds(
        self, client: AsyncClient, alice_h: dict,
        portfolio_project: dict, sql_injection_incident: dict
    ):
        resp = await client.get(
            f"/api/v1/incidents/{sql_injection_incident['id']}",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == sql_injection_incident["id"]

    async def test_get_incident_with_wrong_project_id_returns_404(
        self, client: AsyncClient, alice_h: dict,
        hospital_project: dict, sql_injection_incident: dict
    ):
        """Passing Hospital's project_id while accessing Portfolio incident → 404."""
        resp = await client.get(
            f"/api/v1/incidents/{sql_injection_incident['id']}",
            params={"project_id": hospital_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 404

    async def test_get_incident_without_project_id_is_accessible(
        self, client: AsyncClient, alice_h: dict, xss_incident: dict
    ):
        """
        KNOWN ISOLATION GAP: GET /incidents/{id} without project_id
        returns any incident regardless of project ownership.

        This test documents the current behavior.
        A future fix should return 422 when project_id is missing,
        or apply ownership/role-based filtering.
        """
        resp = await client.get(
            f"/api/v1/incidents/{xss_incident['id']}",
            headers=alice_h,
        )
        # Documents that the incident is reachable without project_id
        assert resp.status_code == 200

    async def test_bob_cannot_filter_alices_incidents_by_hospital_project(
        self, client: AsyncClient, bob_h: dict,
        hospital_project: dict, sql_injection_incident: dict
    ):
        """Bob filtering by Hospital project cannot see Alice's Portfolio incident."""
        resp = await client.get(
            "/api/v1/incidents",
            params={"project_id": hospital_project["id"]},
            headers=bob_h,
        )
        assert resp.status_code == 200
        ids = {i["id"] for i in resp.json()["items"]}
        assert sql_injection_incident["id"] not in ids


class TestProjectOwnership:
    async def test_alice_admin_can_regenerate_any_project_key(
        self, client: AsyncClient, alice_h: dict, hospital_project: dict
    ):
        """Admin can regenerate API key even for a project she doesn't own."""
        resp = await client.post(
            f"/api/v1/projects/{hospital_project['id']}/regenerate-key",
            headers=alice_h,
        )
        assert resp.status_code == 200

    async def test_bob_analyst_cannot_regenerate_alices_project_key(
        self, client: AsyncClient, bob_h: dict, portfolio_project: dict
    ):
        """Non-owner, non-admin cannot regenerate another user's project key."""
        resp = await client.post(
            f"/api/v1/projects/{portfolio_project['id']}/regenerate-key",
            headers=bob_h,
        )
        assert resp.status_code == 403

    async def test_bob_can_regenerate_own_project_key(
        self, client: AsyncClient, bob_h: dict, hospital_project: dict
    ):
        """Project owner can always regenerate their own key."""
        resp = await client.post(
            f"/api/v1/projects/{hospital_project['id']}/regenerate-key",
            headers=bob_h,
        )
        assert resp.status_code == 200

    async def test_get_project_by_id_accessible_to_any_authenticated_user(
        self, client: AsyncClient, bob_h: dict, portfolio_project: dict
    ):
        """
        KNOWN ISOLATION GAP: GET /projects/{id} has no ownership check.
        Any authenticated user can read any project by ID.

        This test documents the current behavior. A future fix should enforce
        that non-admins can only GET projects they own.
        """
        resp = await client.get(
            f"/api/v1/projects/{portfolio_project['id']}",
            headers=bob_h,  # Bob doesn't own Portfolio
        )
        # Documents the gap — returns 200 instead of 403
        assert resp.status_code == 200


class TestEvidenceIsolation:
    async def test_evidence_download_with_correct_project_id_succeeds(
        self, client: AsyncClient, alice_h: dict,
        portfolio_evidence: dict, portfolio_project: dict
    ):
        resp = await client.get(
            f"/api/v1/evidence/{portfolio_evidence['id']}/download",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code in (200, 302)

    async def test_evidence_download_with_wrong_project_id_returns_403_or_404(
        self, client: AsyncClient, alice_h: dict,
        portfolio_evidence: dict, hospital_project: dict
    ):
        """Passing Hospital project_id to access Portfolio evidence → rejected."""
        resp = await client.get(
            f"/api/v1/evidence/{portfolio_evidence['id']}/download",
            params={"project_id": hospital_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code in (403, 404)

    async def test_evidence_list_scoped_to_project(
        self, client: AsyncClient, alice_h: dict,
        portfolio_evidence: dict, hospital_evidence: dict,
        portfolio_project: dict
    ):
        resp = await client.get(
            "/api/v1/evidence",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        ids = {e["id"] for e in resp.json().get("items", [])}
        assert portfolio_evidence["id"] in ids
        assert hospital_evidence["id"] not in ids
