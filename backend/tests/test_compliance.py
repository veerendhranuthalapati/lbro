"""Compliance obligation and scoring endpoint tests."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "Compliance Test Project") -> str:
    """Helper: create a project and return its id string."""
    resp = await client.post("/api/v1/projects", json={
        "name": name,
        "description": "Auto-created for compliance tests",
        "environment": "development",
    }, headers=headers)
    assert resp.status_code == 201, f"Project creation failed: {resp.text}"
    return resp.json()["id"]


# ── List obligations ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_obligations_empty_for_new_project(client: AsyncClient, auth_headers: dict):
    """A freshly created project has no obligations."""
    project_id = await _create_project(client, auth_headers)
    resp = await client.get(
        f"/api/v1/compliance/obligations?project_id={project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ── Create obligation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_obligation(client: AsyncClient, analyst_headers: dict, auth_headers: dict):
    """Analyst can POST a new obligation; response has correct shape."""
    project_id = await _create_project(client, auth_headers, "Create Obligation Project")
    resp = await client.post(
        f"/api/v1/compliance/obligations?project_id={project_id}",
        json={
            "framework": "GDPR",
            "control_id": "g1",
            "control_name": "Data Protection by Design",
            "status": "not_started",
        },
        headers=analyst_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["framework"] == "GDPR"
    assert data["control_id"] == "g1"
    assert str(data["project_id"]) == project_id
    assert data["status"] == "not_started"
    assert data["score"] == 0.0


@pytest.mark.asyncio
async def test_create_obligation_compliant_sets_score_100(
    client: AsyncClient, analyst_headers: dict, auth_headers: dict
):
    """Creating an obligation with status=compliant must auto-set score=100."""
    project_id = await _create_project(client, auth_headers, "Score 100 Project")
    resp = await client.post(
        f"/api/v1/compliance/obligations?project_id={project_id}",
        json={
            "framework": "HIPAA",
            "control_id": "h1",
            "control_name": "Access Controls",
            "status": "compliant",
        },
        headers=analyst_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["score"] == 100.0


# ── Update obligation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_obligation_status(client: AsyncClient, analyst_headers: dict, auth_headers: dict):
    """PATCH changes status and auto-recalculates score."""
    project_id = await _create_project(client, auth_headers, "Patch Obligation Project")
    create_resp = await client.post(
        f"/api/v1/compliance/obligations?project_id={project_id}",
        json={"framework": "GDPR", "control_id": "g2", "control_name": "Encryption", "status": "not_started"},
        headers=analyst_headers,
    )
    assert create_resp.status_code == 200
    obligation_id = create_resp.json()["id"]

    patch_resp = await client.patch(
        f"/api/v1/compliance/obligations/{obligation_id}",
        json={"status": "compliant"},
        headers=analyst_headers,
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["status"] == "compliant"
    assert patched["score"] == 100.0


@pytest.mark.asyncio
async def test_patch_nonexistent_obligation_returns_404(
    client: AsyncClient, analyst_headers: dict
):
    """Patching a non-existent obligation id returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/api/v1/compliance/obligations/{fake_id}",
        json={"status": "compliant"},
        headers=analyst_headers,
    )
    assert resp.status_code == 404


# ── Compliance score ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_score_zero_for_empty_project(client: AsyncClient, auth_headers: dict):
    """Score endpoint returns 0 and totals=0 when no obligations exist."""
    project_id = await _create_project(client, auth_headers, "Empty Score Project")
    resp = await client.get(
        f"/api/v1/compliance/score?project_id={project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_score"] == 0.0
    assert data["total_controls"] == 0
    assert data["compliant_controls"] == 0


@pytest.mark.asyncio
async def test_score_100_when_all_compliant(client: AsyncClient, analyst_headers: dict, auth_headers: dict):
    """Score is 100 when every obligation is marked compliant."""
    project_id = await _create_project(client, auth_headers, "Full Compliance Project")
    for i in range(3):
        await client.post(
            f"/api/v1/compliance/obligations?project_id={project_id}",
            json={"framework": "GDPR", "control_id": f"g{i}", "control_name": f"Control {i}", "status": "compliant"},
            headers=analyst_headers,
        )

    resp = await client.get(
        f"/api/v1/compliance/score?project_id={project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_score"] == 100.0
    assert data["compliant_controls"] == 3
    assert data["total_controls"] == 3


@pytest.mark.asyncio
async def test_score_partial_compliance(client: AsyncClient, analyst_headers: dict, auth_headers: dict):
    """Score is 50 when half the obligations are compliant."""
    project_id = await _create_project(client, auth_headers, "Partial Compliance Project")
    # 2 compliant, 2 not_started
    for i in range(2):
        await client.post(
            f"/api/v1/compliance/obligations?project_id={project_id}",
            json={"framework": "GDPR", "control_id": f"c{i}", "control_name": f"C{i}", "status": "compliant"},
            headers=analyst_headers,
        )
    for i in range(2):
        await client.post(
            f"/api/v1/compliance/obligations?project_id={project_id}",
            json={"framework": "GDPR", "control_id": f"n{i}", "control_name": f"N{i}", "status": "not_started"},
            headers=analyst_headers,
        )

    resp = await client.get(
        f"/api/v1/compliance/score?project_id={project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["overall_score"] == 50.0


# ── RBAC on compliance ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_viewer_can_read_obligations(client: AsyncClient, viewer_headers: dict, auth_headers: dict):
    """Viewer role has VIEW_COMPLIANCE — reading obligations returns 200."""
    project_id = await _create_project(client, auth_headers, "Viewer Read Project")
    resp = await client.get(
        f"/api/v1/compliance/obligations?project_id={project_id}",
        headers=viewer_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_viewer_cannot_create_obligation(client: AsyncClient, viewer_headers: dict, auth_headers: dict):
    """Viewer lacks MANAGE_COMPLIANCE — POST obligation returns 403."""
    project_id = await _create_project(client, auth_headers, "Viewer Write Project")
    resp = await client.post(
        f"/api/v1/compliance/obligations?project_id={project_id}",
        json={"framework": "GDPR", "control_id": "g1", "control_name": "Test", "status": "not_started"},
        headers=viewer_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_compliance_score_returns_401(client: AsyncClient):
    """No token — returns 401."""
    fake_project = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/compliance/score?project_id={fake_project}")
    assert resp.status_code == 401


# ── Compliance dashboard ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compliance_dashboard(client: AsyncClient, auth_headers: dict):
    """Dashboard endpoint returns summaries list."""
    resp = await client.get("/api/v1/compliance/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "summaries" in data
    assert isinstance(data["summaries"], list)


# ── Assessment snapshot ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_assessment(client: AsyncClient, analyst_headers: dict, auth_headers: dict):
    """POST /compliance/assess persists a score snapshot."""
    project_id = await _create_project(client, auth_headers, "Assessment Project")
    resp = await client.post(
        f"/api/v1/compliance/assess?project_id={project_id}&framework=GDPR",
        headers=analyst_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["framework"] == "GDPR"
    assert str(data["project_id"]) == project_id


@pytest.mark.asyncio
async def test_list_assessments(client: AsyncClient, analyst_headers: dict, auth_headers: dict):
    """GET /compliance/assessments returns list (may be empty)."""
    project_id = await _create_project(client, auth_headers, "Assessments List Project")
    resp = await client.get(
        f"/api/v1/compliance/assessments?project_id={project_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
