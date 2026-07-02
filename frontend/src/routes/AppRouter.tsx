/**
 * LBRO App Router - lazy-loaded, error-bounded, RBAC-guarded.
 *
 * Auth guard: ProtectedRoute wraps all authenticated routes.
 * Permission guards: sensitive routes nest inside a ProtectedRoute with
 *   requiredPermission. The backend enforces the same permissions;
 *   the frontend gate is supplemental UX only (shows 403 page instead of
 *   waiting for a backend 403 response).
 */
import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/layouts/AppLayout'
import { ProtectedRoute } from '@/routes/ProtectedRoute'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Skeleton } from '@/components/ui/Skeleton'
import { Permission } from '@/types/rbac'

// Eager-load auth pages (always needed immediately)
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import ForgotPasswordPage from '@/pages/ForgotPasswordPage'
import NotFoundPage from '@/pages/NotFoundPage'

// Route-based lazy loading -- each page gets its own chunk
const DashboardPage       = lazy(() => import('@/pages/DashboardPage'))
const IncidentsPage       = lazy(() => import('@/pages/IncidentsPage'))
const IncidentDetailPage  = lazy(() => import('@/pages/IncidentDetailPage'))
const CreateIncidentPage  = lazy(() => import('@/pages/CreateIncidentPage'))
const CompliancePage      = lazy(() => import('@/pages/CompliancePage'))
const EvidencePage        = lazy(() => import('@/pages/EvidencePage'))
const InfrastructurePage  = lazy(() => import('@/pages/InfrastructurePage'))
const ThreatIntelPage     = lazy(() => import('@/pages/ThreatIntelPage'))
const SettingsPage        = lazy(() => import('@/pages/SettingsPage'))
const NotificationsPage   = lazy(() => import('@/pages/NotificationsPage'))
const UsersPage           = lazy(() => import('@/pages/UsersPage'))
const MLInsightsPage      = lazy(() => import('@/pages/MLInsightsPage'))

function PageLoader() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Loading page content"
      style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 8 }}
    >
      <Skeleton height={28} width={208} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16 }}>
        {[0,1,2,3].map(i => <Skeleton key={i} height={96} />)}
      </div>
      <Skeleton height={256} />
      <span style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap' }}>Loading...</span>
    </div>
  )
}

function SuspenseRoute({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageLoader />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  )
}

export function AppRouter() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login"           element={<LoginPage />} />
      <Route path="/register"        element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />

      {/* Authenticated */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />

          {/* Dashboard - VIEW_DASHBOARD permission */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute requiredPermission={Permission.VIEW_DASHBOARD}>
                <SuspenseRoute><DashboardPage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />

          {/* Incidents - READ_INCIDENT permission */}
          <Route
            path="/incidents"
            element={
              <ProtectedRoute requiredPermission={Permission.READ_INCIDENT}>
                <SuspenseRoute><IncidentsPage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />
          {/* /incidents/new MUST come before /incidents/:id */}
          <Route
            path="/incidents/new"
            element={
              <ProtectedRoute requiredPermission={Permission.CREATE_INCIDENT}>
                <SuspenseRoute><CreateIncidentPage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />
          <Route
            path="/incidents/:id"
            element={
              <ProtectedRoute requiredPermission={Permission.READ_INCIDENT}>
                <SuspenseRoute><IncidentDetailPage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />

          {/* Compliance - VIEW_COMPLIANCE */}
          <Route
            path="/compliance"
            element={
              <ProtectedRoute requiredPermission={Permission.VIEW_COMPLIANCE}>
                <SuspenseRoute><CompliancePage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />

          {/* Evidence - DOWNLOAD_EVIDENCE */}
          <Route
            path="/evidence"
            element={
              <ProtectedRoute requiredPermission={Permission.DOWNLOAD_EVIDENCE}>
                <SuspenseRoute><EvidencePage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />

          {/* Infrastructure - VIEW_INFRASTRUCTURE */}
          <Route
            path="/infrastructure"
            element={
              <ProtectedRoute requiredPermission={Permission.VIEW_INFRASTRUCTURE}>
                <SuspenseRoute><InfrastructurePage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />

          {/* Threat intel - READ_INCIDENT */}
          <Route
            path="/threat-intel"
            element={
              <ProtectedRoute requiredPermission={Permission.READ_INCIDENT}>
                <SuspenseRoute><ThreatIntelPage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />

          {/* Settings - always visible once authenticated */}
          <Route
            path="/settings"
            element={<SuspenseRoute><SettingsPage /></SuspenseRoute>}
          />

          {/* Notifications - READ_NOTIFICATION */}
          <Route
            path="/notifications"
            element={
              <ProtectedRoute requiredPermission={Permission.READ_NOTIFICATION}>
                <SuspenseRoute><NotificationsPage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />

          {/* Users - MANAGE_USERS */}
          <Route
            path="/users"
            element={
              <ProtectedRoute requiredPermission={Permission.MANAGE_USERS}>
                <SuspenseRoute><UsersPage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />

          {/* ML Insights - VIEW_ML */}
          <Route
            path="/ml-insights"
            element={
              <ProtectedRoute requiredPermission={Permission.VIEW_ML}>
                <SuspenseRoute><MLInsightsPage /></SuspenseRoute>
              </ProtectedRoute>
            }
          />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
