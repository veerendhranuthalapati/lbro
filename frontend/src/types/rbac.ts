/**
 * Frontend RBAC types — mirrors backend app/core/rbac.py exactly.
 *
 * Permission values match what the backend emits in JWT `permissions` array.
 * Role values match what the backend stores in `users.role` column.
 *
 * RULE: never do `if (user.role === 'super_admin')`.
 *       Always use `useCan(Permission.MANAGE_USERS)` or `can(Permission.MANAGE_USERS)`.
 */

// ── Roles ─────────────────────────────────────────────────────────────────────
export const ROLES = {
  SUPER_ADMIN:        'super_admin',
  SECURITY_ADMIN:     'security_admin',
  INCIDENT_MANAGER:   'incident_manager',
  SOC_ANALYST:        'soc_analyst',
  COMPLIANCE_OFFICER: 'compliance_officer',
  AUDITOR:            'auditor',
  VIEWER:             'viewer',
} as const

export type Role = (typeof ROLES)[keyof typeof ROLES]

// ── Permissions ───────────────────────────────────────────────────────────────
// Values must match backend Permission enum `.value` strings.
export const Permission = {
  // Incidents
  CREATE_INCIDENT: 'incident:create',
  READ_INCIDENT:   'incident:read',
  UPDATE_INCIDENT: 'incident:update',
  DELETE_INCIDENT: 'incident:delete',
  ASSIGN_INCIDENT: 'incident:assign',

  // Evidence
  UPLOAD_EVIDENCE:   'evidence:upload',
  DOWNLOAD_EVIDENCE: 'evidence:download',
  DELETE_EVIDENCE:   'evidence:delete',

  // Reports
  GENERATE_REPORT: 'report:generate',
  VIEW_REPORT:     'report:view',
  APPROVE_REPORT:  'report:approve',

  // Audit
  VIEW_AUDIT:   'audit:read',
  EXPORT_AUDIT: 'audit:export',

  // Users & Roles
  MANAGE_USERS:    'user:manage',
  MANAGE_ROLES:    'role:manage',
  ROTATE_API_KEYS: 'apikey:rotate',

  // Infrastructure
  VIEW_INFRASTRUCTURE: 'infra:read',

  // ML
  VIEW_ML:   'ml:read',
  MANAGE_ML: 'ml:manage',

  // Notifications
  READ_NOTIFICATION:     'notification:read',
  APPROVE_NOTIFICATION:  'notification:approve',
  DISPATCH_NOTIFICATION: 'notification:dispatch',

  // Compliance
  VIEW_COMPLIANCE:   'compliance:read',
  MANAGE_COMPLIANCE: 'compliance:manage',

  // System
  SYSTEM_SETTINGS: 'system:settings',
  VIEW_DASHBOARD:  'dashboard:read',
} as const

export type PermissionValue = (typeof Permission)[keyof typeof Permission]

// ── Role display metadata ─────────────────────────────────────────────────────
export const ROLE_LABELS: Record<Role, string> = {
  super_admin:        'Super Admin',
  security_admin:     'Security Admin',
  incident_manager:   'Incident Manager',
  soc_analyst:        'SOC Analyst',
  compliance_officer: 'Compliance Officer',
  auditor:            'Auditor',
  viewer:             'Viewer',
}

// ── Client-side permission map ────────────────────────────────────────────────
// Mirrors ROLE_PERMISSIONS in backend/app/core/rbac.py.
// The JWT also carries the permissions list — this map is a fallback for
// roles with no JWT yet (e.g. immediately after a role change before re-login).
const _VIEWER: readonly PermissionValue[] = [
  Permission.READ_INCIDENT,
  Permission.DOWNLOAD_EVIDENCE,
  Permission.VIEW_DASHBOARD,
  Permission.READ_NOTIFICATION,
  Permission.VIEW_COMPLIANCE,
  Permission.VIEW_REPORT,
  Permission.VIEW_ML,
]

const _AUDITOR: readonly PermissionValue[] = [
  ..._VIEWER,
  Permission.VIEW_AUDIT,
  Permission.EXPORT_AUDIT,
]

const _COMPLIANCE_OFFICER: readonly PermissionValue[] = [
  ..._AUDITOR,
  Permission.MANAGE_COMPLIANCE,
  Permission.APPROVE_NOTIFICATION,
  Permission.GENERATE_REPORT,
  Permission.APPROVE_REPORT,
]

const _SOC_ANALYST: readonly PermissionValue[] = [
  ..._VIEWER,
  Permission.CREATE_INCIDENT,
  Permission.UPDATE_INCIDENT,
  Permission.UPLOAD_EVIDENCE,
  Permission.GENERATE_REPORT,
  Permission.VIEW_AUDIT,
  Permission.MANAGE_COMPLIANCE,
]

const _INCIDENT_MANAGER: readonly PermissionValue[] = [
  ..._SOC_ANALYST,
  Permission.ASSIGN_INCIDENT,
  Permission.APPROVE_NOTIFICATION,
  Permission.DISPATCH_NOTIFICATION,
  Permission.VIEW_INFRASTRUCTURE,
  Permission.EXPORT_AUDIT,
  Permission.APPROVE_REPORT,
]

const _SECURITY_ADMIN: readonly PermissionValue[] = [
  ..._INCIDENT_MANAGER,
  Permission.DELETE_INCIDENT,
  Permission.DELETE_EVIDENCE,
  Permission.MANAGE_USERS,
  Permission.ROTATE_API_KEYS,
  Permission.MANAGE_ML,
  Permission.MANAGE_ROLES,
  Permission.SYSTEM_SETTINGS,
]

const _ALL = Object.values(Permission) as PermissionValue[]

export const ROLE_PERMISSIONS: Record<Role, readonly PermissionValue[]> = {
  viewer:             _VIEWER,
  auditor:            _AUDITOR,
  compliance_officer: _COMPLIANCE_OFFICER,
  soc_analyst:        _SOC_ANALYST,
  incident_manager:   _INCIDENT_MANAGER,
  security_admin:     _SECURITY_ADMIN,
  super_admin:        _ALL,
}
