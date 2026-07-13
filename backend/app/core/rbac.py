"""Role-Based Access Control — two-level model.

Level 1 – Platform roles  (apply to the LBRO deployment itself)
  super_admin  — manages the entire platform; bypasses project restrictions

Level 2 – Project roles  (apply within a single Project)
  admin   > analyst > viewer

Role hierarchy:
  super_admin (platform)
      ↓
  admin (project)
      ↓
  analyst (project)
      ↓
  viewer (project)

Rules:
  - Permission checks are the single source of truth; never compare role strings.
  - ROLE_PERMISSIONS is the only place where role->permission mapping lives.
  - Super Admin holds every permission AND every platform permission.
  - has_permission() / has_any_permission() are consumed by dependencies.py.
  - is_super_admin() is used for platform-level bypass; every bypass is audit-logged.
"""
from __future__ import annotations

from enum import Enum
from typing import Set


class Role(str, Enum):
    # Platform level
    SUPER_ADMIN = "super_admin"
    # Project level
    ADMIN   = "admin"
    ANALYST = "analyst"
    VIEWER  = "viewer"


class Permission(str, Enum):
    # ── Incidents ──────────────────────────────────────────────────────────
    CREATE_INCIDENT = "incident:create"
    READ_INCIDENT   = "incident:read"
    UPDATE_INCIDENT = "incident:update"
    DELETE_INCIDENT = "incident:delete"
    ASSIGN_INCIDENT = "incident:assign"

    # ── Evidence ───────────────────────────────────────────────────────────
    UPLOAD_EVIDENCE   = "evidence:upload"
    DOWNLOAD_EVIDENCE = "evidence:download"
    DELETE_EVIDENCE   = "evidence:delete"

    # ── Reports ────────────────────────────────────────────────────────────
    GENERATE_REPORT = "report:generate"
    VIEW_REPORT     = "report:view"
    APPROVE_REPORT  = "report:approve"

    # ── Audit ──────────────────────────────────────────────────────────────
    VIEW_AUDIT   = "audit:read"
    EXPORT_AUDIT = "audit:export"

    # ── Users & Roles ──────────────────────────────────────────────────────
    MANAGE_USERS    = "user:manage"
    MANAGE_ROLES    = "role:manage"
    ROTATE_API_KEYS = "apikey:rotate"

    # ── Infrastructure ─────────────────────────────────────────────────────
    VIEW_INFRASTRUCTURE = "infra:read"

    # ── ML ────────────────────────────────────────────────────────────────
    VIEW_ML   = "ml:read"
    MANAGE_ML = "ml:manage"

    # ── Notifications ──────────────────────────────────────────────────────
    READ_NOTIFICATION     = "notification:read"
    APPROVE_NOTIFICATION  = "notification:approve"
    DISPATCH_NOTIFICATION = "notification:dispatch"

    # ── Compliance ─────────────────────────────────────────────────────────
    VIEW_COMPLIANCE   = "compliance:read"
    MANAGE_COMPLIANCE = "compliance:manage"

    # ── System ────────────────────────────────────────────────────────────
    SYSTEM_SETTINGS = "system:settings"
    VIEW_DASHBOARD  = "dashboard:read"

    # ── Platform-level (SUPER_ADMIN only) ─────────────────────────────────
    PLATFORM_VIEW_ALL       = "platform:view_all"    # read across all projects
    PLATFORM_MANAGE_USERS   = "platform:manage_users"  # create/disable/delete any user
    PLATFORM_MANAGE_PROJECTS = "platform:manage_projects"  # create/archive/delete any project
    PLATFORM_VIEW_AUDIT     = "platform:view_audit"  # view audit logs across all projects
    PLATFORM_SYSTEM_HEALTH  = "platform:system_health"  # Docker / API / ML health endpoints
    PLATFORM_ASSIGN_ROLES   = "platform:assign_roles"  # assign project admins


# ---------------------------------------------------------------------------
# Centralized role -> permission map.
# This is the ONLY place the role->permission relationship is defined.
# ---------------------------------------------------------------------------

_VIEWER_PERMISSIONS: Set[Permission] = {
    Permission.READ_INCIDENT,
    Permission.DOWNLOAD_EVIDENCE,
    Permission.VIEW_DASHBOARD,
    Permission.READ_NOTIFICATION,
    Permission.VIEW_COMPLIANCE,
    Permission.VIEW_REPORT,
    Permission.VIEW_ML,
}

_ANALYST_PERMISSIONS: Set[Permission] = _VIEWER_PERMISSIONS | {
    Permission.CREATE_INCIDENT,
    Permission.UPDATE_INCIDENT,
    Permission.ASSIGN_INCIDENT,
    Permission.UPLOAD_EVIDENCE,
    Permission.GENERATE_REPORT,
    Permission.APPROVE_REPORT,
    Permission.VIEW_AUDIT,
    Permission.EXPORT_AUDIT,
    Permission.APPROVE_NOTIFICATION,
    Permission.DISPATCH_NOTIFICATION,
    Permission.MANAGE_COMPLIANCE,
    Permission.VIEW_INFRASTRUCTURE,
}

ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.VIEWER:      _VIEWER_PERMISSIONS,
    Role.ANALYST:     _ANALYST_PERMISSIONS,
    Role.ADMIN:       set(Permission),      # every permission (project scope)
    Role.SUPER_ADMIN: set(Permission),      # every permission (platform + project)
}


def is_super_admin(role: str | Role) -> bool:
    """Return True iff *role* is the platform-level SUPER_ADMIN.

    Use this to gate platform-only routes.  Every call site must log the bypass.
    """
    try:
        return Role(role) == Role.SUPER_ADMIN
    except ValueError:
        return False


def has_permission(role: Role, permission: Permission) -> bool:
    """Return True iff *role* holds *permission*."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def has_any_permission(role: Role, *permissions: Permission) -> bool:
    """Return True iff *role* holds at least one of the given permissions."""
    held = ROLE_PERMISSIONS.get(role, set())
    return any(p in held for p in permissions)


def get_permissions_for_role(role: Role) -> list[str]:
    """Return sorted list of permission values for JWT embedding."""
    return sorted(p.value for p in ROLE_PERMISSIONS.get(role, set()))
