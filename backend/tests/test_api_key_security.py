"""API key hashing and isolation regression tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.api_keys import generate_project_api_key, hash_api_key, verify_api_key


def test_api_key_hash_verify_roundtrip():
    full, prefix, stored = generate_project_api_key()
    assert full.startswith("proj_")
    assert prefix == full[:16]
    assert verify_api_key(full, stored)
    assert not verify_api_key(full + "x", stored)


@pytest.mark.asyncio
async def test_project_create_returns_key_once(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Key Test Project", "environment": "development"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "api_key" in body
    assert body["api_key"].startswith("proj_")
    assert "api_key_prefix" in body
    assert body["api_key_prefix"].startswith("proj_")

    get_resp = await client.get(f"/api/v1/projects/{body['id']}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert "api_key" not in get_resp.json()
    assert "api_key_prefix" in get_resp.json()


@pytest.mark.asyncio
async def test_regenerate_invalidates_old_key(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/projects",
        json={"name": "Rotate Key Project"},
        headers=auth_headers,
    )
    assert create.status_code == 201
    project_id = create.json()["id"]
    old_key = create.json()["api_key"]

    regen = await client.post(
        f"/api/v1/projects/{project_id}/regenerate-key",
        headers=auth_headers,
    )
    assert regen.status_code == 200
    new_key = regen.json()["api_key"]
    assert new_key != old_key

    old_event = await client.post(
        "/api/v1/events",
        json={"event_type": "test", "severity": "low", "message": "x"},
        headers={"Authorization": f"Bearer {old_key}"},
    )
    assert old_event.status_code == 401

    new_event = await client.post(
        "/api/v1/events",
        json={"event_type": "auth_failure", "severity": "low", "message": "x"},
        headers={"Authorization": f"Bearer {new_key}"},
    )
    assert new_event.status_code == 202
