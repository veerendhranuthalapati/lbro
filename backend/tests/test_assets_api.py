"""Asset API and RBAC tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.test_compliance import _create_project


@pytest.mark.asyncio
async def test_asset_crud_and_idor(client: AsyncClient, analyst_headers: dict, viewer_headers: dict):
    project_id = await _create_project(client, analyst_headers, "Asset Map Project")
    other_id = await _create_project(client, analyst_headers, "Other Asset Project")

    create = await client.post(
        "/api/v1/assets",
        params={"project_id": project_id},
        json={
            "name": "Demo Customer DB",
            "asset_type": "database",
            "classification": "confidential",
            "data_categories": ["personal_identifiers"],
            "identifiers": [{"type": "hostname", "value": "db.demo.local"}],
            "residency": [
                {"jurisdiction_code": "EU", "record_count": 100, "count_basis": "exact"}
            ],
        },
        headers=analyst_headers,
    )
    assert create.status_code == 201, create.text
    asset_id = create.json()["id"]

    list_resp = await client.get(
        "/api/v1/assets",
        params={"project_id": project_id},
        headers=analyst_headers,
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    cross = await client.get(
        f"/api/v1/assets/{asset_id}",
        params={"project_id": other_id},
        headers=analyst_headers,
    )
    assert cross.status_code == 404


@pytest.mark.asyncio
async def test_csv_export_formula_escape(client: AsyncClient, analyst_headers: dict):
    project_id = await _create_project(client, analyst_headers, "CSV Export Project")
    await client.post(
        "/api/v1/assets",
        params={"project_id": project_id},
        json={
            "name": "=cmd|'/c calc'!A0",
            "asset_type": "other",
            "classification": "internal",
            "data_categories": [],
            "identifiers": [],
        },
        headers=analyst_headers,
    )
    resp = await client.get(
        "/api/v1/assets/export/csv",
        params={"project_id": project_id},
        headers=analyst_headers,
    )
    assert resp.status_code == 200
    assert resp.text.splitlines()[1].startswith("'=")


@pytest.mark.asyncio
async def test_knowledge_versions(client: AsyncClient, viewer_headers: dict):
    resp = await client.get("/api/v1/knowledge/versions", headers=viewer_headers)
    assert resp.status_code == 200
    assert "engine_version" in resp.json()
