"""Incident endpoint tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_incident(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/incidents", json={
        "title": "SSH Brute Force Detected",
        "severity": "high",
        "source_ip": "192.168.1.100",
        "destination_ip": "10.0.0.5",
        "destination_port": 22,
        "protocol": "TCP",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "SSH Brute Force Detected"
    assert data["severity"] == "high"
    assert data["status"] == "new"


@pytest.mark.asyncio
async def test_list_incidents(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/incidents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_incident(client: AsyncClient, auth_headers: dict):
    # Create first
    create_resp = await client.post("/api/v1/incidents", json={
        "title": "Test Incident",
        "severity": "medium",
    }, headers=auth_headers)
    incident_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/incidents/{incident_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == incident_id


@pytest.mark.asyncio
async def test_update_incident(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/incidents", json={
        "title": "Initial Title",
        "severity": "low",
    }, headers=auth_headers)
    incident_id = create_resp.json()["id"]

    resp = await client.patch(f"/api/v1/incidents/{incident_id}", json={
        "title": "Updated Title",
        "severity": "critical",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_status_transition(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/incidents", json={
        "title": "Status Test Incident",
    }, headers=auth_headers)
    incident_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/incidents/{incident_id}/status", json={
        "status": "triaging",
        "notes": "Beginning triage",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "triaging"


@pytest.mark.asyncio
async def test_invalid_status_transition(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/v1/incidents", json={
        "title": "Invalid Transition Test",
    }, headers=auth_headers)
    incident_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/incidents/{incident_id}/status", json={
        "status": "closed",
    }, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_incident_stats(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/incidents/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "by_status" in data
    assert "by_severity" in data


@pytest.mark.asyncio
async def test_unauthenticated_access(client: AsyncClient):
    resp = await client.get("/api/v1/incidents")
    assert resp.status_code == 401
