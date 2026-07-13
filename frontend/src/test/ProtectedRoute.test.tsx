/**
 * Tests for ProtectedRoute.
 *
 * ProtectedRoute behaviour (from src/routes/ProtectedRoute.tsx):
 *  - Not authenticated  → <Navigate to="/login" replace />
 *  - Authenticated, no requiredPermission → renders <Outlet /> or children
 *  - Authenticated, requiredPermission present and user has it → renders children
 *  - Authenticated, requiredPermission present and user lacks it → renders 403
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { render } from './utils'
import { ProtectedRoute } from '@/routes/ProtectedRoute'
import { useAuthStore } from '@/store/authStore'
import { Permission } from '@/types/rbac'
import type { AuthUser } from '@/types'
import type { Role } from '@/types/rbac'

function makeAdminUser(): AuthUser {
  return {
    id: '00000000-0000-4000-a000-000000000001' as AuthUser['id'],
    name: 'Arjun Mehta',
    email: 'admin@lbro.dev',
    role: 'admin' as Role,
    // admin has all permissions
    permissions: Object.values(Permission),
    last_login: null,
  }
}

function makeViewerUser(): AuthUser {
  return {
    id: '00000000-0000-4000-a000-000000000004' as AuthUser['id'],
    name: 'Carol Santos',
    email: 'carol@lbro.dev',
    role: 'viewer' as Role,
    // viewer only has dashboard:read
    permissions: ['dashboard:read'],
    last_login: null,
  }
}

beforeEach(() => {
  useAuthStore.getState().logout()
  useAuthStore.setState({ loginAttempts: 0, lockedUntil: null })
})

describe('ProtectedRoute', () => {
  describe('unauthenticated user', () => {
    it('redirects to /login when not authenticated', () => {
      // When the route redirects, MemoryRouter renders /login path content
      // but since we have no route for /login, we verify by checking absence of children
      render(
        <ProtectedRoute>
          <div data-testid="protected-content">Secret</div>
        </ProtectedRoute>,
        { initialEntries: ['/dashboard'] },
      )
      // The protected content must NOT be visible
      expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })
  })

  describe('authenticated user', () => {
    beforeEach(() => {
      useAuthStore.getState().login('tok', 'ref', makeAdminUser())
    })

    it('renders children when authenticated with no required permission', () => {
      render(
        <ProtectedRoute>
          <div data-testid="protected-content">Dashboard</div>
        </ProtectedRoute>,
      )
      expect(screen.getByTestId('protected-content')).toBeInTheDocument()
    })

    it('renders children when user has the required permission', () => {
      render(
        <ProtectedRoute requiredPermission={Permission.MANAGE_USERS}>
          <div data-testid="admin-panel">Admin Panel</div>
        </ProtectedRoute>,
      )
      expect(screen.getByTestId('admin-panel')).toBeInTheDocument()
    })
  })

  describe('authenticated viewer lacking permission', () => {
    beforeEach(() => {
      useAuthStore.getState().login('tok', 'ref', makeViewerUser())
    })

    it('renders the 403 Forbidden page when permission is missing', () => {
      render(
        <ProtectedRoute requiredPermission={Permission.MANAGE_USERS}>
          <div data-testid="admin-only">Admin Only</div>
        </ProtectedRoute>,
      )
      expect(screen.queryByTestId('admin-only')).not.toBeInTheDocument()
      // ProtectedRoute renders <Forbidden /> which has the "403" heading
      expect(screen.getByText('403')).toBeInTheDocument()
    })

    it('renders children for a permission the viewer does hold', () => {
      render(
        <ProtectedRoute requiredPermission={Permission.VIEW_DASHBOARD}>
          <div data-testid="dashboard">Dashboard</div>
        </ProtectedRoute>,
      )
      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
    })
  })
})
