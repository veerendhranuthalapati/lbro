"""Evidence vault endpoint tests."""
from __future__ import annotations

import hashlib
import uuid

import pytest
from httpx import AsyncClient


async def _create_incident(client: AsyncClient, headers: dict) -> dict:
    """Create a minimal test incident and return its JSON."""
    resp = await client.post("/api/v1/incidents", json={
        "title": "Evidence Test Incident",
        "severity": "medium",
    }, headers=headers)
    assert resp.status_code == 201, f"Incident creation failed: {resp.text}"
    return resp.json()


# ── Upload ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_evidence_valid(client: AsyncClient, auth_headers: dict):
    """Valid file upload returns id + correct sha256."""
    inc = await _create_incident(client, auth_headers)
    incident_id = inc["id"]

    file_bytes = b"This is test evidence file content for hashing."
    resp = await client.post(
        f"/api/v1/incidents/{incident_id}/evidence",
        files={"file": ("evidence.txt", file_bytes, "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "sha256_hash" in data
    expected_hash = hashlib.sha256(file_bytes).hexdigest()
    assert data["sha256_hash"] == expected_hash
    assert data["file_size"] == len(file_bytes)
    assert data["filename"] == "evidence.txt"


@pytest.mark.asyncio
async def test_upload_evidence_pdf(client: AsyncClient, auth_headers: dict):
    """PDF upload is allowed."""
    inc = await _create_incident(client, auth_headers)
    pdf_bytes = b"%PDF-1.4 fake pdf content for testing purposes only"
    resp = await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("report.pdf", pdf_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_upload_evidence_disallowed_mime_type(client: AsyncClient, auth_headers: dict):
    """text/html is not in the allowed MIME list — returns 400."""
    inc = await _create_incident(client, auth_headers)
    resp = await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("page.html", b"<html>bad</html>", "text/html")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_evidence_exe_magic_bytes_rejected(client: AsyncClient, auth_headers: dict):
    """File starting with MZ (Windows EXE) magic bytes is rejected even if labeled as PDF."""
    inc = await _create_incident(client, auth_headers)
    exe_bytes = b"\x4d\x5a" + b"\x00" * 100  # MZ header
    resp = await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("malware.pdf", exe_bytes, "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_evidence_viewer_gets_403(client: AsyncClient, viewer_token: str, auth_headers: dict):
    """Viewer role lacks UPLOAD_EVIDENCE — must return 403."""
    inc = await _create_incident(client, auth_headers)
    resp = await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("test.txt", b"content", "text/plain")},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


# ── Download ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_download_evidence_returns_bytes(client: AsyncClient, auth_headers: dict):
    """Downloaded file bytes must match what was uploaded."""
    inc = await _create_incident(client, auth_headers)
    original_bytes = b"Binary evidence content 0x00 0xff"
    upload_resp = await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("binary.bin", original_bytes, "application/octet-stream")},
        headers=auth_headers,
    )
    assert upload_resp.status_code == 201
    evidence_id = upload_resp.json()["id"]

    dl_resp = await client.get(
        f"/api/v1/evidence/{evidence_id}/download",
        headers=auth_headers,
    )
    assert dl_resp.status_code == 200
    assert dl_resp.content == original_bytes


@pytest.mark.asyncio
async def test_download_missing_evidence_id_returns_404(client: AsyncClient, auth_headers: dict):
    """Non-existent evidence id returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/v1/evidence/{fake_id}/download",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── SHA-256 verification ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sha256_verify_endpoint(client: AsyncClient, auth_headers: dict):
    """POST /evidence/{id}/verify must confirm hash integrity."""
    inc = await _create_incident(client, auth_headers)
    data_bytes = b"Verify me please."
    upload_resp = await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("verify.txt", data_bytes, "text/plain")},
        headers=auth_headers,
    )
    assert upload_resp.status_code == 201
    evidence_id = upload_resp.json()["id"]

    verify_resp = await client.post(
        f"/api/v1/evidence/{evidence_id}/verify",
        headers=auth_headers,
    )
    assert verify_resp.status_code == 200
    result = verify_resp.json()
    assert result["ok"] is True
    assert result["hash"] == hashlib.sha256(data_bytes).hexdigest()


# ── List evidence ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_evidence_for_incident(client: AsyncClient, auth_headers: dict):
    """GET /incidents/{id}/evidence returns items uploaded to that incident."""
    inc = await _create_incident(client, auth_headers)
    await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("a.txt", b"file a", "text/plain")},
        headers=auth_headers,
    )
    await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("b.txt", b"file b", "text/plain")},
        headers=auth_headers,
    )

    list_resp = await client.get(
        f"/api/v1/incidents/{inc['id']}/evidence",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_list_all_evidence(client: AsyncClient, auth_headers: dict):
    """GET /evidence returns global paginated evidence list."""
    resp = await client.get("/api/v1/evidence", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body


# ── Get evidence by id ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_evidence_by_id(client: AsyncClient, auth_headers: dict):
    """GET /evidence/{id} returns the evidence record with metadata."""
    inc = await _create_incident(client, auth_headers)
    file_bytes = b"metadata test"
    upload_resp = await client.post(
        f"/api/v1/incidents/{inc['id']}/evidence",
        files={"file": ("meta.txt", file_bytes, "text/plain")},
        headers=auth_headers,
    )
    assert upload_resp.status_code == 201
    evidence_id = upload_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/evidence/{evidence_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    ev = get_resp.json()
    assert ev["id"] == evidence_id
    assert ev["sha256_hash"] == hashlib.sha256(file_bytes).hexdigest()
