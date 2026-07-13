"""Reports and dashboard router integration tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestWeeklyReport:
    async def test_weekly_json_report_succeeds(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/reports/weekly", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        # Report is a dict with period and summary data
        assert isinstance(body, dict)

    async def test_weekly_report_with_days_param(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/reports/weekly", params={"days": 30}, headers=h)
        assert resp.status_code == 200

    async def test_weekly_report_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/reports/weekly")
        assert resp.status_code == 401

    async def test_weekly_pdf_report_returns_pdf(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/reports/weekly/pdf", headers=h)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) > 0

    async def test_weekly_report_with_project_id(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        resp = await client.get(
            "/api/v1/reports/weekly",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200

    async def test_viewer_can_view_reports(
        self, client: AsyncClient, viewer_user
    ):
        """Viewer has report:view permission."""
        login = await client.post("/api/v1/auth/login", json={
            "email": "viewer@lbro-test.com", "password": "Viewer123!",
        })
        assert login.status_code == 200
        token = login.json()["access_token"]
        resp = await client.get(
            "/api/v1/reports/weekly",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_compliance_pdf_report(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/reports/compliance/pdf", headers=h)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"


class TestDashboard:
    async def test_dashboard_summary_returns_data(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/dashboard/summary", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)

    async def test_dashboard_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 401

    async def test_dashboard_viewer_can_read(
        self, client: AsyncClient, viewer_user
    ):
        login = await client.post("/api/v1/auth/login", json={
            "email": "viewer@lbro-test.com", "password": "Viewer123!",
        })
        assert login.status_code == 200
        token = login.json()["access_token"]
        resp = await client.get(
            "/api/v1/dashboard/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_dashboard_with_incident_data(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        # Create some incidents so the dashboard has data
        await client.post("/api/v1/incidents", json={"title": "Dashboard Test", "severity": "high"}, headers=h)
        resp = await client.get("/api/v1/dashboard/summary", headers=h)
        assert resp.status_code == 200
