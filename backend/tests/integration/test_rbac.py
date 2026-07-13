"""
RBAC test suite — LBRO
Verifies that each role can and cannot access the correct endpoints.

Role matrix (from rbac.py):
  viewer  — READ_INCIDENT, DOWNLOAD_EVIDENCE, VIEW_DASHBOARD, READ_NOTIFICATION,
             VIEW_COMPLIANCE, VIEW_REPORT, VIEW_ML
  analyst — everything viewer + CREATE_INCIDENT, UPDATE_INCIDENT, UPLOAD_EVIDENCE,
             MANAGE_COMPLIANCE, GENERATE_REPORT, VIEW_AUDIT, VIEW_INFRASTRUCTURE, ...
  admin   — all permissions
"""
from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


class TestViewerPermissions:
    """Viewer role — read-only access."""

    async def test_viewer_can_list_incidents(
        self, client: AsyncClient, carol_h: dict, sql_injection_incident: dict  # noqa: ARG002
    ):
        resp = await client.get("/api/v1/incidents", headers=carol_h)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_viewer_can_get_single_incident(
        self, client: AsyncClient, carol_h: dict, sql_injection_incident: dict
    ):
        resp = await client.get(
            f"/api/v1/incidents/{sql_injection_incident['id']}",
            headers=carol_h,
        )
        assert resp.status_code == 200

    async def test_viewer_cannot_create_incident(
        self, client: AsyncClient, carol_h: dict, portfolio_project: dict
    ):
        resp = await client.post("/api/v1/incidents", json={
            "title": "Viewer Attempt to Create Incident",
            "severity": "low",
            "project_id": portfolio_project["id"],
        }, headers=carol_h)
        assert resp.status_code == 403

    async def test_viewer_cannot_update_incident(
        self, client: AsyncClient, carol_h: dict, sql_injection_incident: dict
    ):
        resp = await client.patch(
            f"/api/v1/incidents/{sql_injection_incident['id']}",
            json={"severity": "low"},
            headers=carol_h,
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_delete_incident(
        self, client: AsyncClient, carol_h: dict, sql_injection_incident: dict
    ):
        resp = await client.delete(
            f"/api/v1/incidents/{sql_injection_incident['id']}",
            headers=carol_h,
        )
        assert resp.status_code == 403

    async def test_viewer_can_download_evidence(
        self, client: AsyncClient, carol_h: dict,
        portfolio_evidence: dict, portfolio_project: dict
    ):
        resp = await client.get(
            f"/api/v1/evidence/{portfolio_evidence['id']}/download",
            params={"project_id": portfolio_project["id"]},
            headers=carol_h,
        )
        # 200 OK or 302 redirect — both indicate access was granted
        assert resp.status_code in (200, 302)

    async def test_viewer_cannot_upload_evidence(
        self, client: AsyncClient, carol_h: dict, sql_injection_incident: dict
    ):
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("test.txt", io.BytesIO(b"data"), "text/plain")},
            headers=carol_h,
        )
        assert resp.status_code == 403

    async def test_viewer_can_view_compliance(
        self, client: AsyncClient, carol_h: dict,
        portfolio_obligation: dict, portfolio_project: dict  # noqa: ARG002
    ):
        resp = await client.get(
            "/api/v1/compliance/obligations",
            params={"project_id": portfolio_project["id"]},
            headers=carol_h,
        )
        assert resp.status_code == 200

    async def test_viewer_cannot_manage_compliance(
        self, client: AsyncClient, carol_h: dict, portfolio_project: dict
    ):
        resp = await client.post(
            "/api/v1/compliance/obligations",
            json={
                "framework": "ISO27001",
                "control_id": "A.9.1",
                "control_name": "Control A.9.1",
                "description": "Access control policy",
                "status": "not_started",
            },
            params={"project_id": portfolio_project["id"]},
            headers=carol_h,
        )
        assert resp.status_code == 403

    async def test_viewer_can_list_projects(
        self, client: AsyncClient, carol_h: dict,
        portfolio_project: dict  # noqa: ARG002
    ):
        resp = await client.get("/api/v1/projects", headers=carol_h)
        assert resp.status_code == 200


