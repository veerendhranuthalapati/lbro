/**
 * RBAC hooks for the frontend.
 *
 * The JWT access token embeds a `permissions` array (string values from the
 * backend Permission enum).  The auth store stores the user object which
 * includes those permissions.  All permission checks go through here.
 *
 * Usage:
 *   const { can, role, permissions } = usePermissions()
 *   if (!can(Permission.CREATE_INCIDENT)) return <Forbidden />
 *
 *   // Or the boolean shortcut:
 *   const canCreate = useCan(Permission.CREATE_INCIDENT)
 */
import { useAuthStore } from '@/store/authStore'
import {
  Permission,
  type PermissionValue,
  type Role,
  ROLE_PERMISSIONS,
} from '@/types/rbac'

/** Internal: derive effective permissions from JWT claims + client-side map. */
function _effectivePermissions(
  jwtPermissions: readonly string[] | undefined,
  role: string | undefined,
): Set<PermissionValue> {
  // Super-admin always gets every permission — no JWT needed.
  if (role === 'admin') {
    return new Set(Object.values(Permission) as PermissionValue[])
  }
  // If the JWT carries permissions, use them as the ground truth.
  if (jwtPermissions && jwtPermissions.length > 0) {
    return new Set(jwtPermissions as PermissionValue[])
  }
  // Fallback: derive from role (useful immediately after a role change before re-login).
  if (role) {
    const rolePerms = ROLE_PERMISSIONS[role as Role]
    if (rolePerms) return new Set(rolePerms)
  }
  return new Set()
}

// ── Main hook ─────────────────────────────────────────────────────────────────

export interface UsePermissionsResult {
  /** The current user's role string (e.g. 'analyst'). Null if not logged in. */
  role: Role | null
  /** The full resolved permission set for this session. */
  permissions: Set<PermissionValue>
  /** True iff the user holds the given permission. */
  can: (permission: PermissionValue) => boolean
  /** True iff the user holds ALL of the given permissions. */
  canAll: (...permissions: PermissionValue[]) => boolean
  /** True iff the user holds at least one of the given permissions. */
  canAny: (...permissions: PermissionValue[]) => boolean
  /** True iff the user is authenticated at all. */
  isAuthenticated: boolean
}

export function usePermissions(): UsePermissionsResult {
  const user = useAuthStore(s => s.user)
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)

  const permissions = _effectivePermissions(
    user?.permissions as string[] | undefined,
    user?.role,
  )

  return {
    role: (user?.role ?? null) as Role | null,
    permissions,
    can:    (p) => permissions.has(p),
    canAll: (...ps) => ps.every(p => permissions.has(p)),
    canAny: (...ps) => ps.some(p => permissions.has(p)),
    isAuthenticated,
  }
}

// ── Convenience single-permission hook ───────────────────────────────────────

/**
 * Returns true iff the current user holds the given permission.
 *
 * @example
 *   const canManageUsers = useCan(Permission.MANAGE_USERS)
 *   <button disabled={!canManageUsers}>Create user</button>
 */
export function useCan(permission: PermissionValue): boolean {
  const { can } = usePermissions()
  return can(permission)
}

// Re-export Permission so callers only need to import from this file.
export { Permission, type PermissionValue, type Role }
