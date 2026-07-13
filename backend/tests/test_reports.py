"""Weekly security report endpoint tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


# ── JSON report ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_weekly_report_json_structure(client: AsyncClient, auth_headers: dict):
    """GET /reports/weekly returns JSON with expected keys."""
    resp = await client.get("/api/v1/reports/weekly", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "security_score" in data
    assert "security_grade" in data
    assert "executive_summary" in data
    assert "incidents" in data
    assert "evidence_count" in data
    assert "compliance_met" in data
    assert "top_recommendations" in data
    assert "trend" in data
    assert isinstance(data["security_score"], int)
    assert 0 <= data["security_score"] <= 100


@pytest.mark.asyncio
async def test_weekly_report_default_days(client: AsyncClient, auth_headers: dict):
    """Without ?days param, defaults to 7 days — period_start exists."""
    resp = await client.get("/api/v1/reports/weekly", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "period_start" in data
    assert "period_end" in data
    assert "generated_at" in data


@pytest.mark.asyncio
async def test_weekly_report_custom_days(client: AsyncClient, auth_headers: dict):
    """?days=30 is accepted and returns the same report structure."""
    resp = await client.get("/api/v1/reports/weekly?days=30", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "security_score" in data


@pytest.mark.asyncio
async def test_weekly_report_max_days_boundary(client: AsyncClient, auth_headers: dict):
    """?days=365 is the maximum allowed — must succeed."""
    resp = await client.get("/api/v1/reports/weekly?days=365", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_weekly_report_days_out_of_range_422(client: AsyncClient, auth_headers: dict):
    """?days=400 exceeds the max of 365 — returns 422."""
    resp = await client.get("/api/v1/reports/weekly?days=400", headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_weekly_report_days_zero_422(client: AsyncClient, auth_headers: dict):
    """?days=0 is below the minimum of 1 — returns 422."""
    resp = await client.get("/api/v1/reports/weekly?days=0", headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_weekly_report_requires_auth(client: AsyncClient):
    """Unauthenticated request returns 401."""
    resp = await client.get("/api/v1/reports/weekly")
    assert resp.status_code == 401


# ── PDF report ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_weekly_report_pdf_content_type(client: AsyncClient, auth_headers: dict):
    """GET /reports/weekly/pdf returns application/pdf."""
    resp = await client.get("/api/v1/reports/weekly/pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_weekly_report_pdf_has_bytes(client: AsyncClient, auth_headers: dict):
    """PDF response body must be non-empty — reportlab must have run."""
    resp = await client.get("/api/v1/reports/weekly/pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.content) > 200  # any real PDF is several hundred bytes


@pytest.mark.asyncio
async def test_weekly_report_pdf_with_days_param(client: AsyncClient, auth_headers: dict):
    """?days=14 is accepted for the PDF endpoint too."""
    resp = await client.get("/api/v1/reports/weekly/pdf?days=14", headers=auth_headers)
    assert resp.status_code == 200
    assert "pdf" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_weekly_report_pdf_requires_auth(client: AsyncClient):
    """PDF endpoint also requires authentication."""
    resp = await client.get("/api/v1/reports/weekly/pdf")
    assert resp.status_code == 401


# ── Compliance PDF ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compliance_pdf_content_type(client: AsyncClient, auth_headers: dict):
    """GET /reports/compliance/pdf returns application/pdf."""
    resp = await client.get("/api/v1/reports/compliance/pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_compliance_pdf_has_bytes(client: AsyncClient, auth_headers: dict):
    """Compliance PDF is non-empty."""
    resp = await client.get("/api/v1/reports/compliance/pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.content) > 200