class TestAnalystPermissions:
    """Analyst role — read + write, no admin operations."""

    async def test_analyst_can_create_incident(
        self, client: AsyncClient, bob_h: dict, hospital_project: dict
    ):
        resp = await client.post("/api/v1/incidents", json={
            "title": "Analyst Creates Incident Test",
            "severity": "medium",
            "project_id": hospital_project["id"],
        }, headers=bob_h)
        assert resp.status_code == 201

    async def test_analyst_can_upload_evidence(
        self, client: AsyncClient, bob_h: dict, xss_incident: dict
    ):
        resp = await client.post(
            f"/api/v1/incidents/{xss_incident['id']}/evidence",
            files={"file": ("analyst_log.txt", io.BytesIO(b"analyst evidence data"), "text/plain")},
            data={"description": "Analyst uploaded evidence"},
            headers=bob_h,
        )
        assert resp.status_code == 201

    async def test_analyst_can_manage_compliance(
        self, client: AsyncClient, bob_h: dict, hospital_project: dict
    ):
        resp = await client.post(
            "/api/v1/compliance/obligations",
            json={
                "framework": "HIPAA",
                "control_id": "164.308(a)(5)",
                "control_name": "Control 164.308(a)(5)",
                "description": "Security awareness training",
                "status": "not_started",
            },
            params={"project_id": hospital_project["id"]},
            headers=bob_h,
        )
        assert resp.status_code == 200

    async def test_analyst_cannot_manage_users(
        self, client: AsyncClient, bob_h: dict
    ):
        resp = await client.get("/api/v1/users", headers=bob_h)
        assert resp.status_code == 403

    async def test_analyst_can_rotate_own_api_key(
        self, client: AsyncClient, bob_h: dict
    ):
        """Any authenticated user can rotate their OWN api key — no permission guard."""
        resp = await client.post("/api/v1/auth/api-key/rotate", headers=bob_h)
        assert resp.status_code == 200

    async def test_analyst_can_view_audit_log(
        self, client: AsyncClient, bob_h: dict
    ):
        resp = await client.get("/api/v1/audit/logs", headers=bob_h)
        assert resp.status_code == 200


class TestAdminPermissions:
    """Admin role — unrestricted access to all endpoints."""

    async def test_admin_can_manage_users(
        self, client: AsyncClient, alice_h: dict
    ):
        resp = await client.get("/api/v1/users", headers=alice_h)
        assert resp.status_code == 200

    async def test_admin_can_rotate_api_key(
        self, client: AsyncClient, alice_h: dict
    ):
        resp = await client.post("/api/v1/auth/api-key/rotate", headers=alice_h)
        assert resp.status_code == 200

    async def test_admin_can_delete_incident(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        resp = await client.delete(
            f"/api/v1/incidents/{sql_injection_incident['id']}",
            headers=alice_h,
        )
        assert resp.status_code in (200, 204)

    async def test_admin_can_view_all_reports(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        resp = await client.get(
            "/api/v1/reports/weekly",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200


class TestUnauthenticated:
    """No credentials — every protected endpoint must return 401."""

    async def test_unauthenticated_cannot_list_incidents(self, client: AsyncClient):
        resp = await client.get("/api/v1/incidents")
        assert resp.status_code == 401

    async def test_unauthenticated_cannot_get_me(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_unauthenticated_cannot_list_projects(self, client: AsyncClient):
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 401

    async def test_unauthenticated_cannot_list_compliance(
        self, client: AsyncClient, portfolio_project: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/obligations",
            params={"project_id": portfolio_project["id"]},
        )
        assert resp.status_code == 401
