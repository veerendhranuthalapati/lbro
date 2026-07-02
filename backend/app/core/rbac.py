"""Role-Based Access Control -- centralized permission map.

Rules:
  - Permission checks are the single source of truth; never use role-string comparisons.
  - `ROLE_PERMISSIONS` is the only place where role->permission mapping is defined.
  - `has_permission()` and the FastAPI dependency factories in dependencies.py consume this.
  - To add a role: extend Role enum + add entry in ROLE_PERMISSIONS.
  - To add a permission: extend Permission enum + assign to relevant roles.

Role hierarchy (highest to lowest):
  SUPER_ADMIN > SECURITY_ADMIN > INCIDENT_MANAGER > SOC_ANALYST
               > COMPLIANCE_OFFICER > AUDITOR > VIEWER
"""
from __future__ import annotations

from enum import Enum
from typing import Set


class Role(str, Enum):
    SUPER_ADMIN        = "super_admin"
    SECURITY_ADMIN     = "security_admin"
    INCIDENT_MANAGER   = "incident_manager"
    SOC_ANALYST        = "soc_analyst"
    COMPLIANCE_OFFICER = "compliance_officer"
    AUDITOR            = "auditor"
    VIEWER             = "viewer"


class Permission(str, Enum):
    # Incidents
    CREATE_INCIDENT = "incident:create"
    READ_INCIDENT   = "incident:read"
    UPDATE_INCIDENT = "incident:update"
    DELETE_INCIDENT = "incident:delete"
    ASSIGN_INCIDENT = "incident:assign"

    # Evidence
    UPLOAD_EVIDENCE   = "evidence:upload"
    DOWNLOAD_EVIDENCE = "evidence:download"
    DELETE_EVIDENCE   = "evidence:delete"

    # Reports
    GENERATE_REPORT = "report:generate"
    VIEW_REPORT     = "report:view"
    APPROVE_REPORT  = "report:approve"

    # Audit
    VIEW_AUDIT   = "audit:read"
    EXPORT_AUDIT = "audit:export"

    # Users & Roles
    MANAGE_USERS    = "user:manage"
    MANAGE_ROLES    = "role:manage"
    ROTATE_API_KEYS = "apikey:rotate"

    # Infrastructure
    VIEW_INFRASTRUCTURE = "infra:read"

    # ML
    VIEW_ML   = "ml:read"
    MANAGE_ML = "ml:manage"

    # Notifications
    READ_NOTIFICATION     = "notification:read"
    APPROVE_NOTIFICATION  = "notification:approve"
    DISPATCH_NOTIFICATION = "notification:dispatch"

    # Compliance
    VIEW_COMPLIANCE   = "compliance:read"
    MANAGE_COMPLIANCE = "compliance:manage"

    # System
    SYSTEM_SETTINGS = "system:settings"
    VIEW_DASHBOARD  = "dashboard:read"


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

_AUDITOR_PERMISSIONS: Set[Permission] = _VIEWER_PERMISSIONS | {
    Permission.VIEW_AUDIT,
    Permission.EXPORT_AUDIT,
}

_COMPLIANCE_OFFICER_PERMISSIONS: Set[Permission] = _AUDITOR_PERMISSIONS | {
    Permission.MANAGE_COMPLIANCE,
    Permission.APPROVE_NOTIFICATION,
    Permission.GENERATE_REPORT,
    Permission.APPROVE_REPORT,
}

_SOC_ANALYST_PERMISSIONS: Set[Permission] = _VIEWER_PERMISSIONS | {
    Permission.CREATE_INCIDENT,
    Permission.UPDATE_INCIDENT,
    Permission.UPLOAD_EVIDENCE,
    Permission.GENERATE_REPORT,
    Permission.VIEW_AUDIT,
    Permission.MANAGE_COMPLIANCE,
}

_INCIDENT_MANAGER_PERMISSIONS: Set[Permission] = _SOC_ANALYST_PERMISSIONS | {
    Permission.ASSIGN_INCIDENT,
    Permission.APPROVE_NOTIFICATION,
    Permission.DISPATCH_NOTIFICATION,
    Permission.VIEW_INFRASTRUCTURE,
    Permission.EXPORT_AUDIT,
    Permission.APPROVE_REPORT,
}

_SECURITY_ADMIN_PERMISSIONS: Set[Permission] = _INCIDENT_MANAGER_PERMISSIONS | {
    Permission.DELETE_INCIDENT,
    Permission.DELETE_EVIDENCE,
    Permission.MANAGE_USERS,
    Permission.ROTATE_API_KEYS,
    Permission.MANAGE_ML,
    Permission.MANAGE_ROLES,
    Permission.SYSTEM_SETTINGS,
}

ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.VIEWER:             _VIEWER_PERMISSIONS,
    Role.AUDITOR:            _AUDITOR_PERMISSIONS,
    Role.COMPLIANCE_OFFICER: _COMPLIANCE_OFFICER_PERMISSIONS,
    Role.SOC_ANALYST:        _SOC_ANALYST_PERMISSIONS,
    Role.INCIDENT_MANAGER:   _INCIDENT_MANAGER_PERMISSIONS,
    Role.SECURITY_ADMIN:     _SECURITY_ADMIN_PERMISSIONS,
    Role.SUPER_ADMIN:        set(Permission),  # all permissions -- never removed
}


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
