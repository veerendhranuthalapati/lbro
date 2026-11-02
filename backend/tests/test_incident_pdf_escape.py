"""Incident PDF must escape HTML-like incident text."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_incident_pdf_escapes_title_markup(client: AsyncClient, auth_headers: dict):
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "PDF Escape", "environment": "development"},
        headers=auth_headers,
    )
    assert proj.status_code == 201
    pid = proj.json()["id"]

    inc = await client.post(
        "/api/v1/incidents",
        json={
            "title": "<script>alert(1)</script> & ampersand",
            "severity": "medium",
            "project_id": pid,
        },
        headers=auth_headers,
    )
    assert inc.status_code == 201
    iid = inc.json()["id"]

    resp = await client.get(f"/api/v1/incidents/{iid}/report", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/pdf")
    body = resp.content
    assert body[:4] == b"%PDF"
    assert b"<script>alert(1)</script>" not in body
