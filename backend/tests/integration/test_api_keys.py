"""
API key test suite — LBRO
Covers: rotate, authenticate via key, revocation after rotation, inactive user rejection.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestApiKeyRotate:
    async def test_admin_can_rotate_api_key_returns_new_key(
        self, client: AsyncClient, alice_h: dict
    ):
        resp = await client.post("/api/v1/auth/api-key/rotate", headers=alice_h)
        assert resp.status_code == 200
        body = resp.json()
        # Response must include a new key value
        assert "api_key" in body or "key" in body or "api_key" in str(body)

    async def test_analyst_can_rotate_own_api_key(
        self, client: AsyncClient, bob_h: dict
    ):
        """Any authenticated user can rotate their own API key."""
        resp = await client.post("/api/v1/auth/api-key/rotate", headers=bob_h)
        assert resp.status_code == 200

    async def test_viewer_can_rotate_own_api_key(
        self, client: AsyncClient, carol_h: dict
    ):
        """Viewers can also rotate their own API key."""
        resp = await client.post("/api/v1/auth/api-key/rotate", headers=carol_h)
        assert resp.status_code == 200


class TestApiKeyAuthentication:
    async def test_authenticate_with_valid_api_key(
        self, client: AsyncClient, alice_h: dict
    ):
        # Rotate to get a fresh key
        rotate_resp = await client.post("/api/v1/auth/api-key/rotate", headers=alice_h)
        assert rotate_resp.status_code == 200

        body = rotate_resp.json()
        new_key = body.get("api_key") or body.get("key")
        assert new_key is not None, f"No api_key in response: {body}"

        # Use the API key to authenticate
        resp = await client.get(
            "/api/v1/incidents",
            headers={"X-API-Key": new_key},
        )
        assert resp.status_code == 200

    async def test_invalid_api_key_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/incidents",
            headers={"X-API-Key": "invalid-key-that-does-not-exist"},
        )
        assert resp.status_code == 401

    async def test_old_api_key_rejected_after_rotation(
        self, client: AsyncClient, alice_h: dict
    ):
        # First rotation — get initial key
        r1 = await client.post("/api/v1/auth/api-key/rotate", headers=alice_h)
        assert r1.status_code == 200
        body1 = r1.json()
        first_key = body1.get("api_key") or body1.get("key")
        assert first_key is not None

        # Second rotation — get new key
        r2 = await client.post("/api/v1/auth/api-key/rotate", headers=alice_h)
        assert r2.status_code == 200

        # First key must now be rejected
        resp = await client.get(
            "/api/v1/incidents",
            headers={"X-API-Key": first_key},
        )
        assert resp.status_code == 401

    async def test_api_key_for_inactive_user_rejected(
        self, client: AsyncClient, db, alice_h: dict
    ):
        import uuid
        from app.models.user import User
        from app.core.security import hash_password

        # Create a user with a known api_key
        test_key = "test-api-key-inactive-user-xyz123"
        inactive = User(
            id=uuid.uuid4(),
            email="inactive_key@test.com",
            username="inactive_key_user",
            full_name="Inactive Key User",
            hashed_password=hash_password("Pass@word1!"),
            role="viewer",
            is_active=False,
            is_verified=True,
            api_key=test_key,
        )
        db.add(inactive)
        await db.flush()

        resp = await client.get(
            "/api/v1/incidents",
            headers={"X-API-Key": test_key},
        )
        assert resp.status_code == 401


class TestApiKeyVsJWT:
    async def test_api_key_can_read_incidents(
        self, client: AsyncClient, alice_h: dict, sql_injection_incident: dict  # noqa: ARG002
    ):
        rotate_resp = await client.post("/api/v1/auth/api-key/rotate", headers=alice_h)
        body = rotate_resp.json()
        new_key = body.get("api_key") or body.get("key")
        assert new_key is not None

        resp = await client.get(
            "/api/v1/incidents",
            headers={"X-API-Key": new_key},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_jwt_and_api_key_both_authenticate_to_same_user(
        self, client: AsyncClient, alice_h: dict, alice
    ):
        rotate_resp = await client.post("/api/v1/auth/api-key/rotate", headers=alice_h)
        body = rotate_resp.json()
        new_key = body.get("api_key") or body.get("key")
        assert new_key is not None

        # /auth/me via Bearer JWT
        jwt_resp = await client.get("/api/v1/auth/me", headers=alice_h)
        assert jwt_resp.status_code == 200

        # /auth/me via API key
        key_resp = await client.get("/api/v1/auth/me", headers={"X-API-Key": new_key})
        assert key_resp.status_code == 200

        assert jwt_resp.json()["email"] == alice.email
        assert key_resp.json()["email"] == alice.email
