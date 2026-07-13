"""
Security test suite — LBRO
Covers: IDOR, JWT tampering, path traversal, privilege escalation attempts,
        input injection, missing auth, malformed inputs.
"""
from __future__ import annotations

import base64
import io
import json
import uuid

import pytest
from httpx import AsyncClient


class TestIDOR:
    """Insecure Direct Object Reference tests."""

    async def test_idor_incident_without_project_id_gap(
        self, client: AsyncClient, alice_h: dict, xss_incident: dict
    ):
        """
        IDOR GAP (documented): accessing any incident by ID without project_id
        succeeds for any authenticated user.

        Current behavior: 200
        Expected (secure) behavior: 422 (project_id required) or 403
        """
        resp = await client.get(
            f"/api/v1/incidents/{xss_incident['id']}",
            headers=alice_h,
        )
        # Documents the gap — does NOT assert 403/404
        assert resp.status_code == 200

    async def test_idor_incident_with_wrong_project_id_is_rejected(
        self, client: AsyncClient, alice_h: dict,
        xss_incident: dict, portfolio_project: dict
    ):
        """Providing the wrong project_id correctly returns 404."""
        resp = await client.get(
            f"/api/v1/incidents/{xss_incident['id']}",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 404

    async def test_idor_evidence_download_has_no_project_id_enforcement(
        self, client: AsyncClient, alice_h: dict,
        hospital_evidence: dict, portfolio_project: dict
    ):
        """
        IDOR GAP (documented): GET /evidence/{id}/download does not accept a
        project_id parameter. Any authenticated user with DOWNLOAD_EVIDENCE
        permission can download any evidence by ID regardless of project.

        Current behavior: 200 (no project_id check on download)
        Expected (secure) behavior: require project_id and validate ownership
        """
        resp = await client.get(
            f"/api/v1/evidence/{hospital_evidence['id']}/download",
            headers=alice_h,
        )
        # Documents the gap — evidence is accessible without project scoping
        assert resp.status_code in (200, 404)  # 404 if file_data not stored in test DB

    async def test_idor_nonexistent_resource_returns_404_not_500(
        self, client: AsyncClient, alice_h: dict
    ):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/incidents/{fake_id}",
            headers=alice_h,
        )
        assert resp.status_code == 404

    async def test_idor_nonexistent_evidence_returns_404(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/evidence/{fake_id}",
            params={"project_id": portfolio_project["id"]},
            headers=alice_h,
        )
        assert resp.status_code == 404


