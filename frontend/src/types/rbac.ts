/**
 * Frontend RBAC types -- mirrors backend app/core/rbac.py exactly.
 *
 * 3 roles: admin > analyst > viewer
 * Permission values match what the backend emits in JWT `permissions` array.
 *
 * RULE: never do `if (user.role === 'admin')`.
 *       Always use `useCan(Permission.MANAGE_USERS)` instead.
 */

// ---- Roles ------------------------------------------------------------------
export const ROLES = {
  ADMIN:   'admin',
  ANALYST: 'analyst',
  VIEWER:  'viewer',
} as const

export type Role = (typeof ROLES)[keyof typeof ROLES]

// ---- Permissions ------------------------------------------------------------
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

// ---- Role display metadata --------------------------------------------------
export const ROLE_LABELS: Record<Role, string> = {
  admin:   'Admin',
  analyst: 'Analyst',
  viewer:  'Viewer',
}

// ---- Client-side permission map ---------------------------------------------
// Mirrors ROLE_PERMISSIONS in backend/app/core/rbac.py.
// The JWT carries the real permissions list; this is a local fallback.

const _VIEWER: readonly PermissionValue[] = [
  Permission.READ_INCIDENT,
  Permission.DOWNLOAD_EVIDENCE,
  Permission.VIEW_DASHBOARD,
  Permission.READ_NOTIFICATION,
  Permission.VIEW_COMPLIANCE,
  Permission.VIEW_REPORT,
  Permission.VIEW_ML,
]

const _ANALYST: readonly PermissionValue[] = [
  ..._VIEWER,
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
]

const _ALL = Object.values(Permission) as PermissionValue[]

export const ROLE_PERMISSIONS: Record<Role, readonly PermissionValue[]> = {
  viewer:  _VIEWER,
  analyst: _ANALYST,
  admin:   _ALL,
}
