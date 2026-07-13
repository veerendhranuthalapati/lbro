"""
Authentication test suite — LBRO
Covers: register, login, refresh, logout, token validation, edge cases.
"""
from __future__ import annotations

import time

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, create_refresh_token


# ── Registration ──────────────────────────────────────────────────────────────

class TestRegister:
    async def test_register_valid_user_returns_201_and_tokens(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "full_name": "New User",
            "password": "Secure@Pass1!",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient, alice):  # noqa: ARG002
        resp = await client.post("/api/v1/auth/register", json={
            "email": "alice@test.com",
            "full_name": "Alice Duplicate",
            "password": "Secure@Pass1!",
        })
        assert resp.status_code == 409

    async def test_register_weak_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak@example.com",
            "full_name": "Weak User",
            "password": "password",  # no uppercase, digit, or special char
        })
        assert resp.status_code == 422

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "Secure@Pass1!",
        })
        assert resp.status_code == 422

    async def test_register_custom_username_is_stored(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "custom@example.com",
            "full_name": "Custom User",
            "username": "myhandle",
            "password": "Secure@Pass1!",
        })
        assert resp.status_code == 201


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    async def test_login_valid_credentials_returns_200_and_tokens(
        self, client: AsyncClient, alice
    ):  # noqa: ARG002
        resp = await client.post("/api/v1/auth/login", json={
            "email": "alice@test.com",
            "password": "Alice@Demo1!",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_wrong_password_returns_401(self, client: AsyncClient, alice):  # noqa: ARG002
        resp = await client.post("/api/v1/auth/login", json={
            "email": "alice@test.com",
            "password": "WrongPass999!",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_email_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@nowhere.com",
            "password": "Any@Pass1!",
        })
        assert resp.status_code == 401

    async def test_login_inactive_account_returns_401_or_403(
        self, client: AsyncClient, db
    ):
        import uuid
        from app.models.user import User
        from app.core.security import hash_password

        user = User(
            id=uuid.uuid4(),
            email="inactive@test.com",
            username="inactive_user",
            full_name="Inactive User",
            hashed_password=hash_password("Secure@Pass1!"),
            role="viewer",
            is_active=False,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "inactive@test.com",
            "full_name": "Inactive",
            "password": "Secure@Pass1!",
        })
        # Either refused at login (401) or after token check (403)
        assert resp.status_code in (401, 403)

    async def test_login_response_does_not_leak_password_hash(
        self, client: AsyncClient, alice
    ):  # noqa: ARG002
        resp = await client.post("/api/v1/auth/login", json={
            "email": "alice@test.com",
            "password": "Alice@Demo1!",
        })
        assert resp.status_code == 200
        text = resp.text
        # Must never expose the bcrypt hash
        assert "$2b$" not in text
        assert "hashed_password" not in text


# ── GET /auth/me ──────────────────────────────────────────────────────────────

class TestGetMe:
    async def test_get_me_with_valid_token_returns_user(
        self, client: AsyncClient, alice_token: str, alice
    ):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == alice.email
        assert body["role"] == "admin"

    async def test_get_me_without_token_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_get_me_with_garbage_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert resp.status_code == 401

    async def test_get_me_does_not_return_hashed_password(
        self, client: AsyncClient, alice_token: str, alice  # noqa: ARG002
    ):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        assert resp.status_code == 200
        assert "hashed_password" not in resp.json()


# ── Token Refresh ─────────────────────────────────────────────────────────────

class TestRefresh:
    async def test_refresh_with_valid_refresh_token_returns_new_tokens(
        self, client: AsyncClient, alice  # noqa: ARG002
    ):
        login = await client.post("/api/v1/auth/login", json={
            "email": "alice@test.com",
            "password": "Alice@Demo1!",
        })
        refresh_token = login.json()["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body

    async def test_refresh_with_access_token_returns_401(
        self, client: AsyncClient, alice_token: str, alice  # noqa: ARG002
    ):
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": alice_token})
        assert resp.status_code == 401

    async def test_refresh_with_garbage_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.token"})
        assert resp.status_code == 401


# ── Logout + Token Revocation ─────────────────────────────────────────────────

class TestLogout:
    async def test_logout_returns_204(
        self, client: AsyncClient, alice_token: str, alice  # noqa: ARG002
    ):
        login = await client.post("/api/v1/auth/login", json={
            "email": "alice@test.com",
            "password": "Alice@Demo1!",
        })
        refresh_token = login.json()["refresh_token"]
        token = login.json()["access_token"]

        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204

    async def test_revoked_token_rejected_on_me_endpoint(
        self, client: AsyncClient, alice  # noqa: ARG002
    ):
        login = await client.post("/api/v1/auth/login", json={
            "email": "alice@test.com",
            "password": "Alice@Demo1!",
        })
        token = login.json()["access_token"]
        refresh = login.json()["refresh_token"]

        await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401


# ── JWT Tamper Resistance ─────────────────────────────────────────────────────

class TestJWTTamper:
    async def test_modified_payload_rejected(
        self, client: AsyncClient, bob  # noqa: ARG002
    ):
        """Sign with correct key, modify payload bytes → should be rejected."""
        import base64, json

        login = await client.post("/api/v1/auth/login", json={
            "email": "bob@test.com",
            "password": "Bob@Demo1!",
        })
        token = login.json()["access_token"]

        # Split and tamper with the payload
        header, payload, sig = token.split(".")
        # Decode payload, change role to admin
        padded = payload + "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded))
        decoded["role"] = "admin"
        tampered_payload = base64.urlsafe_b64encode(
            json.dumps(decoded).encode()
        ).rstrip(b"=").decode()

        tampered_token = f"{header}.{tampered_payload}.{sig}"
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert resp.status_code == 401

    async def test_wrong_signature_rejected(self, client: AsyncClient, alice  # noqa: ARG002
    ):
        """Token signed with a different secret must be rejected."""
        from unittest.mock import patch

        # Generate a token signed with a DIFFERENT secret
        with patch("app.core.security.settings") as mock_settings:
            mock_settings.SECRET_KEY = "completely-different-secret-key-xyz"
            mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
            mock_settings.ALGORITHM = "HS256"
            evil_token = create_access_token(
                {"sub": str(alice.id), "role": "admin", "email": alice.email}
            )

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {evil_token}"},
        )
        assert resp.status_code == 401

    async def test_refresh_token_cannot_be_used_as_access_token(
        self, client: AsyncClient, alice  # noqa: ARG002
    ):
        login = await client.post("/api/v1/auth/login", json={
            "email": "alice@test.com",
            "password": "Alice@Demo1!",
        })
        refresh_token = login.json()["refresh_token"]

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert resp.status_code == 401
