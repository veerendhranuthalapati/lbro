/**
 * LBRO React Query hooks -- typed, cache-optimised, wired to real backend endpoints.
 *
 * Endpoint availability:
 *  EXISTS:  /api/v1/incidents, /api/v1/dashboard/summary, /api/v1/notifications,
 *           /api/v1/compliance/dashboard, /api/v1/evidence (per-incident),
 *           /api/v1/users, /api/v1/ml/stats, /api/v1/ml/model-info,
 *           /api/v1/audit/logs, /api/v1/auth/me
 *  MISSING: /api/v1/infrastructure, /api/v1/ml/flows, /api/v1/ml/metrics,
 *           /api/v1/evidence (global), /api/v1/ml/classify (exists but no live feed)
 */
import {
  useQuery, useMutation, useQueryClient, useInfiniteQuery,
} from '@tanstack/react-query'
import {
  incidentsApi, evidenceApi, notificationsApi, healthApi,
  dashboardApi, complianceApi, usersApi, mlApi, auditLogsApi,
  infrastructureApi, authApi, securityScoreApi, reportsApi,
} from '@/api/client'
import type { DashboardSummary, ObligationCreate, ObligationUpdate } from '@/api/client'
import { debounce } from '@/lib/rateLimiter'
import { logger, auditAction } from '@/lib/logger'
import { useProjectStore } from '@/store/projectStore'
import {
  POLL_INCIDENTS_MS, POLL_NOTIFICATIONS_MS, POLL_HEALTH_MS,
  STALE_INCIDENTS_MS, STALE_EVIDENCE_MS, STALE_NOTIFICATIONS_MS, STALE_HEALTH_MS,
  DEFAULT_PAGE_SIZE,
} from '@/constants'
import type { IncidentCreate, IncidentUpdate, PagedIncidentResponse } from '@/types'
import { useCallback, useRef, useState } from 'react'
import { DEBOUNCE_SEARCH_MS } from '@/constants'

// ---- Query key factory ------------------------------------------------------
export const qk = {
  incidents: {
    all:      ['incidents'] as const,
    list:     (f: object) => ['incidents', 'list', f] as const,
    detail:   (id: string) => ['incidents', 'detail', id] as const,
    infinite: (f: object) => ['incidents', 'infinite', f] as const,
    stats:    (pid?: string) => ['incidents', 'stats', pid] as const,
  },
  evidence: {
    all:        ['evidence'] as const,
    forIncident:(id: string) => ['evidence', id] as const,
    global:     (p?: object) => ['evidence', 'global', p] as const,
  },
  notifications: {
    all:        ['notifications'] as const,
    list:       (p?: object) => ['notifications', 'list', p] as const,
    forIncident:(id: string) => ['notifications', 'incident', id] as const,
  },
  dashboard:     (pid?: string) => ['dashboard', 'summary', pid] as const,
  compliance:    (pid?: string) => ['compliance', 'dashboard', pid] as const,
  users:         (p?: object) => ['users', p] as const,
  ml: {
    stats:     ['ml', 'stats'] as const,
    modelInfo: ['ml', 'model-info'] as const,
    flows:     ['ml', 'flows'] as const,
    metrics:   ['ml', 'metrics'] as const,
  },
  audit:         (p?: object) => ['audit', 'logs', p] as const,
  health:        ['health'] as const,
  infrastructure:{
    status:    ['infra', 'status'] as const,
    sqsHistory:['infra', 'sqs-history'] as const,
  },
  securityScore: (pid?: string) => ['security-score', pid] as const,
  weeklyReport:  (pid?: string) => ['reports', 'weekly', pid] as const,
} as const

// ---- Incident filters -------------------------------------------------------
export interface IncidentFilters {
  status?: string; severity?: string; search?: string
  page?: number; page_size?: number; project_id?: string
}

// ---- Incidents list (paginated) --------------------------------------------
export function useIncidents(filters: IncidentFilters = {}) {
  const pid = useProjectStore(s => s.currentProject?.id)
  const merged = { ...filters, project_id: filters.project_id ?? pid }
  return useQuery({
    queryKey: qk.incidents.list(merged),
    queryFn:  () => incidentsApi.list(merged),
    refetchInterval: POLL_INCIDENTS_MS,
    staleTime: STALE_INCIDENTS_MS,
    gcTime: 5 * 60_000,
    placeholderData: (prev) => prev,
  })
}

