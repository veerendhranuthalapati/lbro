/**
 * LBRO App Router - lazy-loaded, error-bounded.
 *
 * Auth guard: ProtectedRoute wraps all authenticated routes.
 * All authenticated pages are accessible to any logged-in user.
 * Permission enforcement happens on the backend.
 */
import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/layouts/AppLayout'
import { ProtectedRoute } from '@/routes/ProtectedRoute'
import { ErrorBoundary } from '@/components/ui/ErrorBoundary'
import { Skeleton } from '@/components/ui/Skeleton'

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
const AuditLogsPage       = lazy(() => import('@/pages/AuditLogsPage'))

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

      {/* Authenticated - any logged-in user can access all pages */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard"      element={<SuspenseRoute><DashboardPage /></SuspenseRoute>} />
          <Route path="/incidents"      element={<SuspenseRoute><IncidentsPage /></SuspenseRoute>} />
          {/* /incidents/new MUST come before /incidents/:id */}
          <Route path="/incidents/new"  element={<SuspenseRoute><CreateIncidentPage /></SuspenseRoute>} />
          <Route path="/incidents/:id"  element={<SuspenseRoute><IncidentDetailPage /></SuspenseRoute>} />
          <Route path="/compliance"     element={<SuspenseRoute><CompliancePage /></SuspenseRoute>} />
          <Route path="/evidence"       element={<SuspenseRoute><EvidencePage /></SuspenseRoute>} />
          <Route path="/infrastructure" element={<SuspenseRoute><InfrastructurePage /></SuspenseRoute>} />
          <Route path="/threat-intel"   element={<SuspenseRoute><ThreatIntelPage /></SuspenseRoute>} />
          <Route path="/settings"       element={<SuspenseRoute><SettingsPage /></SuspenseRoute>} />
          <Route path="/notifications"  element={<SuspenseRoute><NotificationsPage /></SuspenseRoute>} />
          <Route path="/users"          element={<SuspenseRoute><UsersPage /></SuspenseRoute>} />
          <Route path="/ml-insights"    element={<SuspenseRoute><MLInsightsPage /></SuspenseRoute>} />
          <Route path="/audit-logs"     element={<SuspenseRoute><AuditLogsPage /></SuspenseRoute>} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
