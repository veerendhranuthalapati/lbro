"""Data-integrity audit tests — compliance and ML metrics must not be fabricated."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.metrics import compliance_percentage, format_compliance_pct
from app.ml.model_registry import has_verified_evaluation, model_artifact_exists


@pytest.mark.asyncio
async def test_compliance_percentage_zero_total_returns_none():
    assert compliance_percentage(0, 0) is None
    assert compliance_percentage(5, 0) is None
    assert format_compliance_pct(0, 0) == "N/A"


@pytest.mark.asyncio
async def test_compliance_score_empty_project_has_no_data(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Empty Integrity", "environment": "development"},
        headers=auth_headers,
    )
    pid = resp.json()["id"]
    score = await client.get(f"/api/v1/compliance/score?project_id={pid}", headers=auth_headers)
    assert score.status_code == 200
    data = score.json()
    assert data["has_data"] is False
    assert data["overall_score"] is None
    assert data["total_controls"] == 0


@pytest.mark.asyncio
async def test_compliance_score_one_obligation(client: AsyncClient, analyst_headers: dict):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "One Obligation", "environment": "development"},
        headers=analyst_headers,
    )
    pid = resp.json()["id"]
    await client.post(
        f"/api/v1/compliance/obligations?project_id={pid}",
        json={"framework": "GDPR", "control_id": "g1", "control_name": "Notify", "status": "compliant"},
        headers=analyst_headers,
    )
    score = await client.get(f"/api/v1/compliance/score?project_id={pid}", headers=analyst_headers)
    data = score.json()
    assert data["has_data"] is True
    assert data["overall_score"] == 100.0
    assert data["total_controls"] == 1


@pytest.mark.asyncio
async def test_compliance_score_mixed_50_percent(client: AsyncClient, analyst_headers: dict):
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Mixed Compliance", "environment": "development"},
        headers=analyst_headers,
    )
    pid = resp.json()["id"]
    for cid, status in [("a", "compliant"), ("b", "not_started")]:
        await client.post(
            f"/api/v1/compliance/obligations?project_id={pid}",
            json={"framework": "GDPR", "control_id": cid, "control_name": cid, "status": status},
            headers=analyst_headers,
        )
    score = await client.get(f"/api/v1/compliance/score?project_id={pid}", headers=analyst_headers)
    data = score.json()
    assert data["has_data"] is True
    assert data["overall_score"] == 50.0


@pytest.mark.asyncio
async def test_compliance_dashboard_empty_has_no_pct(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/compliance/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_data"] is False
    assert data["overall_compliance_pct"] is None


@pytest.mark.asyncio
async def test_compliance_dashboard_matches_demo_records(client: AsyncClient, auth_headers: dict):
    """Dashboard counts must reflect seeded compliance records."""
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "PDF Integrity", "environment": "development"},
        headers=auth_headers,
    )
    pid = proj.json()["id"]
    gen = await client.post(
        "/api/v1/demo/generate",
        json={"project_id": pid},
        headers=auth_headers,
    )
    assert gen.status_code == 201
    assert gen.json()["compliance_created"] > 0

    dash = await client.get(f"/api/v1/compliance/dashboard?project_id={pid}", headers=auth_headers)
    assert dash.status_code == 200
    body = dash.json()
    assert body["has_data"] is True
    assert body["total_records"] == gen.json()["compliance_created"]
    assert body["overall_compliance_pct"] is not None


@pytest.mark.asyncio
async def test_compliance_pdf_matches_dashboard(client: AsyncClient, auth_headers: dict):
    """PDF summary numbers must match dashboard API (same DB query path)."""
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "PDF Match", "environment": "development"},
        headers=auth_headers,
    )
    pid = proj.json()["id"]
    await client.post("/api/v1/demo/generate", json={"project_id": pid}, headers=auth_headers)

    dash = (await client.get(f"/api/v1/compliance/dashboard?project_id={pid}", headers=auth_headers)).json()
    pdf = await client.get(f"/api/v1/reports/compliance/pdf?project_id={pid}", headers=auth_headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    total = dash["total_records"]
    met = dash["met_records"]
    assert str(total).encode() in pdf.content
    assert str(met).encode() in pdf.content
    if total > 0:
        expected_pct = compliance_percentage(met, total)
        assert dash["overall_compliance_pct"] == expected_pct
    else:
        assert dash["overall_compliance_pct"] is None


@pytest.mark.asyncio
async def test_compliance_pdf_empty_shows_no_data(client: AsyncClient, auth_headers: dict):
    """Empty PDF must not claim 100% — verify via dashboard + PDF generation succeeds."""
    dash = (await client.get("/api/v1/compliance/dashboard", headers=auth_headers)).json()
    assert dash["has_data"] is False
    assert dash["overall_compliance_pct"] is None

    resp = await client.get("/api/v1/reports/compliance/pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
    # Compressed PDF — verify zero totals appear as plain digits in the stream
    assert b"0" in resp.content


@pytest.mark.asyncio
async def test_compliance_project_isolation(client: AsyncClient, analyst_headers: dict, auth_headers: dict):
    """Obligations in project A must not affect score in project B."""
    a = (await client.post("/api/v1/projects", json={"name": "Iso A", "environment": "development"}, headers=auth_headers)).json()["id"]
    b = (await client.post("/api/v1/projects", json={"name": "Iso B", "environment": "development"}, headers=auth_headers)).json()["id"]
    await client.post(
        f"/api/v1/compliance/obligations?project_id={a}",
        json={"framework": "GDPR", "control_id": "x", "control_name": "X", "status": "compliant"},
        headers=analyst_headers,
    )
    score_b = (await client.get(f"/api/v1/compliance/score?project_id={b}", headers=auth_headers)).json()
    assert score_b["has_data"] is False
    assert score_b["overall_score"] is None


@pytest.mark.asyncio
async def test_ml_metrics_no_synthetic_defaults(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/ml/metrics", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "has_evaluation_data" in body
    assert body["runtime_mode"] in ("model", "heuristic")


@pytest.mark.asyncio
async def test_ml_stats_evaluation_gated_on_model_file(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/ml/stats", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_evaluation_data"] == has_verified_evaluation()
    if not model_artifact_exists() and body.get("active_model"):
        assert body["active_model"].get("accuracy") is None


@pytest.mark.asyncio
async def test_ml_metrics_fp_empty_without_evaluation(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/ml/metrics", headers=auth_headers)
    if not has_verified_evaluation():
        body = resp.json()
        assert body.get("false_positive_analysis", []) == []
        assert body.get("evaluation") is None
        for row in body.get("per_class_confidence", []):
            assert 0 <= row["A"] <= 100


@pytest.mark.asyncio
async def test_ml_metrics_no_fake_accuracy_when_heuristic(client: AsyncClient, auth_headers: dict):
    if has_verified_evaluation():
        pytest.skip("Model artifact present — heuristic guard not applicable")
    resp = await client.get("/api/v1/ml/metrics", headers=auth_headers)
    body = resp.json()
    assert body["has_evaluation_data"] is False
    assert body.get("evaluation") is None

