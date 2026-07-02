/**
 * Frontend RBAC helpers.
 *
 * The canonical permission map lives in types/rbac.ts.
 * This file re-exports the hooks and provides non-hook helpers for use
 * outside React components (e.g. in route loaders or utility functions).
 *
 * RULE: always check permissions, never role strings.
 */

import type { AuthUser } from '@/types'
import {
  Permission,
  type PermissionValue,
  type Role,
  ROLE_PERMISSIONS,
} from '@/types/rbac'

export { Permission, type PermissionValue, type Role }

// ── Non-hook permission helpers (for use outside React components) ────────────

/** Returns the effective permission set for an AuthUser. */
export function getPermissions(user: AuthUser | null): Set<PermissionValue> {
  if (!user) return new Set()
  // JWT-embedded permissions are ground truth.
  if (user.permissions && user.permissions.length > 0) {
    return new Set(user.permissions)
  }
  // Role-derived fallback.
  return new Set(ROLE_PERMISSIONS[user.role as Role] ?? [])
}

export function hasPermission(user: AuthUser | null, permission: PermissionValue): boolean {
  return getPermissions(user).has(permission)
}

export function hasAnyPermission(user: AuthUser | null, permissions: readonly PermissionValue[]): boolean {
  const held = getPermissions(user)
  return permissions.some(p => held.has(p))
}

export function hasAllPermissions(user: AuthUser | null, permissions: readonly PermissionValue[]): boolean {
  const held = getPermissions(user)
  return permissions.every(p => held.has(p))
}

// ── React hooks (re-exported from canonical location) ─────────────────────────
export { usePermissions, useCan } from '@/hooks/usePermissions'
