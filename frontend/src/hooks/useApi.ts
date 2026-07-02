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
  infrastructureApi, authApi,
} from '@/api/client'
import { debounce } from '@/lib/rateLimiter'
import { logger, auditAction } from '@/lib/logger'
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
    stats:    ['incidents', 'stats'] as const,
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
  dashboard:     ['dashboard', 'summary'] as const,
  compliance:    ['compliance', 'dashboard'] as const,
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
} as const

// ---- Incident filters -------------------------------------------------------
export interface IncidentFilters {
  status?: string; severity?: string; search?: string
  page?: number; page_size?: number
}

// ---- Incidents list (paginated) --------------------------------------------
export function useIncidents(filters: IncidentFilters = {}) {
  return useQuery({
    queryKey: qk.incidents.list(filters),
    queryFn:  () => incidentsApi.list(filters),
    refetchInterval: POLL_INCIDENTS_MS,
    staleTime: STALE_INCIDENTS_MS,
    gcTime: 5 * 60_000,
    placeholderData: (prev) => prev,
  })
}

// ---- Infinite scroll -------------------------------------------------------
export function useInfiniteIncidents(filters: Omit<IncidentFilters, 'page'> = {}) {
  return useInfiniteQuery<PagedIncidentResponse>({
    queryKey: qk.incidents.infinite(filters),
    queryFn:  ({ pageParam }) =>
      incidentsApi.list({ ...filters, page: pageParam as number, page_size: DEFAULT_PAGE_SIZE }),
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
  return useQuery({
    queryKey: qk.incidents.stats,
    queryFn:  () => incidentsApi.stats(),
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
      qc.invalidateQueries({ queryKey: qk.dashboard })
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
      qc.invalidateQueries({ queryKey: qk.dashboard })
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
      qc.invalidateQueries({ queryKey: qk.dashboard })
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
  return useQuery({
    queryKey: qk.dashboard,
    queryFn:  () => dashboardApi.summary(),
    refetchInterval: POLL_INCIDENTS_MS,
    staleTime: STALE_INCIDENTS_MS,
    retry: 1,
  })
}

// ---- Compliance dashboard (GET /api/v1/compliance/dashboard -- EXISTS) -----
export function useComplianceDashboard() {
  return useQuery({
    queryKey: qk.compliance,
    queryFn:  () => complianceApi.dashboard(),
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: 1,
  })
}

export function useMarkComplianceMet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => complianceApi.markMet(id, notes),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.compliance }),
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
