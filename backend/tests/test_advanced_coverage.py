"""Targeted tests to boost coverage on low-coverage modules."""
from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient


async def _create_incident(client: AsyncClient, headers: dict, **extra) -> dict:
    payload = {
        "title": "Test Coverage Incident",
        "description": "Created for coverage purposes",
        "severity": "high",
        "source_ip": "10.0.0.1",
        "destination_port": 443,
    }
    payload.update(extra)
    resp = await client.post("/api/v1/incidents", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()

@pytest.mark.asyncio
async def test_security_score_basic(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/security-score", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert 0 <= data["score"] <= 100
    assert data["grade"] in ("A", "B", "C", "D", "F")
    assert "factors" in data
    assert "recommendations" in data
    assert "data_snapshot" in data

@pytest.mark.asyncio
async def test_security_score_requires_auth(client: AsyncClient):
    assert (await client.get("/api/v1/security-score")).status_code == 401

@pytest.mark.asyncio
async def test_security_score_with_project_id(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"/api/v1/security-score?project_id={uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_security_score_with_critical_incident(client: AsyncClient, auth_headers: dict):
    await _create_incident(client, auth_headers, severity="critical")
    resp = await client.get("/api/v1/security-score", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data_snapshot"]["open_critical_incidents"] >= 1

@pytest.mark.asyncio
async def test_infrastructure_status(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/infrastructure", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "ecs_services" in data
    assert "sqs_queues" in data
    assert "api_latency_p50_ms" in data
    assert "worker_health" in data

@pytest.mark.asyncio
async def test_infrastructure_requires_auth(client: AsyncClient):
    assert (await client.get("/api/v1/infrastructure")).status_code == 401

@pytest.mark.asyncio
async def test_infrastructure_sqs_history(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/infrastructure/sqs-history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 10
    assert "time" in data[0]

@pytest.mark.asyncio
async def test_infrastructure_sqs_history_custom_hours(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/infrastructure/sqs-history?hours=5", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 5

@pytest.mark.asyncio
async def test_dashboard_summary(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_incidents" in data
    assert "severity_breakdown" in data
    assert "recent_incidents" in data

@pytest.mark.asyncio
async def test_dashboard_summary_with_project_id(client: AsyncClient, auth_headers: dict):
    proj_resp = await client.post("/api/v1/projects", json={"name": "Dash Proj"}, headers=auth_headers)
    project_id = proj_resp.json()["id"]
    resp = await client.get(f"/api/v1/dashboard/summary?project_id={project_id}", headers=auth_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    assert (await client.get("/api/v1/dashboard/summary")).status_code == 401

@pytest.mark.asyncio
async def test_ml_model_info(client: AsyncClient, auth_headers: dict):
    assert (await client.get("/api/v1/ml/model-info", headers=auth_headers)).status_code == 200

@pytest.mark.asyncio
async def test_ml_model_info_requires_auth(client: AsyncClient):
    assert (await client.get("/api/v1/ml/model-info")).status_code == 401

@pytest.mark.asyncio
async def test_ml_models_list(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/ml/models", headers=auth_headers)
    assert resp.status_code == 200
    assert "models" in resp.json()

@pytest.mark.asyncio
async def test_ml_stats(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/ml/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "predictions_today" in data
    assert "attack_distribution" in data

@pytest.mark.asyncio
async def test_ml_flows(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/ml/flows", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_ml_metrics(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/ml/metrics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "feature_importance" in data
    assert "tactic_distribution" in data

@pytest.mark.asyncio
async def test_ml_classify(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/ml/classify", json={
        "destination_port": 443, "flow_duration": 1000.0, "flow_bytes_per_sec": 5000.0,
    }, headers=auth_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_ml_requires_auth(client: AsyncClient):
    assert (await client.get("/api/v1/ml/stats")).status_code == 401

@pytest.mark.asyncio
async def test_incident_with_eu_jurisdiction_creates_notifications(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/incidents", json={
        "title": "EU Data Breach", "severity": "critical",
        "affected_jurisdictions": ["EU"], "personal_data_involved": True,
    }, headers=auth_headers)
    assert resp.status_code == 201
    notif_resp = await client.get(
        f"/api/v1/notifications?incident_id={resp.json()['id']}", headers=auth_headers)
    assert notif_resp.json()["total"] >= 1

@pytest.mark.asyncio
async def test_incident_with_hipaa_creates_notification(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/incidents", json={
        "title": "HIPAA Breach", "severity": "high", "health_data_involved": True,
    }, headers=auth_headers)
    assert resp.status_code == 201
    notif_resp = await client.get(
        f"/api/v1/notifications?incident_id={resp.json()['id']}", headers=auth_headers)
    assert notif_resp.json()["total"] >= 1

@pytest.mark.asyncio
async def test_list_notifications(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()

@pytest.mark.asyncio
async def test_list_notifications_status_filter(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/incidents", json={
        "title": "Filter Test", "severity": "high",
        "affected_jurisdictions": ["EU"], "personal_data_involved": True,
    }, headers=auth_headers)
    resp = await client.get("/api/v1/notifications?status=pending", headers=auth_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_list_notifications_regulation_filter(client: AsyncClient, auth_headers: dict):
    await client.post("/api/v1/incidents", json={
        "title": "Regulation Filter", "severity": "high",
        "affected_jurisdictions": ["EU"], "personal_data_involved": True,
    }, headers=auth_headers)
    resp = await client.get("/api/v1/notifications?regulation=GDPR", headers=auth_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_get_notification_by_id(client: AsyncClient, auth_headers: dict):
    inc_resp = await client.post("/api/v1/incidents", json={
        "title": "Notif ID Test", "severity": "critical",
        "affected_jurisdictions": ["EU"], "personal_data_involved": True,
    }, headers=auth_headers)
    incident_id = inc_resp.json()["id"]
    list_resp = await client.get(
        f"/api/v1/notifications?incident_id={incident_id}", headers=auth_headers)
    notif_id = list_resp.json()["items"][0]["id"]
    get_resp = await client.get(f"/api/v1/notifications/{notif_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == notif_id

@pytest.mark.asyncio
async def test_approve_notification(client: AsyncClient, auth_headers: dict):
    inc_resp = await client.post("/api/v1/incidents", json={
        "title": "Approvable", "severity": "high",
        "affected_jurisdictions": ["EU"], "personal_data_involved": True,
    }, headers=auth_headers)
    incident_id = inc_resp.json()["id"]
    list_resp = await client.get(
        f"/api/v1/notifications?incident_id={incident_id}", headers=auth_headers)
    notif_id = list_resp.json()["items"][0]["id"]
    resp = await client.post(f"/api/v1/notifications/{notif_id}/approve", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

@pytest.mark.asyncio
async def test_dispatch_notification(client: AsyncClient, auth_headers: dict):
    inc_resp = await client.post("/api/v1/incidents", json={
        "title": "Dispatchable", "severity": "high",
        "affected_jurisdictions": ["EU"], "personal_data_involved": True,
    }, headers=auth_headers)
    incident_id = inc_resp.json()["id"]
    list_resp = await client.get(
        f"/api/v1/notifications?incident_id={incident_id}", headers=auth_headers)
    notif_id = list_resp.json()["items"][0]["id"]
    resp = await client.post(f"/api/v1/notifications/{notif_id}/dispatch", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] in ("sent", "failed", "approved")

@pytest.mark.asyncio
async def test_send_notification_after_approve(client: AsyncClient, auth_headers: dict):
    inc_resp = await client.post("/api/v1/incidents", json={
        "title": "Send After Approve", "severity": "high",
        "affected_jurisdictions": ["EU"], "personal_data_involved": True,
    }, headers=auth_headers)
    incident_id = inc_resp.json()["id"]
    list_resp = await client.get(
        f"/api/v1/notifications?incident_id={incident_id}", headers=auth_headers)
    notif_id = list_resp.json()["items"][0]["id"]
    await client.post(f"/api/v1/notifications/{notif_id}/approve", headers=auth_headers)
    resp = await client.post(f"/api/v1/notifications/{notif_id}/send", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] in ("sent", "failed")

@pytest.mark.asyncio
async def test_notifications_require_auth(client: AsyncClient):
    assert (await client.get("/api/v1/notifications")).status_code == 401

@pytest.mark.asyncio
async def test_demo_generate(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/demo/generate", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["incidents_created"] > 0

@pytest.mark.asyncio
async def test_demo_generate_rate_limit(client: AsyncClient, auth_headers: dict):
    first = await client.post("/api/v1/demo/generate", headers=auth_headers)
    assert first.status_code == 201
    second = await client.post("/api/v1/demo/generate", headers=auth_headers)
    assert second.status_code == 429

@pytest.mark.asyncio
async def test_demo_generate_requires_auth(client: AsyncClient):
    assert (await client.post("/api/v1/demo/generate")).status_code == 401

@pytest.mark.asyncio
async def test_incident_stats(client: AsyncClient, auth_headers: dict):
    assert (await client.get("/api/v1/incidents/stats", headers=auth_headers)).status_code == 200

@pytest.mark.asyncio
async def test_incident_stats_with_project(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"/api/v1/incidents/stats?project_id={uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_incident_status_change(client: AsyncClient, auth_headers: dict):
    inc = await _create_incident(client, auth_headers)
    resp = await client.post(
        f"/api/v1/incidents/{inc['id']}/status",
        json={"status": "triaging"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "triaging"

@pytest.mark.asyncio
async def test_incident_reopen(client: AsyncClient, auth_headers: dict):
    inc = await _create_incident(client, auth_headers)
    inc_id = inc["id"]
    await client.post(f"/api/v1/incidents/{inc_id}/status", json={"status": "triaging"}, headers=auth_headers)
    await client.post(f"/api/v1/incidents/{inc_id}/status", json={"status": "closed"}, headers=auth_headers)
    resp = await client.post(f"/api/v1/incidents/{inc_id}/reopen", json={"reason": "New evidence"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "reopened"

@pytest.mark.asyncio
async def test_incident_delete(client: AsyncClient, auth_headers: dict):
    inc = await _create_incident(client, auth_headers)
    resp = await client.delete(f"/api/v1/incidents/{inc['id']}", headers=auth_headers)
    assert resp.status_code == 204

@pytest.mark.asyncio
async def test_incident_explain(client: AsyncClient, auth_headers: dict):
    inc = await _create_incident(client, auth_headers, title="SQL Injection Test")
    resp = await client.get(f"/api/v1/incidents/{inc['id']}/explain", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["incident_id"] == inc["id"]

@pytest.mark.asyncio
async def test_incident_list_with_filters(client: AsyncClient, auth_headers: dict):
    await _create_incident(client, auth_headers, severity="critical", title="Critical SQL Injection")
    assert (await client.get("/api/v1/incidents?severity=critical", headers=auth_headers)).status_code == 200
    assert (await client.get("/api/v1/incidents?status=new", headers=auth_headers)).status_code == 200
    resp = await client.get("/api/v1/incidents?search=SQL", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

@pytest.mark.asyncio
async def test_incident_via_project_api_key(client: AsyncClient, auth_headers: dict):
    proj_resp = await client.post("/api/v1/projects", json={"name": "API Key Proj"}, headers=auth_headers)
    api_key = proj_resp.json()["api_key"]
    resp = await client.post("/api/v1/incidents", json={
        "title": "Incident via Project Key", "severity": "medium",
    }, headers={**auth_headers, "X-Project-Key": api_key})
    assert resp.status_code == 201
    assert "id" in resp.json()

@pytest.mark.asyncio
async def test_weekly_report_with_incident_data(client: AsyncClient, auth_headers: dict):
    for t in ["SQL Injection", "XSS Attack", "Port Scan"]:
        await _create_incident(client, auth_headers, title=t)
    resp = await client.get("/api/v1/reports/weekly", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_incidents"] >= 3

@pytest.mark.asyncio
async def test_weekly_report_project_scoped(client: AsyncClient, auth_headers: dict):
    resp = await client.get(f"/api/v1/reports/weekly?project_id={uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_viewer_can_access_security_score(client: AsyncClient, viewer_headers: dict):
    assert (await client.get("/api/v1/security-score", headers=viewer_headers)).status_code == 200

@pytest.mark.asyncio
async def test_viewer_can_access_dashboard(client: AsyncClient, viewer_headers: dict):
    assert (await client.get("/api/v1/dashboard/summary", headers=viewer_headers)).status_code == 200

@pytest.mark.asyncio
async def test_viewer_can_read_ml_stats(client: AsyncClient, viewer_headers: dict):
    assert (await client.get("/api/v1/ml/stats", headers=viewer_headers)).status_code == 200

@pytest.mark.asyncio
async def test_viewer_cannot_manage_ml(client: AsyncClient, viewer_headers: dict):
    assert (await client.get("/api/v1/ml/models", headers=viewer_headers)).status_code == 403

@pytest.mark.asyncio
async def test_audit_log_accessible(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/audit/logs", headers=auth_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()

@pytest.mark.asyncio
async def test_audit_log_requires_auth(client: AsyncClient):
    assert (await client.get("/api/v1/audit/logs")).status_code == 401