// ---- Infinite scroll -------------------------------------------------------
export function useInfiniteIncidents(filters: Omit<IncidentFilters, 'page'> = {}) {
  const pid = useProjectStore(s => s.currentProject?.id)
  const merged = { ...filters, project_id: filters.project_id ?? pid }
  return useInfiniteQuery<PagedIncidentResponse>({
    queryKey: qk.incidents.infinite(merged),
    queryFn:  ({ pageParam }) =>
      incidentsApi.list({ ...merged, page: pageParam as number, page_size: DEFAULT_PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
    getPreviousPageParam: (first) => first.page > 1 ? first.page - 1 : undefined,
    staleTime: STALE_INCIDENTS_MS,
    refetchInterval: POLL_INCIDENTS_MS,
  })
}

// ---- Single incident -------------------------------------------------------
export function useIncident(id: string) {
  return useQuery({
    queryKey: qk.incidents.detail(id),
    queryFn:  () => incidentsApi.get(id),
    enabled:  !!id,
    staleTime: STALE_INCIDENTS_MS,
    gcTime: 10 * 60_000,
  })
}

// ---- Incident stats (GET /api/v1/incidents/stats) --------------------------
export function useIncidentStats() {
  const pid = useProjectStore(s => s.currentProject?.id)
  return useQuery({
    queryKey: qk.incidents.stats(pid),
    queryFn:  () => incidentsApi.stats(pid),
    staleTime: STALE_INCIDENTS_MS,
    refetchInterval: POLL_INCIDENTS_MS,
    retry: false,
  })
}

// ---- Mutations -------------------------------------------------------------
export function useCreateIncident() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: IncidentCreate) => incidentsApi.create(payload),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: qk.incidents.all })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      auditAction('incidents:create', 'incident', created.id)
      logger.info('Incident created', { id: created.id, severity: created.severity })
    },
    onError: (err) => logger.error('Failed to create incident', err),
  })
}

export function useUpdateIncident() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: IncidentUpdate }) =>
      incidentsApi.update(id, payload),
    onSuccess: (updated, { id }) => {
      qc.invalidateQueries({ queryKey: qk.incidents.all })
      qc.setQueryData(qk.incidents.detail(id), updated)
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      auditAction('incidents:update', 'incident', id, { new_status: updated.status })
    },
    onError: (err, { id }) => logger.error('Failed to update incident', err, { id }),
  })
}

// ---- Evidence (per-incident) -----------------------------------------------
export function useEvidence(incidentId: string) {
  return useQuery({
    queryKey: qk.evidence.forIncident(incidentId),
    queryFn:  () => evidenceApi.list(incidentId),
    enabled:  !!incidentId,
    staleTime: STALE_EVIDENCE_MS,
    gcTime: 15 * 60_000,
  })
}

export function useUploadEvidence() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ incidentId, file, description }: { incidentId: string; file: File; description?: string }) =>
      evidenceApi.upload(incidentId, file, description),
    onSuccess: (_, { incidentId }) => {
      qc.invalidateQueries({ queryKey: qk.evidence.forIncident(incidentId) })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
    onError: (err) => logger.error('Failed to upload evidence', err),
  })
}

// ---- Evidence (global -- endpoint MISSING on backend) ----------------------
export function useAllEvidence(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: qk.evidence.global(params),
    queryFn:  () => evidenceApi.listAll(params),
    staleTime: STALE_EVIDENCE_MS,
    gcTime: 15 * 60_000,
    retry: false,
  })
}

// ---- Notifications ---------------------------------------------------------
export function useNotifications(params?: {
  incidentId?: string; status?: string; regulation?: string
  page?: number; page_size?: number
}) {
  return useQuery({
    queryKey: params?.incidentId
      ? qk.notifications.forIncident(params.incidentId)
      : qk.notifications.list(params),
    queryFn: () => notificationsApi.list(params),
    refetchInterval: POLL_NOTIFICATIONS_MS,
    staleTime: STALE_NOTIFICATIONS_MS,
  })
}

export function useApproveNotification() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => notificationsApi.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.notifications.all }),
  })
}

export function useDispatchNotification() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => notificationsApi.dispatch(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.notifications.all }),
  })
}

// ---- Dashboard summary (GET /api/v1/dashboard/summary -- EXISTS) -----------
export function useDashboardSummary() {
  const pid = useProjectStore(s => s.currentProject?.id)
  return useQuery<DashboardSummary>({
    queryKey: qk.dashboard(pid),
    queryFn:  () => dashboardApi.summary(pid),
    refetchInterval: POLL_INCIDENTS_MS,
    staleTime: STALE_INCIDENTS_MS,
    retry: 1,
  })
}

// ---- Compliance dashboard (GET /api/v1/compliance/dashboard -- EXISTS) -----
export function useComplianceDashboard() {
  const pid = useProjectStore(s => s.currentProject?.id)
  return useQuery({
    queryKey: qk.compliance(pid),
    queryFn:  () => complianceApi.dashboard(pid),
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: 1,
  })
}

export function useMarkComplianceMet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => complianceApi.markMet(id, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance'] }),
  })
}

// ---- Project-scoped compliance obligation hooks (DB-backed) ----------------

/**
 * Fetch all saved obligation states for the current project.
 * Returns an empty array when no project is selected so the page can render
 * the obligation list in its default unchecked state.
 */
export function useComplianceObligations(framework?: string) {
  const pid = useProjectStore(s => s.currentProject?.id)
  return useQuery({
    queryKey: ['compliance', 'obligations', pid, framework ?? null],
    queryFn: () => pid
      ? complianceApi.getObligations(pid, framework)
      : Promise.resolve([]),
    enabled: !!pid,
    staleTime: 30_000,
    gcTime: 5 * 60_000,
    retry: 1,
  })
}

/**
 * Upsert an obligation (create-or-update) for the current project.
 * Used when toggling a checkbox that has not been saved to the DB yet.
 */
