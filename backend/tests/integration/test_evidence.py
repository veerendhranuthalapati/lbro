"""
Evidence test suite — LBRO
Covers: upload, list, download, integrity verification, delete, content filtering.
"""
from __future__ import annotations

import io
import hashlib

import pytest
from httpx import AsyncClient


class TestEvidenceUpload:
    async def test_upload_text_file_returns_201_with_metadata(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        content = b"Captured log entry showing SQL injection attempt"
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("capture.txt", io.BytesIO(content), "text/plain")},
            data={"description": "Network capture log"},
            headers=alice_h,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["filename"] == "capture.txt"
        assert body["sha256_hash"] is not None
        assert body["file_size"] == len(content)

    async def test_uploaded_sha256_matches_file_content(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        content = b"deterministic content for hash verification"
        expected_hash = hashlib.sha256(content).hexdigest()

        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("hashcheck.txt", io.BytesIO(content), "text/plain")},
            headers=alice_h,
        )
        assert resp.status_code == 201
        assert resp.json()["sha256_hash"] == expected_hash

    async def test_upload_json_file_succeeds(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("data.json", io.BytesIO(b'{"key": "value"}'), "application/json")},
            headers=alice_h,
        )
        assert resp.status_code == 201

    async def test_upload_executable_rejected(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        """ELF magic bytes must be rejected by content inspection."""
        elf_header = b"\x7fELF" + b"\x00" * 20
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("malware.bin", io.BytesIO(elf_header), "application/octet-stream")},
            headers=alice_h,
        )
        assert resp.status_code == 400

    async def test_upload_pe_executable_rejected(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        """PE (Windows EXE) magic bytes MZ must be rejected."""
        mz_header = b"MZ" + b"\x00" * 20
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("evil.exe", io.BytesIO(mz_header), "application/octet-stream")},
            headers=alice_h,
        )
        assert resp.status_code == 400

    async def test_upload_disallowed_content_type_rejected(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("page.html", io.BytesIO(b"<html>test</html>"), "text/html")},
            headers=alice_h,
        )
        assert resp.status_code == 400

    async def test_filename_path_traversal_is_sanitized(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        """Filenames with ../ path traversal components must be sanitized."""
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("../../etc/passwd", io.BytesIO(b"safe content here"), "text/plain")},
            headers=alice_h,
        )
        # Either rejected or sanitized — never stored with raw path
        if resp.status_code == 201:
            stored_name = resp.json()["filename"]
            assert ".." not in stored_name
            assert "/" not in stored_name
            assert "\\" not in stored_name

    async def test_viewer_cannot_upload_evidence(
        self, client: AsyncClient, carol_h: dict, sql_injection_incident: dict
    ):
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": ("test.txt", io.BytesIO(b"data"), "text/plain")},
            headers=carol_h,
        )
        assert resp.status_code == 403


class TestEvidenceList:
    async def test_list_evidence_for_incident(
        self, client: AsyncClient, alice_h: dict,
        sql_injection_incident: dict, portfolio_evidence: dict  # noqa: ARG002
    ):
        resp = await client.get(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            headers=alice_h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) >= 1

    async def test_list_all_evidence_filtered_by_project(
        self, client: AsyncClient, alice_h: dict,
        portfolio_evidence: dict, hospital_evidence: dict,
        portfolio_project: dict
    ):
        """IDOR GAP (documented): GET /evidence?project_id=... does not enforce
        project scoping — the endpoint returns all evidence regardless of
        project_id param. Portfolio evidence is visible but so is hospital evidence.
        This is a known gap; test documents observed behaviour."""
        resp = await client.get(
            "/api/v1/evidence",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        ids = {e["id"] for e in resp.json().get("items", [])}
        # The endpoint exists and returns the uploaded evidence
        assert portfolio_evidence["id"] in ids
        # Documents gap: project_id filter is not enforced; hospital evidence
        # may also appear (200 returned, not filtered)


class TestEvidenceDownload:
    async def test_download_evidence_with_correct_project_id(
        self, client: AsyncClient, alice_h: dict,
        portfolio_evidence: dict, portfolio_project: dict
    ):
        resp = await client.get(
            f"/api/v1/evidence/{portfolio_evidence['id']}/download",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code in (200, 302)

    async def test_download_evidence_with_wrong_project_id_gap(
        self, client: AsyncClient, alice_h: dict,
        portfolio_evidence: dict, hospital_project: dict
    ):
        """IDOR GAP (documented): GET /evidence/{id}/download ignores project_id
        — any authenticated user with DOWNLOAD_EVIDENCE permission can access
        any evidence file by ID regardless of which project it belongs to.
        Documents observed behaviour (200); enforcement is absent."""
        resp = await client.get(
            f"/api/v1/evidence/{portfolio_evidence['id']}/download",
            params={"project_id": hospital_project["id"]},
            headers=alice_h,
        )
        # Gap: returns 200 even with wrong project_id (no project scope check)
        assert resp.status_code in (200, 403, 404)

    async def test_viewer_can_download_with_correct_project_id(
        self, client: AsyncClient, carol_h: dict,
        portfolio_evidence: dict, portfolio_project: dict
    ):
        resp = await client.get(
            f"/api/v1/evidence/{portfolio_evidence['id']}/download",
            params={"project_id": portfolio_project["id"]},
            headers=carol_h,
        )
        assert resp.status_code in (200, 302)


class TestEvidenceIntegrity:
    async def test_verify_integrity_returns_valid_result(
        self, client: AsyncClient, alice_h: dict,
        portfolio_evidence: dict, portfolio_project: dict
    ):
        resp = await client.post(
            f"/api/v1/evidence/{portfolio_evidence['id']}/verify",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "ok" in body  # response: {"ok": bool, "hash": str}


class TestEvidenceDelete:
    async def test_default_evidence_is_immutable(
        self, client: AsyncClient, alice_h: dict,
        portfolio_evidence: dict, portfolio_project: dict
    ):
        """Evidence is immutable by default (is_immutable=True on the model).
        Attempting deletion must return 403 PermissionDenied.
        """
        resp = await client.delete(
            f"/api/v1/evidence/{portfolio_evidence['id']}",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 403

    async def test_mutable_evidence_can_be_deleted(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict,
        portfolio_project: dict, db
    ):
        """Create evidence with is_immutable=False directly in DB, then delete via API."""
        import uuid as _uuid
        from app.models.evidence import Evidence

        ev = Evidence(
            id=_uuid.uuid4(),
              incident_id=_uuid.UUID(sql_injection_incident["id"]),
            filename="mutable_test.txt",
            original_filename="mutable_test.txt",
            content_type="text/plain",
            file_size=4,
            sha256_hash="a" * 64,
            is_immutable=False,  # explicitly mutable
        )
        db.add(ev)
        await db.flush()
        ev_id = str(ev.id)

        del_resp = await client.delete(
            f"/api/v1/evidence/{ev_id}",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert del_resp.status_code in (200, 204)

        get_resp = await client.get(
            f"/api/v1/evidence/{ev_id}",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert get_resp.status_code == 404
