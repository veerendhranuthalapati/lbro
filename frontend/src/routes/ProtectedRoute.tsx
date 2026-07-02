/**
 * ProtectedRoute - guards routes by authentication and optionally by permission.
 *
 * Two usage patterns:
 *
 * 1. As a React Router route element (renders <Outlet />):
 *    <Route element={<ProtectedRoute />}>
 *      <Route path="/dashboard" element={<DashboardPage />} />
 *    </Route>
 *
 * 2. As a wrapper with children (renders children):
 *    <Route path="/users" element={
 *      <ProtectedRoute requiredPermission={Permission.MANAGE_USERS}>
 *        <SuspenseRoute><UsersPage /></SuspenseRoute>
 *      </ProtectedRoute>
 *    } />
 *
 * 401 -> redirect to /login
 * 403 -> render <Forbidden /> inline (user is authenticated but lacks access)
 */
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { usePermissions } from '@/hooks/usePermissions'
import type { PermissionValue } from '@/types/rbac'

interface ProtectedRouteProps {
  /** If provided, the user must hold this permission to access the route. */
  requiredPermission?: PermissionValue
  /** Optional children -- if omitted, renders <Outlet /> instead. */
  children?: React.ReactNode
}

function Forbidden() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60vh', gap: 12 }}>
      <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 72, color: '#e54e1b', lineHeight: 1 }}>403</span>
      <p style={{ fontSize: 13, color: '#6b6560' }}>You don't have permission to access this page.</p>
    </div>
  )
}

export function ProtectedRoute({ requiredPermission, children }: ProtectedRouteProps = {}) {
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)
  const { can } = usePermissions()

  // Not authenticated -> login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  // Authenticated but missing required permission -> 403 page
  if (requiredPermission && !can(requiredPermission)) {
    return <Forbidden />
  }

  // Render children if provided, otherwise render <Outlet /> for React Router nesting
  return children ? <>{children}</> : <Outlet />
}