export function useUpsertObligation() {
  const qc = useQueryClient()
  const pid = useProjectStore(s => s.currentProject?.id)
  return useMutation({
    mutationFn: (data: ObligationCreate) => {
      if (!pid) return Promise.reject(new Error('No project selected'))
      return complianceApi.upsertObligation(pid, data)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'obligations'] })
    },
    onError: (err) => logger.error('Failed to upsert obligation', err),
  })
}

/**
 * Patch an existing obligation by its server-assigned UUID.
 * Used when toggling a checkbox that is already persisted in the DB.
 */
export function useUpdateObligation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ObligationUpdate }) =>
      complianceApi.updateObligationStatus(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'obligations'] })
    },
    onError: (err) => logger.error('Failed to update obligation', err),
  })
}

// ---- Users (GET /api/v1/users -- EXISTS) -----------------------------------
export function useUsers(params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: qk.users(params),
    queryFn:  () => usersApi.list(params),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    retry: 1,
  })
}

// ---- ML stats (GET /api/v1/ml/stats -- EXISTS) -----------------------------
export function useMlStats() {
  return useQuery({
    queryKey: qk.ml.stats,
    queryFn:  () => mlApi.stats(),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  })
}

export function useMlModelInfo() {
  return useQuery({
    queryKey: qk.ml.modelInfo,
    queryFn:  () => mlApi.modelInfo(),
    staleTime: 5 * 60_000,
    retry: 1,
  })
}

// ---- ML flows (MISSING endpoint) ------------------------------------------
export function useMlFlows() {
  return useQuery({
    queryKey: qk.ml.flows,
    queryFn:  () => mlApi.flows(),
    refetchInterval: 30_000,
    staleTime: 20_000,
    retry: false,
  })
}

// ---- ML metrics (MISSING endpoint) ----------------------------------------
export function useMlMetrics() {
  return useQuery({
    queryKey: qk.ml.metrics,
    queryFn:  () => mlApi.metrics(),
    staleTime: 5 * 60_000,
    retry: false,
  })
}

// ---- Audit logs (GET /api/v1/audit/logs -- EXISTS) -------------------------
export function useAuditLogs(params?: { page?: number; page_size?: number; user_id?: string; action?: string }) {
  return useQuery({
    queryKey: qk.audit(params),
    queryFn:  () => auditLogsApi.list(params),
    staleTime: 30_000,
    gcTime: 5 * 60_000,
    retry: 1,
  })
}

// ---- Health ----------------------------------------------------------------
export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn:  () => healthApi.check(),
    refetchInterval: POLL_HEALTH_MS,
    staleTime: STALE_HEALTH_MS,
    retry: false,
  })
}

// ---- Current user (GET /api/v1/auth/me) ------------------------------------
export function useCurrentUser() {
  return useQuery({
    queryKey: ['auth', 'me'],
    queryFn:  () => authApi.me(),
    staleTime: 5 * 60_000,
    retry: false,
  })
}

// ---- Infrastructure (MISSING backend) -------------------------------------
export function useInfrastructure() {
  return useQuery({
    queryKey: qk.infrastructure.status,
    queryFn:  () => infrastructureApi.status(),
    refetchInterval: 30_000,
    staleTime: 20_000,
    retry: false,
  })
}

export function useSqsHistory() {
  return useQuery({
    queryKey: qk.infrastructure.sqsHistory,
    queryFn:  () => infrastructureApi.sqsHistory(),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: false,
  })
}

// ---- Debounced search ------------------------------------------------------
export function useDebouncedSearch(initialValue = '') {
  const [search, setSearch] = useState(initialValue)
  const [debouncedSearch, setDebouncedSearch] = useState(initialValue)

  const debouncedSet = useRef(
    debounce((v: unknown) => setDebouncedSearch(v as string), DEBOUNCE_SEARCH_MS)
  ).current

  const handleSearch = useCallback((value: string) => {
    setSearch(value)
    debouncedSet(value)
  }, [debouncedSet])

  return { search, debouncedSearch, handleSearch }
}

// ---- Security Score --------------------------------------------------------
export function useSecurityScore() {
  const pid = useProjectStore(s => s.currentProject?.id)
  return useQuery({
    queryKey: qk.securityScore(pid),
    queryFn:  () => securityScoreApi.get(pid),
    refetchInterval: 60_000,
    staleTime:       30_000,
    retry: 1,
  })
}

// ---- Incident Explanation ---------------------------------------------------
export function useIncidentExplanation(incidentId: string) {
  return useQuery({
    queryKey: ['incidents', 'explain', incidentId],
    queryFn:  () => incidentsApi.explain(incidentId),
    enabled:  !!incidentId,
    staleTime: 5 * 60_000,
    retry: 1,
  })
}

// ---- Weekly Report ---------------------------------------------------------
export function useWeeklyReport() {
  const pid = useProjectStore(s => s.currentProject?.id)
  return useQuery({
    queryKey: qk.weeklyReport(pid),
    queryFn:  () => reportsApi.weekly(pid),
    staleTime: 5 * 60_000,
    retry: 1,
  })
}