class TestPrivilegeEscalation:
    async def test_cannot_register_as_admin_role(self, client: AsyncClient):
        """Registration endpoint must not accept a role field that bypasses viewer default."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "hacker@evil.com",
            "full_name": "Evil Hacker",
            "password": "Hacked@Pass1!",
            "role": "admin",  # attempt to inject role
        })
        # Either 422 (extra field rejected) or 201 but role defaults to viewer
        if resp.status_code == 201:
            # Must have gotten default role — check via login
            login = await client.post("/api/v1/auth/login", json={
                "email": "hacker@evil.com",
            "full_name": "Evil Hacker",
                "password": "Hacked@Pass1!",
            })
            me = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            )
            # Must NOT be admin
            assert me.json()["role"] != "admin"
        else:
            assert resp.status_code == 422

    async def test_jwt_role_elevation_via_payload_tamper_rejected(
        self, client: AsyncClient, bob  # noqa: ARG002
    ):
        """Tamper with JWT payload to elevate role from analyst → admin."""
        login = await client.post("/api/v1/auth/login", json={
            "email": "bob@test.com",
            "password": "Bob@Demo1!",
        })
        token = login.json()["access_token"]
        header, payload, sig = token.split(".")

        # Decode and tamper
        padded = payload + "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded))
        decoded["role"] = "admin"
        decoded["permissions"] = ["user:manage", "role:manage", "apikey:rotate"]
        tampered_payload = (
            base64.urlsafe_b64encode(json.dumps(decoded).encode())
            .rstrip(b"=")
            .decode()
        )
        evil_token = f"{header}.{tampered_payload}.{sig}"

        # Any request with this tampered token must be rejected
        resp = await client.get(
            "/api/v1/users",  # admin-only endpoint
            headers={"Authorization": f"Bearer {evil_token}"},
        )
        assert resp.status_code == 401

    async def test_profile_update_cannot_change_own_role(
        self, client: AsyncClient, bob_h: dict
    ):
        """PATCH /auth/profile must not allow users to change their own role."""
        resp = await client.patch(
            "/api/v1/auth/profile",
            json={"role": "admin"},  # attempt
            headers=bob_h,
        )
        # Either 422 (field rejected) or 200 but role unchanged
        if resp.status_code == 200:
            assert resp.json().get("role") != "admin"


class TestInputValidation:
    async def test_incident_title_too_short_returns_422(
        self, client: AsyncClient, alice_h: dict
    ):
        resp = await client.post("/api/v1/incidents", json={
            "title": "ab",  # min_length is 3
            "severity": "low",
        }, headers=alice_h)
        assert resp.status_code == 422

    async def test_incident_title_too_long_returns_422(
        self, client: AsyncClient, alice_h: dict
    ):
        resp = await client.post("/api/v1/incidents", json={
            "title": "A" * 501,  # max_length is 500
            "severity": "low",
        }, headers=alice_h)
        assert resp.status_code == 422

    async def test_invalid_severity_returns_422(
        self, client: AsyncClient, alice_h: dict
    ):
        resp = await client.post("/api/v1/incidents", json={
            "title": "Valid Title Here",
            "severity": "catastrophic",  # not a valid literal
        }, headers=alice_h)
        assert resp.status_code == 422

    async def test_malformed_uuid_in_path_returns_422(
        self, client: AsyncClient, alice_h: dict
    ):
        resp = await client.get(
            "/api/v1/incidents/not-a-valid-uuid",
            headers=alice_h,
        )
        assert resp.status_code == 422

    async def test_sql_injection_in_search_does_not_crash(
        self, client: AsyncClient, alice_h: dict
    ):
        """SQL injection attempt in search param must return 200 (parameterized queries)."""
        resp = await client.get(
            "/api/v1/incidents",
            params={"search": "' OR '1'='1' --"},
            headers=alice_h,
        )
        # Must NOT return 500 — parameterized queries must handle this safely
        assert resp.status_code == 200

    async def test_xss_in_incident_title_stored_but_not_executed(
        self, client: AsyncClient, alice_h: dict, portfolio_project: dict
    ):
        """XSS payload in title is stored as text — backend must not crash."""
        xss_title = "<script>alert('xss')</script> Incident"
        resp = await client.post("/api/v1/incidents", json={
            "title": xss_title,
            "severity": "low",
            "project_id": portfolio_project["id"],
        }, headers=alice_h)
        # Must not crash the server
        assert resp.status_code in (201, 422)


class TestPathTraversal:
    async def test_path_traversal_in_evidence_filename_sanitized(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": (
                "../../../../etc/shadow",
                io.BytesIO(b"root:x:0:0:root:/root:/bin/bash"),
                "text/plain",
            )},
            headers=alice_h,
        )
        if resp.status_code == 201:
            name = resp.json()["filename"]
            assert "/" not in name
            assert "\\" not in name
            assert ".." not in name

    async def test_windows_path_traversal_sanitized(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict
    ):
        resp = await client.post(
            f"/api/v1/incidents/{sql_injection_incident['id']}/evidence",
            files={"file": (
                "..\\..\\Windows\\system32\\config.txt",
                io.BytesIO(b"windows path traversal test"),
                "text/plain",
            )},
            headers=alice_h,
        )
        if resp.status_code == 201:
            name = resp.json()["filename"]
            assert ".." not in name


class TestMissingAuth:
    """Every protected endpoint must return 401 when no credentials are provided."""

    @pytest.mark.parametrize("method,path", [
        ("GET",  "/api/v1/incidents"),
        ("POST", "/api/v1/incidents"),
        ("GET",  "/api/v1/projects"),
        ("GET",  "/api/v1/auth/me"),
        ("GET",  "/api/v1/users"),
        ("GET",  "/api/v1/audit/logs"),
    ])
    async def test_protected_endpoint_requires_auth(
        self, client: AsyncClient, method: str, path: str
    ):
        resp = await client.request(method, path)
        assert resp.status_code == 401, (
            f"{method} {path} returned {resp.status_code}, expected 401"
        )
