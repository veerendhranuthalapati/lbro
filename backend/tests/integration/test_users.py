"""User management router integration tests (admin-only CRUD)."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


class TestUserList:
    async def test_admin_can_list_users(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.get("/api/v1/users", headers=h)
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
        assert "total" in body
        assert body["total"] >= 1  # at least admin_user

    async def test_analyst_cannot_list_users(
        self, client: AsyncClient, analyst_token: str, analyst_user
    ):
        resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert resp.status_code == 403

    async def test_list_users_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/users")
        assert resp.status_code == 401


class TestUserCreate:
    async def test_admin_can_create_user(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = await client.post("/api/v1/users", json={
            "email": "newuser@test.com",
            "username": "newuser",
            "full_name": "New User",
            "password": "NewUser123!",
            "role": "analyst",
        }, headers=h)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "newuser@test.com"
        assert body["role"] == "analyst"
        assert "id" in body

    async def test_duplicate_email_returns_409(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "email": "dup@test.com",
            "username": "dupuser",
            "full_name": "Dup",
            "password": "Dup123!456",
            "role": "viewer",
        }
        await client.post("/api/v1/users", json=payload, headers=h)
        # Second attempt with same email but different username
        payload2 = dict(payload, username="dupuser2")
        resp = await client.post("/api/v1/users", json=payload2, headers=h)
        assert resp.status_code == 409

    async def test_duplicate_username_returns_409(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        payload = {
            "email": "unique1@test.com",
            "username": "sameusername",
            "full_name": "User One",
            "password": "Pass123!456",
            "role": "viewer",
        }
        await client.post("/api/v1/users", json=payload, headers=h)
        payload2 = dict(payload, email="unique2@test.com")
        resp = await client.post("/api/v1/users", json=payload2, headers=h)
        assert resp.status_code == 409

    async def test_non_admin_cannot_create_user(
        self, client: AsyncClient, analyst_token: str, analyst_user
    ):
        resp = await client.post("/api/v1/users", json={
            "email": "blocked@test.com",
            "username": "blocked",
            "full_name": "Blocked",
            "password": "Blocked123!",
            "role": "viewer",
        }, headers={"Authorization": f"Bearer {analyst_token}"})
        assert resp.status_code == 403


class TestUserGetAndUpdate:
    async def test_get_user_by_id(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        # Create then get
        create = await client.post("/api/v1/users", json={
            "email": "getme@test.com",
            "username": "getme",
            "full_name": "Get Me",
            "password": "GetMe123!",
            "role": "viewer",
        }, headers=h)
        uid = create.json()["id"]

        resp = await client.get(f"/api/v1/users/{uid}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["id"] == uid

    async def test_get_nonexistent_user_returns_404(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        resp = await client.get(
            f"/api/v1/users/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    async def test_patch_user_full_name(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/users", json={
            "email": "patchme@test.com",
            "username": "patchme",
            "full_name": "Old Name",
            "password": "PatchMe123!",
            "role": "viewer",
        }, headers=h)
        uid = create.json()["id"]

        resp = await client.patch(f"/api/v1/users/{uid}", json={"full_name": "New Name"}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "New Name"

    async def test_patch_user_role_change_audited(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        """Role change succeeds; audit log is created (no assertion on audit log here)."""
        h = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/users", json={
            "email": "rolechange@test.com",
            "username": "rolechange",
            "full_name": "Role Change",
            "password": "RoleChange123!",
            "role": "viewer",
        }, headers=h)
        uid = create.json()["id"]

        resp = await client.patch(f"/api/v1/users/{uid}", json={"role": "analyst"}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["role"] == "analyst"


class TestUserDelete:
    async def test_admin_can_delete_user(
        self, client: AsyncClient, admin_token: str, admin_user
    ):
        h = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/users", json={
            "email": "deleteme@test.com",
            "username": "deleteme",
            "full_name": "Delete Me",
            "password": "DeleteMe123!",
            "role": "viewer",
        }, headers=h)
        uid = create.json()["id"]

        resp = await client.delete(f"/api/v1/users/{uid}", headers=h)
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/v1/users/{uid}", headers=h)
        assert get_resp.status_code == 404

    async def test_non_admin_cannot_delete_user(
        self, client: AsyncClient, admin_token: str, analyst_token: str, admin_user, analyst_user
    ):
        ah = {"Authorization": f"Bearer {admin_token}"}
        create = await client.post("/api/v1/users", json={
            "email": "cantdelete@test.com",
            "username": "cantdelete",
            "full_name": "Cant Delete",
            "password": "CantDelete123!",
            "role": "viewer",
        }, headers=ah)
        uid = create.json()["id"]

        resp = await client.delete(
            f"/api/v1/users/{uid}",
            headers={"Authorization": f"Bearer {analyst_token}"},
        )
        assert resp.status_code == 403
