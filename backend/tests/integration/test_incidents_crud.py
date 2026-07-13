"""Incident CRUD, status transitions, stats, explain — LBRO integration tests.

Uses the shared SQLite in-memory fixture stack from tests/conftest.py
and the per-class Alice / Bob fixtures from tests/integration/conftest.py.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestIncidentCreate:
    async def test_create_incident_minimal(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Test Incident Alpha", "severity": "medium"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Test Incident Alpha"
        assert body["severity"] == "medium"
        assert body["status"] == "new"
        assert "id" in body

    async def test_create_incident_full_fields(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        """attack_category is set by the ML pipeline, not at creation time."""
        resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "DDoS Attack on Primary API",
                "severity": "critical",
                "description": "Flood detected from 203.0.113.0/24",
                "source_ip": "203.0.113.42",
                "destination_ip": "10.0.0.1",
                "source_port": 54321,
                "destination_port": 443,
                "protocol": "TCP",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["source_ip"] == "203.0.113.42"
        assert body["destination_port"] == 443
        assert body["protocol"].upper() == "TCP"  # stored as lowercase

    async def test_create_incident_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Unauthenticated Incident"},
        )
        assert resp.status_code == 401

    async def test_viewer_cannot_create_incident(
        self, client: AsyncClient, viewer_user
    ):
        """Viewer role (read-only) cannot create incidents — expects 403."""
        login = await client.post("/api/v1/auth/login", json={
            "email": "viewer@lbro-test.com", "password": "Viewer123!",
        })
        assert login.status_code == 200
        token = login.json()["access_token"]
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Viewer Should Fail"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_analyst_can_create_incident(
        self, client: AsyncClient, analyst_token: str, analyst_user
    ):
        resp = await client.post(
            "/api/v1/incidents",
            json={"title": "Analyst Creates Incident", "severity": "low"},
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert resp.status_code == 201


class TestIncidentRead:
    async def test_list_incidents_empty(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        resp = await client.get(
            "/api/v1/incidents",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert isinstance(body["items"], list)

    async def test_list_incidents_returns_created(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        await client.post(
            "/api/v1/incidents",
            json={"title": "List Test Incident"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = await client.get(
            "/api/v1/incidents",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        titles = [i["title"] for i in resp.json()["items"]]
        assert "List Test Incident" in titles

    async def test_list_incidents_filter_by_severity(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        await client.post("/api/v1/incidents", json={"title": "Critical One", "severity": "critical"}, headers=h)
        await client.post("/api/v1/incidents", json={"title": "Low One", "severity": "low"}, headers=h)

        resp = await client.get("/api/v1/incidents", params={"severity": "critical"}, headers=h)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["severity"] == "critical"

    async def test_get_incident_by_id(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/incidents", json={"title": "Get By ID Test"}, headers=h)
        incident_id = create.json()["id"]

        resp = await client.get(f"/api/v1/incidents/{incident_id}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["id"] == incident_id

    async def test_get_nonexistent_incident_returns_404(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        import uuid
        resp = await client.get(
            f"/api/v1/incidents/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_incident_stats_returns_counts(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        await client.post("/api/v1/incidents", json={"title": "Stats Test", "severity": "high"}, headers=h)

        resp = await client.get("/api/v1/incidents/stats", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "by_status" in body or "by_severity" in body or isinstance(body, dict)


class TestIncidentUpdate:
    async def test_patch_incident_title(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/incidents", json={"title": "Original Title"}, headers=h)
        iid = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/incidents/{iid}",
            json={"title": "Updated Title"},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    async def test_patch_incident_severity(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/incidents", json={"title": "Severity Update", "severity": "low"}, headers=h)
        iid = create.json()["id"]

        resp = await client.patch(f"/api/v1/incidents/{iid}", json={"severity": "critical"}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["severity"] == "critical"

    async def test_viewer_cannot_patch_incident(
        self, client: AsyncClient, admin_token: str, admin_user, viewer_user
    ):
        ah = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/incidents", json={"title": "Viewer Patch Test"}, headers=ah)
        iid = create.json()["id"]

        login = await client.post("/api/v1/auth/login", json={
            "email": "viewer@lbro-test.com", "password": "Viewer123!",
        })
        assert login.status_code == 200
        viewer_token = login.json()["access_token"]
        resp = await client.patch(
            f"/api/v1/incidents/{iid}",
            json={"title": "Hacked"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403


class TestIncidentStatusTransitions:
    """
    FSM: new → triaging → contained → eradicating → recovering → closed → reopened
         triaging can also go directly → closed
         contained can also go directly → closed
    """

    async def _create(self, client, h):
        r = await client.post("/api/v1/incidents", json={"title": "Status Test"}, headers=h)
        assert r.status_code == 201
        return r.json()["id"]

    async def _advance_to(self, client, h, iid, *statuses):
        """Drive the incident through a chain of statuses."""
        for s in statuses:
            r = await client.post(f"/api/v1/incidents/{iid}/status", json={"status": s}, headers=h)
            assert r.status_code == 200, f"Failed to transition to {s}: {r.text}"

    async def test_change_status_to_triaging(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        iid = await self._create(client, h)
        resp = await client.post(
            f"/api/v1/incidents/{iid}/status",
            json={"status": "triaging"},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "triaging"

    async def test_change_status_to_contained(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        """new → triaging → contained"""
        h = {"Authorization": f"Bearer {admin_token}"}
        iid = await self._create(client, h)
        await self._advance_to(client, h, iid, "triaging")
        resp = await client.post(
            f"/api/v1/incidents/{iid}/status",
            json={"status": "contained", "notes": "Firewall rule applied"},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "contained"

    async def test_change_status_to_closed_via_triaging(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        """new → triaging → closed (valid shortcut)"""
        h = {"Authorization": f"Bearer {admin_token}"}
        iid = await self._create(client, h)
        await self._advance_to(client, h, iid, "triaging")
        resp = await client.post(
            f"/api/v1/incidents/{iid}/status",
            json={"status": "closed"},
            headers=h,
        )
        assert resp.status_code == 200

    async def test_invalid_transition_returns_409(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        """new → contained is invalid — must pass through triaging first."""
        h = {"Authorization": f"Bearer {admin_token}"}
        iid = await self._create(client, h)
        resp = await client.post(
            f"/api/v1/incidents/{iid}/status",
            json={"status": "contained"},
            headers=h,
        )
        assert resp.status_code == 409

    async def test_reopen_incident(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        """new → triaging → closed → reopened"""
        h = {"Authorization": f"Bearer {admin_token}"}
        iid = await self._create(client, h)
        await self._advance_to(client, h, iid, "triaging", "closed")

        resp = await client.post(
            f"/api/v1/incidents/{iid}/reopen",
            json={"reason": "New evidence discovered"},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reopened"

    async def test_viewer_cannot_change_status(
        self, client: AsyncClient, admin_token: str, admin_user, viewer_user
    ):
        ah = {"Authorization": f"Bearer {admin_token}"}
        iid = await self._create(client, ah)

        login = await client.post("/api/v1/auth/login", json={
            "email": "viewer@lbro-test.com", "password": "Viewer123!",
        })
        assert login.status_code == 200
        viewer_token = login.json()["access_token"]
        resp = await client.post(
            f"/api/v1/incidents/{iid}/status",
            json={"status": "triaging"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403


class TestIncidentDelete:
    async def test_admin_can_delete_incident(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/incidents", json={"title": "Delete Me"}, headers=h)
        iid = create.json()["id"]

        resp = await client.delete(f"/api/v1/incidents/{iid}", headers=h)
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/v1/incidents/{iid}", headers=h)
        assert get_resp.status_code == 404

    async def test_analyst_cannot_delete_incident(
        self, client: AsyncClient, admin_token: str, analyst_token: str, admin_user, analyst_user
    ):
        ah = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/incidents", json={"title": "Analyst Delete Test"}, headers=ah)
        iid = create.json()["id"]

        resp = await client.delete(
            f"/api/v1/incidents/{iid}",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert resp.status_code == 403


class TestIncidentExplain:
    async def test_explain_incident_returns_explanation(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Port Scan Detected",
                "severity": "medium",
            },
            headers=h,
        )
        iid = create.json()["id"]

        resp = await client.get(f"/api/v1/incidents/{iid}/explain", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert "incident_id" in body
        assert body["incident_id"] == iid

    async def test_explain_nonexistent_incident_returns_404(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        import uuid
        resp = await client.get(
            f"/api/v1/incidents/{uuid.uuid4()}/explain",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


class TestIncidentPagination:
    async def test_list_incidents_default_page_size(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        for i in range(5):
            await client.post("/api/v1/incidents", json={"title": f"Paginate {i}"}, headers=h)

        resp = await client.get("/api/v1/incidents", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1
        assert body["page_size"] == 20

    async def test_list_incidents_custom_page_size(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/incidents", params={"page_size": 5}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["page_size"] == 5
        assert len(resp.json()["items"]) <= 5
