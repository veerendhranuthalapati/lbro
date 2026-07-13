/**
 * LBRO App Router - lazy-loaded, error-bounded.
 *
 * Auth guard: ProtectedRoute wraps all authenticated routes.
 * Route-level permission guards are applied for admin-only pages.
 * Permission enforcement also happens on the backend.
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
const AuditLogsPage       = lazy(() => import('@/pages/AuditLogsPage'))
const SecurityScorePage   = lazy(() => import('@/pages/SecurityScorePage'))
const WeeklyReportPage    = lazy(() => import('@/pages/WeeklyReportPage'))
const PrivacyPage         = lazy(() => import('@/pages/PrivacyPage'))
const RoadmapPage         = lazy(() => import('@/pages/RoadmapPage'))
const ComplianceAuditPage = lazy(() => import('@/pages/ComplianceAuditPage'))
const WelcomePage            = lazy(() => import('@/pages/WelcomePage'))
const ProjectsPage           = lazy(() => import('@/pages/ProjectsPage'))
const ProjectOverviewPage    = lazy(() => import('@/pages/ProjectOverviewPage'))
const ProjectSettingsPage    = lazy(() => import('@/pages/ProjectSettingsPage'))
const ProjectSetupWizardPage = lazy(() => import('@/pages/ProjectSetupWizardPage'))
const IntegrationsPage       = lazy(() => import('@/pages/IntegrationsPage'))
const LiveEventsPage         = lazy(() => import('@/pages/LiveEventsPage'))
const ApiDocsPage            = lazy(() => import('@/pages/ApiDocsPage'))

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

      {/* Authenticated — full-screen (no AppLayout) */}
      <Route element={<ProtectedRoute />}>
        <Route path="/welcome"    element={<SuspenseRoute><WelcomePage /></SuspenseRoute>} />
        <Route path="/projects"   element={<SuspenseRoute><ProjectsPage /></SuspenseRoute>} />
        <Route path="/docs"       element={<SuspenseRoute><ApiDocsPage /></SuspenseRoute>} />
        <Route path="/projects/:projectId"               element={<SuspenseRoute><ProjectOverviewPage /></SuspenseRoute>} />
        <Route path="/projects/:projectId/setup"         element={<SuspenseRoute><ProjectSetupWizardPage /></SuspenseRoute>} />
        <Route path="/projects/:projectId/settings"      element={<SuspenseRoute><ProjectSettingsPage /></SuspenseRoute>} />
        <Route path="/projects/:projectId/integrations"  element={<SuspenseRoute><IntegrationsPage /></SuspenseRoute>} />
        <Route path="/projects/:projectId/events"        element={<SuspenseRoute><LiveEventsPage /></SuspenseRoute>} />
      </Route>

      {/* Authenticated — inside AppLayout */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />

          {/* ── Available to all authenticated users ── */}
          <Route path="/dashboard"      element={<SuspenseRoute><DashboardPage /></SuspenseRoute>} />
          <Route path="/incidents"      element={<SuspenseRoute><IncidentsPage /></SuspenseRoute>} />
          <Route path="/incidents/new"  element={<SuspenseRoute><CreateIncidentPage /></SuspenseRoute>} />
          <Route path="/incidents/:id"  element={<SuspenseRoute><IncidentDetailPage /></SuspenseRoute>} />
          <Route path="/evidence"       element={<SuspenseRoute><EvidencePage /></SuspenseRoute>} />
          <Route path="/notifications"  element={<SuspenseRoute><NotificationsPage /></SuspenseRoute>} />
          <Route path="/settings"       element={<SuspenseRoute><SettingsPage /></SuspenseRoute>} />
          <Route path="/privacy"        element={<SuspenseRoute><PrivacyPage /></SuspenseRoute>} />
          <Route path="/roadmap"        element={<SuspenseRoute><RoadmapPage /></SuspenseRoute>} />
          <Route path="/security-score" element={<SuspenseRoute><SecurityScorePage /></SuspenseRoute>} />
          <Route path="/weekly-report"  element={<SuspenseRoute><WeeklyReportPage /></SuspenseRoute>} />

          {/* ── Compliance — analyst + admin ── */}
          <Route path="/compliance" element={
            <ProtectedRoute requiredPermission={Permission.VIEW_COMPLIANCE}>
              <SuspenseRoute><CompliancePage /></SuspenseRoute>
            </ProtectedRoute>
          } />
          <Route path="/compliance/audit" element={
            <ProtectedRoute requiredPermission={Permission.VIEW_COMPLIANCE}>
              <SuspenseRoute><ComplianceAuditPage /></SuspenseRoute>
            </ProtectedRoute>
          } />

          {/* ── Infrastructure — analyst + admin ── */}
          <Route path="/infrastructure" element={
            <ProtectedRoute requiredPermission={Permission.VIEW_INFRASTRUCTURE}>
              <SuspenseRoute><InfrastructurePage /></SuspenseRoute>
            </ProtectedRoute>
          } />

          {/* ── Threat Intel — analyst + admin ── */}
          <Route path="/threat-intel" element={
            <ProtectedRoute requiredPermission={Permission.READ_INCIDENT}>
              <SuspenseRoute><ThreatIntelPage /></SuspenseRoute>
            </ProtectedRoute>
          } />

          {/* ── ML Insights — analyst + admin ── */}
          <Route path="/ml-insights" element={
            <ProtectedRoute requiredPermission={Permission.VIEW_ML}>
              <SuspenseRoute><MLInsightsPage /></SuspenseRoute>
            </ProtectedRoute>
          } />

          {/* ── Audit Logs — admin only ── */}
          <Route path="/audit-logs" element={
            <ProtectedRoute requiredPermission={Permission.VIEW_AUDIT}>
              <SuspenseRoute><AuditLogsPage /></SuspenseRoute>
            </ProtectedRoute>
          } />

          {/* ── User Management — admin only ── */}
          <Route path="/users" element={
            <ProtectedRoute requiredPermission={Permission.MANAGE_USERS}>
              <SuspenseRoute><UsersPage /></SuspenseRoute>
            </ProtectedRoute>
          } />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
