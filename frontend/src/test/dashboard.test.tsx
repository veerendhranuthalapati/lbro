/**
 * Tests for DashboardPage.
 *
 * DashboardPage fetches:
 *   - GET /api/v1/dashboard/summary  → useDashboardSummary()
 *   - GET /api/v1/incidents          → useIncidents()
 *   - GET /api/v1/security-score     → useSecurityScore()
 *
 * MSW handlers for all three live in src/mocks/handlers/dashboard.ts,
 * incidents.ts, and a security-score handler.
 *
 * The page is authenticated-only. We set the auth store to a logged-in
 * state before rendering.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { render } from './utils'
import DashboardPage from '@/pages/DashboardPage'
import { useAuthStore } from '@/store/authStore'
import { server } from '../mocks/server'
import { MOCK_DASHBOARD } from '../mocks/data'
import type { AuthUser } from '@/types'
import type { Role } from '@/types/rbac'

function makeAdminUser(): AuthUser {
  return {
    id: '00000000-0000-4000-a000-000000000001' as AuthUser['id'],
    name: 'Arjun Mehta',
    email: 'admin@lbro.dev',
    role: 'admin' as Role,
    permissions: [],
    last_login: null,
  }
}

beforeEach(() => {
  useAuthStore.getState().logout()
  useAuthStore.getState().login('tok', 'ref', makeAdminUser())
})

describe('DashboardPage', () => {
  describe('loading state', () => {
    it('shows skeleton placeholders while data is loading', () => {
      // Render without waiting — MSW handlers have artificial delays
      render(<DashboardPage />)
      // The loading state shows '—' dashes in stat cards
      const dashes = screen.getAllByText('—')
      expect(dashes.length).toBeGreaterThan(0)
    })

    it('shows "Checking status…" before the health status resolves', () => {
      render(<DashboardPage />)
      expect(screen.getByText(/checking status/i)).toBeInTheDocument()
    })
  })

  describe('after data loads', () => {
    it('renders the user greeting with first name', async () => {
      render(<DashboardPage />)
      // The greeting uses user.name split on space → "Arjun"
      await waitFor(() => {
        expect(screen.getByText(/arjun/i)).toBeInTheDocument()
      }, { timeout: 5000 })
    })

    it('renders the stat cards with mock data values', async () => {
      render(<DashboardPage />)
      await waitFor(() => {
        // MOCK_DASHBOARD.new_last_24h = 1, critical_incidents = 2
        expect(screen.getByText(String(MOCK_DASHBOARD.new_last_24h))).toBeInTheDocument()
      }, { timeout: 5000 })
    })

    it('renders the "Recent Activity" section heading', async () => {
      render(<DashboardPage />)
      await waitFor(() => {
        expect(screen.getByText(/recent activity/i)).toBeInTheDocument()
      }, { timeout: 5000 })
    })

    it('renders the "Recommended Actions" section', async () => {
      render(<DashboardPage />)
      await waitFor(() => {
        expect(screen.getByText(/recommended actions/i)).toBeInTheDocument()
      }, { timeout: 5000 })
    })
  })

  describe('empty incidents state', () => {
    it('shows the empty state prompt when incidents list is empty', async () => {
      // Override the incidents endpoint to return an empty list
      server.use(
        http.get('/api/v1/incidents', () =>
          HttpResponse.json({ items: [], total: 0, page: 1, page_size: 12 }),
        ),
      )
      render(<DashboardPage />)
      await waitFor(() => {
        expect(screen.getByText(/no attacks detected yet/i)).toBeInTheDocument()
      }, { timeout: 5000 })
    })
  })

  describe('critical incidents banner', () => {
    it('shows the critical incidents banner when there are critical incidents', async () => {
      // Override the summary to have critical incidents
      server.use(
        http.get('/api/v1/dashboard/summary', () =>
          HttpResponse.json({ ...MOCK_DASHBOARD, critical_incidents: 3 }),
        ),
      )
      render(<DashboardPage />)
      await waitFor(() => {
        expect(screen.getByText(/3 critical incident/i)).toBeInTheDocument()
      }, { timeout: 5000 })
    })

    it('hides the critical banner when there are no critical incidents', async () => {
      server.use(
        http.get('/api/v1/dashboard/summary', () =>
          HttpResponse.json({ ...MOCK_DASHBOARD, critical_incidents: 0 }),
        ),
      )
      render(<DashboardPage />)
      await waitFor(() => {
        // Summary stat card "0" for critical should appear instead of the banner
        expect(screen.queryByText(/critical incident.*require immediate attention/i)).not.toBeInTheDocument()
      }, { timeout: 5000 })
    })
  })
})
