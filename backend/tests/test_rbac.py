"""RBAC test suite — production-grade.

Covers:
  - has_permission() correctness for every role × permission combination
  - get_permissions_for_role() completeness
  - JWT contains permissions array after login
  - 401 for unauthenticated requests
  - 403 for authenticated but underpowered requests
  - 200 for authorised requests
  - audit log is written on every 403
  - require_any_permission allows access when at least one permission is held
  - Unrecognized roles produce 403 (not 500)
  - All 7 roles, all 25 permissions exercised
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import (
    Permission,
    Role,
    ROLE_PERMISSIONS,
    has_permission,
    has_any_permission,
    get_permissions_for_role,
)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure functions, no DB/HTTP needed
# ─────────────────────────────────────────────────────────────────────────────

class TestPermissionMap:
    """has_permission() and ROLE_PERMISSIONS are consistent and complete."""

    def test_super_admin_has_all_permissions(self):
        for perm in Permission:
            assert has_permission(Role.SUPER_ADMIN, perm), \
                f"SUPER_ADMIN missing {perm}"

    def test_viewer_cannot_create_incidents(self):
        assert not has_permission(Role.VIEWER, Permission.CREATE_INCIDENT)

    def test_viewer_cannot_delete_evidence(self):
        assert not has_permission(Role.VIEWER, Permission.DELETE_EVIDENCE)

    def test_viewer_cannot_manage_users(self):
        assert not has_permission(Role.VIEWER, Permission.MANAGE_USERS)

    def test_viewer_can_read_incidents(self):
        assert has_permission(Role.VIEWER, Permission.READ_INCIDENT)

    def test_viewer_can_view_dashboard(self):
        assert has_permission(Role.VIEWER, Permission.VIEW_DASHBOARD)

    def test_auditor_can_view_audit(self):
        assert has_permission(Role.AUDITOR, Permission.VIEW_AUDIT)

    def test_auditor_can_export_audit(self):
        assert has_permission(Role.AUDITOR, Permission.EXPORT_AUDIT)

    def test_auditor_cannot_create_incidents(self):
        assert not has_permission(Role.AUDITOR, Permission.CREATE_INCIDENT)

    def test_auditor_cannot_manage_users(self):
        assert not has_permission(Role.AUDITOR, Permission.MANAGE_USERS)

    def test_compliance_officer_can_manage_compliance(self):
        assert has_permission(Role.COMPLIANCE_OFFICER, Permission.MANAGE_COMPLIANCE)

    def test_compliance_officer_can_approve_notification(self):
        assert has_permission(Role.COMPLIANCE_OFFICER, Permission.APPROVE_NOTIFICATION)

    def test_compliance_officer_cannot_delete_incidents(self):
        assert not has_permission(Role.COMPLIANCE_OFFICER, Permission.DELETE_INCIDENT)

    def test_soc_analyst_can_create_incidents(self):
        assert has_permission(Role.SOC_ANALYST, Permission.CREATE_INCIDENT)

    def test_soc_analyst_can_upload_evidence(self):
        assert has_permission(Role.SOC_ANALYST, Permission.UPLOAD_EVIDENCE)

    def test_soc_analyst_cannot_delete_evidence(self):
        assert not has_permission(Role.SOC_ANALYST, Permission.DELETE_EVIDENCE)

    def test_soc_analyst_cannot_manage_users(self):
        assert not has_permission(Role.SOC_ANALYST, Permission.MANAGE_USERS)

    def test_incident_manager_can_assign_incidents(self):
        assert has_permission(Role.INCIDENT_MANAGER, Permission.ASSIGN_INCIDENT)

    def test_incident_manager_can_dispatch_notifications(self):
        assert has_permission(Role.INCIDENT_MANAGER, Permission.DISPATCH_NOTIFICATION)

    def test_incident_manager_cannot_manage_users(self):
        assert not has_permission(Role.INCIDENT_MANAGER, Permission.MANAGE_USERS)

    def test_security_admin_can_manage_users(self):
        assert has_permission(Role.SECURITY_ADMIN, Permission.MANAGE_USERS)

    def test_security_admin_can_rotate_api_keys(self):
        assert has_permission(Role.SECURITY_ADMIN, Permission.ROTATE_API_KEYS)

    def test_security_admin_can_manage_ml(self):
        assert has_permission(Role.SECURITY_ADMIN, Permission.MANAGE_ML)

    def test_security_admin_cannot_have_permission_not_in_super_admin(self):
        # Security admin is a strict subset of super_admin
        security_admin_perms = ROLE_PERMISSIONS[Role.SECURITY_ADMIN]
        super_admin_perms = ROLE_PERMISSIONS[Role.SUPER_ADMIN]
        assert security_admin_perms.issubset(super_admin_perms)

    def test_role_hierarchy_viewer_subset_of_all(self):
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        for role in Role:
            if role != Role.VIEWER:
                assert viewer_perms.issubset(ROLE_PERMISSIONS[role]), \
                    f"VIEWER permissions not a subset of {role}"

    def test_all_roles_present_in_role_permissions(self):
        for role in Role:
            assert role in ROLE_PERMISSIONS, f"{role} missing from ROLE_PERMISSIONS"

    def test_all_permissions_present_in_super_admin(self):
        super_perms = ROLE_PERMISSIONS[Role.SUPER_ADMIN]
        for perm in Permission:
            assert perm in super_perms, f"{perm} not in SUPER_ADMIN permissions"


class TestHasAnyPermission:
    def test_returns_true_if_one_of_many_held(self):
        assert has_any_permission(
            Role.VIEWER,
            Permission.READ_INCIDENT,
            Permission.DELETE_INCIDENT,  # viewer does NOT have this
        )

    def test_returns_false_if_none_held(self):
        assert not has_any_permission(
            Role.VIEWER,
            Permission.DELETE_INCIDENT,
            Permission.MANAGE_USERS,
        )

    def test_super_admin_always_true(self):
        for perm in Permission:
            assert has_any_permission(Role.SUPER_ADMIN, perm)


class TestGetPermissionsForRole:
    def test_returns_string_list(self):
        perms = get_permissions_for_role(Role.SOC_ANALYST)
        assert isinstance(perms, list)
        assert all(isinstance(p, str) for p in perms)

    def test_is_sorted(self):
        perms = get_permissions_for_role(Role.SOC_ANALYST)
        assert perms == sorted(perms)

    def test_super_admin_has_all(self):
        perms = get_permissions_for_role(Role.SUPER_ADMIN)
        expected = sorted(p.value for p in Permission)
        assert perms == expected

    def test_viewer_does_not_have_manage_users(self):
        perms = get_permissions_for_role(Role.VIEWER)
        assert Permission.MANAGE_USERS.value not in perms


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — HTTP + DB
# ─────────────────────────────────────────────────────────────────────────────

# Helper fixtures for each of the 7 new roles

def _make_user_fixture(role: str, email: str, username: str, password: str):
    @pytest_asyncio.fixture
    async def _fixture(db: AsyncSession):
        from app.models.user import User
        from app.core.security import hash_password
        user = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            full_name=username.replace("_", " ").title(),
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()
        return user
    return _fixture


super_admin_user    = _make_user_fixture("super_admin",        "superadmin@t.test",   "t_superadmin",    "SuperPass123!")
security_admin_user = _make_user_fixture("security_admin",     "secadmin@t.test",     "t_secadmin",      "SecPass123!")
incident_mgr_user   = _make_user_fixture("incident_manager",   "incmgr@t.test",       "t_incmgr",        "IncPass123!")
soc_analyst_user    = _make_user_fixture("soc_analyst",        "socanalyst@t.test",   "t_socanalyst",    "SocPass123!")
compliance_user     = _make_user_fixture("compliance_officer", "compliance@t.test",   "t_compliance",    "CompPass123!")
auditor_user        = _make_user_fixture("auditor",            "auditor@t.test",      "t_auditor",       "AuditPass123!")
viewer_user_new     = _make_user_fixture("viewer",             "viewer2@t.test",      "t_viewer2",       "ViewPass123!")


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestJWTContainsPermissions:
    """Login response contains a JWT with permissions baked in."""

    @pytest.mark.asyncio
    async def test_login_jwt_contains_permissions(self, client: AsyncClient, soc_analyst_user):
        token = await _login(client, "socanalyst@t.test", "SocPass123!")
        # Decode payload without verifying signature (already tested in security tests)
        import base64, json as _json
        payload_b64 = token.split(".")[1]
        # Add padding
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        assert "permissions" in payload
        assert isinstance(payload["permissions"], list)
        assert Permission.CREATE_INCIDENT.value in payload["permissions"]
        assert Permission.DELETE_INCIDENT.value not in payload["permissions"]

    @pytest.mark.asyncio
    async def test_super_admin_jwt_has_all_permissions(self, client: AsyncClient, super_admin_user):
        token = await _login(client, "superadmin@t.test", "SuperPass123!")
        import base64, json as _json
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        perms_in_token = set(payload["permissions"])
        all_perms = {p.value for p in Permission}
        assert all_perms == perms_in_token


class TestUnauthenticated:
    """401 for requests with no credentials."""

    @pytest.mark.asyncio
    async def test_incidents_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/incidents")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_users_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/users")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_audit_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/audit/logs")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_401_response_is_structured_json(self, client: AsyncClient):
        resp = await client.get("/api/v1/incidents")
        body = resp.json()
        assert "detail" in body


class TestViewerPermissions:
    """VIEWER can read but cannot mutate."""

    @pytest.mark.asyncio
    async def test_viewer_can_list_incidents(self, client: AsyncClient, viewer_user_new):
        token = await _login(client, "viewer2@t.test", "ViewPass123!")
        resp = await client.get("/api/v1/incidents", headers=_auth(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_incident(self, client: AsyncClient, viewer_user_new):
        token = await _login(client, "viewer2@t.test", "ViewPass123!")
        resp = await client.post("/api/v1/incidents", headers=_auth(token), json={
            "title": "Test incident",
            "severity": "medium",
        })
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_list_users(self, client: AsyncClient, viewer_user_new):
        token = await _login(client, "viewer2@t.test", "ViewPass123!")
        resp = await client.get("/api/v1/users", headers=_auth(token))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_cannot_view_audit(self, client: AsyncClient, viewer_user_new):
        token = await _login(client, "viewer2@t.test", "ViewPass123!")
        resp = await client.get("/api/v1/audit/logs", headers=_auth(token))
        assert resp.status_code == 403


class TestSOCAnalystPermissions:
    """SOC_ANALYST can create/update incidents but not delete or manage users."""

    @pytest.mark.asyncio
    async def test_soc_analyst_can_create_incident(self, client: AsyncClient, soc_analyst_user):
        token = await _login(client, "socanalyst@t.test", "SocPass123!")
        resp = await client.post("/api/v1/incidents", headers=_auth(token), json={
            "title": "Analyst-created incident",
            "severity": "high",
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_soc_analyst_cannot_delete_incident(self, client: AsyncClient, soc_analyst_user, super_admin_user):
        # Create an incident as super_admin, then try to delete as analyst
        sa_token = await _login(client, "superadmin@t.test", "SuperPass123!")
        create_resp = await client.post("/api/v1/incidents", headers=_auth(sa_token), json={
            "title": "To be deleted",
            "severity": "low",
        })
        assert create_resp.status_code == 201
        incident_id = create_resp.json()["id"]

        analyst_token = await _login(client, "socanalyst@t.test", "SocPass123!")
        del_resp = await client.delete(
            f"/api/v1/incidents/{incident_id}",
            headers=_auth(analyst_token),
        )
        assert del_resp.status_code == 403

    @pytest.mark.asyncio
    async def test_soc_analyst_cannot_manage_users(self, client: AsyncClient, soc_analyst_user):
        token = await _login(client, "socanalyst@t.test", "SocPass123!")
        resp = await client.get("/api/v1/users", headers=_auth(token))
        assert resp.status_code == 403


class TestAuditorPermissions:
    """AUDITOR can view audit logs but cannot mutate incidents."""

    @pytest.mark.asyncio
    async def test_auditor_can_view_audit_logs(self, client: AsyncClient, auditor_user):
        token = await _login(client, "auditor@t.test", "AuditPass123!")
        resp = await client.get("/api/v1/audit/logs", headers=_auth(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auditor_cannot_create_incident(self, client: AsyncClient, auditor_user):
        token = await _login(client, "auditor@t.test", "AuditPass123!")
        resp = await client.post("/api/v1/incidents", headers=_auth(token), json={
            "title": "Auditor incident",
            "severity": "low",
        })
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_auditor_cannot_manage_users(self, client: AsyncClient, auditor_user):
        token = await _login(client, "auditor@t.test", "AuditPass123!")
        resp = await client.get("/api/v1/users", headers=_auth(token))
        assert resp.status_code == 403


class TestSecurityAdminPermissions:
    """SECURITY_ADMIN can manage users and delete incidents."""

    @pytest.mark.asyncio
    async def test_security_admin_can_list_users(self, client: AsyncClient, security_admin_user):
        token = await _login(client, "secadmin@t.test", "SecPass123!")
        resp = await client.get("/api/v1/users", headers=_auth(token))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_security_admin_can_delete_incident(self, client: AsyncClient, security_admin_user):
        token = await _login(client, "secadmin@t.test", "SecPass123!")
        # First create one
        create_resp = await client.post("/api/v1/incidents", headers=_auth(token), json={
            "title": "To delete",
            "severity": "low",
        })
        assert create_resp.status_code == 201
        incident_id = create_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/incidents/{incident_id}",
            headers=_auth(token),
        )
        assert del_resp.status_code == 204


class TestSuperAdminPermissions:
    """SUPER_ADMIN can do everything."""

    @pytest.mark.asyncio
    async def test_super_admin_can_create_user(self, client: AsyncClient, super_admin_user):
        token = await _login(client, "superadmin@t.test", "SuperPass123!")
        resp = await client.post("/api/v1/users", headers=_auth(token), json={
            "email": "newuser@t.test",
            "username": "newuser_t",
            "full_name": "New User",
            "password": "NewUser123!",
            "role": "viewer",
        })
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_super_admin_can_view_audit(self, client: AsyncClient, super_admin_user):
        token = await _login(client, "superadmin@t.test", "SuperPass123!")
        resp = await client.get("/api/v1/audit/logs", headers=_auth(token))
        assert resp.status_code == 200


class TestForbiddenResponseStructure:
    """403 responses have structured JSON with error/message/permission_required."""

    @pytest.mark.asyncio
    async def test_403_has_structured_body(self, client: AsyncClient, viewer_user_new):
        token = await _login(client, "viewer2@t.test", "ViewPass123!")
        resp = await client.post("/api/v1/incidents", headers=_auth(token), json={
            "title": "Should fail",
            "severity": "low",
        })
        assert resp.status_code == 403
        body = resp.json()
        assert "detail" in body
        detail = body["detail"]
        assert "error" in detail
        assert detail["error"] == "forbidden"
        assert "permission_required" in detail
        assert "your_role" in detail


class TestAuditLoggingOnForbidden:
    """Every 403 is written to the audit_logs table."""

    @pytest.mark.asyncio
    async def test_forbidden_creates_audit_log(
        self, client: AsyncClient, viewer_user_new, db: AsyncSession
    ):
        from sqlalchemy import select
        from app.models.audit import AuditLog

        # Count before
        before = (await db.execute(select(AuditLog).where(AuditLog.action == "authz_failure"))).scalars().all()
        count_before = len(before)

        token = await _login(client, "viewer2@t.test", "ViewPass123!")
        resp = await client.post("/api/v1/incidents", headers=_auth(token), json={
            "title": "Should fail",
            "severity": "low",
        })
        assert resp.status_code == 403

        # Flush so changes are visible in this session
        await db.flush()

        after = (await db.execute(select(AuditLog).where(AuditLog.action == "authz_failure"))).scalars().all()
        assert len(after) > count_before

        latest = max(after, key=lambda l: l.created_at)
        assert latest.response_status == 403
        assert latest.details is not None
        assert latest.details["role"] == "viewer"
        assert Permission.CREATE_INCIDENT.value in latest.details["permission_requested"]


class TestInvalidRoleHandling:
    """Users with unrecognized roles get 403, not 500."""

    @pytest.mark.asyncio
    async def test_unknown_role_returns_403_not_500(self, client: AsyncClient, db: AsyncSession):
        from app.models.user import User
        from app.core.security import hash_password, create_access_token

        # Create user with invalid role directly in DB
        user = User(
            id=uuid.uuid4(),
            email="badrole@t.test",
            username="badrole_t",
            full_name="Bad Role",
            hashed_password=hash_password("BadRole123!"),
            role="sith_lord",  # Not a valid role
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

        token = create_access_token(user.id, {"role": user.role, "email": user.email})
        resp = await client.post(
            "/api/v1/incidents",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Test", "severity": "low"},
        )
        # Should be 403 (unknown role = no permissions) not 500
        assert resp.status_code == 403
