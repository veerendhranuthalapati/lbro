/**
 * LBRO API Client
 *
 * Key security decisions:
 * - getAccessToken() reads from module-level memory (not Zustand state) to avoid
 *   the persist-getter bug where spread converts getter -> null data property.
 * - 401 with a stored refresh token triggers a silent token refresh before logout.
 * - Request IDs injected per-request for distributed tracing.
 * - No withCredentials -- API key header only, zero CSRF surface.
 */
import axios, {
  type AxiosError,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { getAccessToken, getRefreshToken, useAuthStore } from '@/store/authStore'
import { globalApiThrottle, exponentialBackoff, shouldRetry } from '@/lib/rateLimiter'
import { logger, generateRequestId } from '@/lib/logger'
import {
  API_BASE_URL, API_TIMEOUT_MS, AUTH_HEADER, MAX_RETRIES,
} from '@/constants'
import type {
  Incident, IncidentDetail, IncidentCreate, IncidentUpdate,
  PagedIncidentResponse, EvidencePackage, RegulatoryNotification,
  HealthCheck, ApiError, User,
  DashboardStats, AWSStatus, CICIDSFlow, PagedResponse,
  Project, ProjectListResponse, ProjectCreate, ProjectUpdate, ProjectDashboard,
} from '@/types'

// ---- Extend Axios config with per-request metadata -------------------------
declare module 'axios' {
  interface InternalAxiosRequestConfig {
    metadata?: { requestId: string; startTime: number }
    _retryCount?: number
    _isRefresh?: boolean
  }
}

// ---- LoginResponse ----------------------------------------------------------
export interface LoginResponse {
  readonly access_token: string
  readonly refresh_token: string
  readonly token_type: string
  readonly expires_in: number
}

// ---- Analytics types -------------------------------------------------------
export interface AttackDistributionEntry { name: string; value: number }
export interface FlowVolumeEntry         { time: string; flows: number; anomalies: number }
export interface IncidentTimelineEntry   { hour: string; new: number; triaging: number; closed: number }
export interface SqsHistoryEntry         { time: string; incident: number; containment: number; notification: number }

// ---- ML types ---------------------------------------------------------------
export interface MlMetrics {
  feature_importance: { feature: string; importance: number }[]
  per_class_confidence: { subject: string; A: number; fullMark: number }[]
  false_positive_analysis: { attack: string; tp: number; fp: number; fn: number }[]
  tactic_distribution: { tactic: string; count: number; color: string }[]
}

// ---- Axios instance ---------------------------------------------------------
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
    'X-Client-Version': import.meta.env.VITE_APP_VERSION ?? 'dev',
  },
  withCredentials: false,
})

// ---- Request interceptor ----------------------------------------------------
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  if (!globalApiThrottle.consume()) {
    return Promise.reject(new Error('Rate limit exceeded. Please wait.')) as never
  }

  // Use getAccessToken() -- reads module-level memory, never Zustand state.
  // This is the fix for the persist-getter bug.
  let token = getAccessToken()

  // Proactive silent refresh: after a page reload the access token is gone
  // (it lives only in memory) but the refresh token survives in sessionStorage.
  // Rather than letting the request go out without a token, get a new access
  // token first. This prevents a 401 round-trip on every page reload and stops
  // the ProtectedRoute flash-to-login that users see as "frequent logouts".
  if (!token && getRefreshToken() && !config._isRefresh) {
    try {
      token = await refreshAccessToken()
    } catch {
      // Refresh failed — let the request proceed without a token.
      // The response interceptor will handle the resulting 401 (logout).
    }
  }

  if (token) {
    config.headers[AUTH_HEADER] = `Bearer ${token}`
  }

  const requestId = generateRequestId()
  config.headers['X-Request-ID'] = requestId
  config.metadata = { requestId, startTime: Date.now() }
  logger.debug('API request', { url: config.url, method: config.method, requestId })
  return config
})

// ---- Refresh token helper ---------------------------------------------------
let _refreshing: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  // Deduplicate concurrent refresh calls
  if (_refreshing) return _refreshing

  _refreshing = (async () => {
    const refreshToken = getRefreshToken()
    if (!refreshToken) throw new Error('No refresh token')

    const res = await axios.post<LoginResponse>(
      `${API_BASE_URL}/api/v1/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } }
    )
    const { access_token, refresh_token } = res.data
    // Update memory (do not call login() to avoid resetting lockout / session)
    const user = useAuthStore.getState().user
    if (user) {
      useAuthStore.getState().login(access_token, refresh_token ?? null, user)
    }
    return access_token
  })().finally(() => { _refreshing = null })

  return _refreshing
}

// ---- Response interceptor --------------------------------------------------
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    const meta = response.config.metadata
    const duration = meta ? Date.now() - meta.startTime : 0
    logger.debug('API response', {
      url: response.config.url,
      status: response.status,
      duration_ms: duration,
      request_id: meta?.requestId,
    })
    return response
  },
  async (err: AxiosError<ApiError>) => {
    const status = err.response?.status ?? 0
    const config = err.config as (InternalAxiosRequestConfig & { _retryCount?: number; _isRefresh?: boolean }) | undefined

    // 401: try token refresh once, then logout.
    // Skip this path for auth endpoints that legitimately return 401
    // (login with bad creds, register, refresh itself) — those 401s must
    // bubble back to the calling component so it can show the error message.
    // Without this guard the interceptor would reload the page before the
    // catch block in handleSubmit could display anything.
    const url = config?.url ?? ''
    const isAuthEndpoint = url.includes('/auth/login')
      || url.includes('/auth/register')
      || url.includes('/auth/refresh')
      || url.includes('/auth/me')
    if (status === 401 && config && !config._isRefresh && !isAuthEndpoint) {
      try {
        const newToken = await refreshAccessToken()
        config._isRefresh = true
        config.headers[AUTH_HEADER] = `Bearer ${newToken}`
        return apiClient(config)
      } catch {
        logger.warn('Token refresh failed -- logging out', { url: config?.url })
        useAuthStore.getState().logout()
        window.location.replace('/login')
        return Promise.reject(err)
      }
    }

    // 429 or 5xx: exponential backoff retry
    if (config && shouldRetry(status, config._retryCount ?? 0, MAX_RETRIES)) {
      config._retryCount = (config._retryCount ?? 0) + 1
      const delayMs = exponentialBackoff(config._retryCount)
      logger.warn(`Retrying request (attempt ${config._retryCount})`, { url: config.url, status })
      await new Promise(r => setTimeout(r, delayMs))
      return apiClient(config)
    }

    const apiErr = err.response?.data
    logger.error('API error', err, {
      url: err.config?.url, status,
      detail: apiErr?.detail, code: apiErr?.code,
    })
    return Promise.reject(err)
  }
)

// ---- Auth -------------------------------------------------------------------
export const authApi = {
  login: (email: string, password: string): Promise<LoginResponse> =>
    apiClient.post<LoginResponse>('/api/v1/auth/login', { email, password }).then(r => r.data),

  me: (token?: string): Promise<User> =>
    apiClient.get<User>('/api/v1/auth/me', {
      headers: token ? { [AUTH_HEADER]: `Bearer ${token}` } : undefined,
    }).then(r => r.data),

  register: (data: { email: string; full_name: string; password: string; username?: string }): Promise<LoginResponse> =>
    apiClient.post<LoginResponse>('/api/v1/auth/register', data).then(r => r.data),

  updateProfile: (data: { full_name?: string; email?: string; new_password?: string; current_password?: string }): Promise<User> =>
    apiClient.patch<User>('/api/v1/auth/profile', data).then(r => r.data),

  refresh: (refreshToken: string): Promise<LoginResponse> =>
    apiClient.post<LoginResponse>('/api/v1/auth/refresh', { refresh_token: refreshToken }).then(r => r.data),

  rotateApiKey: (): Promise<{ api_key: string }> =>
    apiClient.post<{ api_key: string }>('/api/v1/auth/api-key/rotate').then(r => r.data),

  logout: (): Promise<void> =>
    apiClient.post('/api/v1/auth/logout').then(() => undefined).catch(() => undefined),
}

// ---- Dashboard --------------------------------------------------------------
export interface DashboardSummary {
  total_incidents:       number
  new_last_24h:          number
  open_incidents:        number
  critical_incidents:    number
  pending_notifications: number
  overdue_compliance:    number
  total_evidence:        number
  needs_analyst_review:  number
  severity_breakdown:    Record<string, number>
  status_breakdown:      Record<string, number>
  recent_incidents:      Array<{ id: string; title: string; severity: string; status: string; created_at: string }>
}

export const dashboardApi = {
  /** GET /api/v1/dashboard/summary -- exists */
  summary: (project_id?: string): Promise<DashboardSummary> =>
    apiClient.get<DashboardSummary>('/api/v1/dashboard/summary', {
      params: project_id ? { project_id } : undefined,
    }).then(r => r.data),
}

// ---- Incidents --------------------------------------------------------------
export const incidentsApi = {
  list: (params?: {
    status?: string; severity?: string; page?: number
    page_size?: number; search?: string; project_id?: string
  }): Promise<PagedIncidentResponse> =>
    apiClient.get<PagedIncidentResponse>('/api/v1/incidents', { params }).then(r => r.data),

  get: (id: string): Promise<IncidentDetail> =>
    apiClient.get<IncidentDetail>(`/api/v1/incidents/${id}`).then(r => r.data),

  create: (payload: IncidentCreate): Promise<Incident> =>
    apiClient.post<Incident>('/api/v1/incidents', payload).then(r => r.data),

  update: (id: string, payload: IncidentUpdate): Promise<Incident> =>
    apiClient.patch<Incident>(`/api/v1/incidents/${id}`, payload).then(r => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/api/v1/incidents/${id}`).then(() => undefined),

  stats: (project_id?: string): Promise<Record<string, unknown>> =>
    apiClient.get('/api/v1/incidents/stats', {
      params: project_id ? { project_id } : undefined,
    }).then(r => r.data),

  explain: (id: string): Promise<IncidentExplanation> =>
    apiClient.get<IncidentExplanation>(`/api/v1/incidents/${id}/explain`).then(r => r.data),
}

// ---- Evidence ---------------------------------------------------------------
export const evidenceApi = {
  list: (incidentId: string): Promise<EvidencePackage[]> =>
    apiClient.get<{ items: EvidencePackage[] }>(`/api/v1/incidents/${incidentId}/evidence`).then(r => r.data.items ?? []),

  upload: (incidentId: string, file: File, description?: string): Promise<EvidencePackage> => {
    const fd = new FormData()
    fd.append('file', file)
    if (description) fd.append('description', description)
    return apiClient.post<EvidencePackage>(
      `/api/v1/incidents/${incidentId}/evidence`, fd,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    ).then(r => r.data)
  },

  downloadUrl: (evidenceId: string): Promise<{ download_url: string }> =>
    apiClient.get(`/api/v1/evidence/${evidenceId}/download-url`).then(r => r.data),

  verify: (evidenceId: string): Promise<{ verified: boolean; hash_matched: boolean }> =>
    apiClient.post(`/api/v1/evidence/${evidenceId}/verify`).then(r => r.data),

  /** Global evidence list -- endpoint not yet implemented on backend */
  listAll: (params?: { page?: number; page_size?: number }): Promise<PagedResponse<EvidencePackage>> =>
    apiClient.get<PagedResponse<EvidencePackage>>('/api/v1/evidence', { params }).then(r => r.data),
}

// ---- Notifications ----------------------------------------------------------
export interface NotificationListResponse {
  items: RegulatoryNotification[]
  total: number
  page: number
  page_size: number
}

export const notificationsApi = {
  list: (params?: {
    incidentId?: string; status?: string; regulation?: string
    page?: number; page_size?: number
  }): Promise<NotificationListResponse> => {
    const qp: Record<string, unknown> = {}
    if (params?.status)     qp.status     = params.status
    if (params?.regulation) qp.regulation = params.regulation
    if (params?.incidentId) qp.incident_id = params.incidentId
    if (params?.page)       qp.page       = params.page
    if (params?.page_size)  qp.page_size  = params.page_size
    return apiClient.get<NotificationListResponse>('/api/v1/notifications', { params: qp }).then(r => r.data)
  },

  get: (id: string): Promise<RegulatoryNotification> =>
    apiClient.get<RegulatoryNotification>(`/api/v1/notifications/${id}`).then(r => r.data),

  approve: (id: string): Promise<RegulatoryNotification> =>
    apiClient.post<RegulatoryNotification>(`/api/v1/notifications/${id}/approve`).then(r => r.data),

  dispatch: (id: string): Promise<RegulatoryNotification> =>
    apiClient.post<RegulatoryNotification>(`/api/v1/notifications/${id}/dispatch`).then(r => r.data),

  send: (id: string): Promise<RegulatoryNotification> =>
    apiClient.post<RegulatoryNotification>(`/api/v1/notifications/${id}/send`).then(r => r.data),
}

// ---- Compliance -------------------------------------------------------------
export interface ComplianceSummary { regulation: string; total: number; met: number; overdue: number; pending: number }
export interface ComplianceRecord {
  id: string; incident_id: string; regulation: string; jurisdiction: string
  obligation: string; deadline: string; is_met: boolean; met_at: string | null
  notes: string | null; created_at: string; updated_at: string
}
export interface ComplianceDashboard {
  summaries: ComplianceSummary[]
  overdue_records: ComplianceRecord[]
  upcoming_deadlines: ComplianceRecord[]
}

/** Project-scoped obligation (replaces localStorage persistence). */
export interface ObligationResponse {
  id: string
  project_id: string
  framework: string
  control_id: string
  control_name: string
  description: string | null
  status: string           // not_started | in_progress | compliant | non_compliant | not_applicable
  evidence_reference: string | null
  score: number
  recommendations: string | null
  last_updated: string | null
  created_at: string
}

export interface ObligationCreate {
  framework: string
  control_id: string
  control_name: string
  description?: string
  status?: string
  evidence_reference?: string
  recommendations?: string
}

export interface ObligationUpdate {
  status?: string
  evidence_reference?: string
  recommendations?: string
  score?: number
}

export interface ComplianceScoreResponse {
  project_id: string
  framework: string | null
  overall_score: number
  total_controls: number
  compliant_controls: number
  non_compliant_controls: number
  in_progress_controls: number
}

export const complianceApi = {
  dashboard: (project_id?: string): Promise<ComplianceDashboard> =>
    apiClient.get<ComplianceDashboard>('/api/v1/compliance/dashboard', {
      params: project_id ? { project_id } : undefined,
    }).then(r => r.data),

  markMet: (recordId: string, notes?: string): Promise<ComplianceRecord> =>
    apiClient.post<ComplianceRecord>(`/api/v1/compliance/records/${recordId}/mark-met`, { notes }).then(r => r.data),

  // --- Project-scoped obligation persistence (DB-backed, replaces localStorage) ---

  getObligations: (projectId: string, framework?: string): Promise<ObligationResponse[]> =>
    apiClient.get<ObligationResponse[]>('/api/v1/compliance/obligations', {
      params: { project_id: projectId, ...(framework ? { framework } : {}) },
    }).then(r => r.data),

  /**
   * Upsert an obligation (create-or-update by project+framework+control_id).
   * Use this when toggling a checkbox for the first time or when no obligation
   * ID is available yet.
   */
  upsertObligation: (projectId: string, data: ObligationCreate): Promise<ObligationResponse> =>
    apiClient.post<ObligationResponse>('/api/v1/compliance/obligations', data, {
      params: { project_id: projectId },
    }).then(r => r.data),

  /**
   * Patch an existing obligation by its UUID.
   * Use when the obligation already has a server-assigned ID.
   */
  updateObligationStatus: (id: string, data: ObligationUpdate): Promise<ObligationResponse> =>
    apiClient.patch<ObligationResponse>(`/api/v1/compliance/obligations/${id}`, data).then(r => r.data),

  getScore: (projectId: string, framework?: string): Promise<ComplianceScoreResponse> =>
    apiClient.get<ComplianceScoreResponse>('/api/v1/compliance/score', {
      params: { project_id: projectId, ...(framework ? { framework } : {}) },
    }).then(r => r.data),

  createAssessment: (projectId: string, framework: string, notes?: string): Promise<ObligationResponse> =>
    apiClient.post<ObligationResponse>('/api/v1/compliance/assess', null, {
      params: { project_id: projectId, framework, ...(notes ? { notes } : {}) },
    }).then(r => r.data),

  getAssessments: (projectId: string, framework?: string): Promise<ObligationResponse[]> =>
    apiClient.get<ObligationResponse[]>('/api/v1/compliance/assessments', {
      params: { project_id: projectId, ...(framework ? { framework } : {}) },
    }).then(r => r.data),
}

// ---- Users ------------------------------------------------------------------
export interface UserCreate {
  email: string
  username: string
  full_name: string
  password: string
  role: string
}

export const usersApi = {
  list: (params?: { page?: number; page_size?: number }): Promise<PagedResponse<User>> =>
    apiClient.get<PagedResponse<User>>('/api/v1/users', { params }).then(r => r.data),

  get: (id: string): Promise<User> =>
    apiClient.get<User>(`/api/v1/users/${id}`).then(r => r.data),

  create: (payload: UserCreate): Promise<User> =>
    apiClient.post<User>('/api/v1/users', payload).then(r => r.data),

  update: (id: string, payload: Partial<Pick<User, 'full_name' | 'role'>>): Promise<User> =>
    apiClient.patch<User>(`/api/v1/users/${id}`, payload).then(r => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/api/v1/users/${id}`).then(() => undefined),
}

// ---- ML ---------------------------------------------------------------------
export const mlApi = {
  /** GET /api/v1/ml/stats -- EXISTS */
  stats: (): Promise<Record<string, unknown>> =>
    apiClient.get('/api/v1/ml/stats').then(r => r.data),

  /** GET /api/v1/ml/model-info -- EXISTS */
  modelInfo: (): Promise<Record<string, unknown>> =>
    apiClient.get('/api/v1/ml/model-info').then(r => r.data),

  /** GET /api/v1/ml/models -- EXISTS */
  models: (): Promise<Record<string, unknown>> =>
    apiClient.get('/api/v1/ml/models').then(r => r.data),

  /** POST /api/v1/ml/classify -- EXISTS */
  classify: (features: Record<string, number>): Promise<Record<string, unknown>> =>
    apiClient.post('/api/v1/ml/classify', features).then(r => r.data),

  /** MISSING: live classified network flows */
  flows: (): Promise<CICIDSFlow[]> =>
    apiClient.get<CICIDSFlow[]>('/api/v1/ml/flows').then(r => r.data),

  /** MISSING: aggregated ML performance metrics for charts */
  metrics: (): Promise<MlMetrics> =>
    apiClient.get<MlMetrics>('/api/v1/ml/metrics').then(r => r.data),
}

// ---- Audit Logs -------------------------------------------------------------
export const auditLogsApi = {
  list: (params?: { page?: number; page_size?: number; user_id?: string; action?: string }): Promise<PagedResponse<Record<string, unknown>>> =>
    apiClient.get('/api/v1/audit/logs', { params }).then(r => r.data),
}

// ---- Health -----------------------------------------------------------------
export const healthApi = {
  check: (): Promise<HealthCheck> =>
    apiClient.get<HealthCheck>('/health').then(r => r.data),
}

// ---- Infrastructure (MISSING backend endpoints) ----------------------------
export const infrastructureApi = {
  status: (): Promise<AWSStatus> =>
    apiClient.get<AWSStatus>('/api/v1/infrastructure').then(r => r.data),
  sqsHistory: (): Promise<SqsHistoryEntry[]> =>
    apiClient.get<SqsHistoryEntry[]>('/api/v1/infrastructure/sqs-history').then(r => r.data),
}

// ---- Security Score ---------------------------------------------------------
export interface ScoreFactor {
  label: string
  detail: string
  impact: 'positive' | 'negative'
}

export interface ScoreRecommendation {
  priority: 'critical' | 'high' | 'medium' | 'low'
  title: string
  detail: string
}

export interface SecurityScore {
  score: number
  grade: string
  color: string
  status: string
  summary: string
  factors: ScoreFactor[]
  recommendations: ScoreRecommendation[]
  data_snapshot: Record<string, number | string>
  calculated_at: string
}

export const securityScoreApi = {
  get: (project_id?: string): Promise<SecurityScore> =>
    apiClient.get<SecurityScore>('/api/v1/security-score', {
      params: project_id ? { project_id } : undefined,
    }).then(r => r.data),
}


// ---- Incident Explanation ---------------------------------------------------
export interface IncidentExplanation {
  incident_id: string
  incident_title: string
  incident_severity: string
  attack_category: string | null
  category: string
  plain_english: string
  context: string | null
  business_impact: string
  technical_impact: string
  likelihood: 'Low' | 'Medium' | 'High' | 'Critical'
  owasp: string | null
  mitre_attack: string[]
  recommended_fixes: string[]
  severity_hint: string
  learn_more_url: string | null
}

// ---- Weekly Report ---------------------------------------------------------
export interface WeeklyReportSection {
  open_critical: number
  open_high: number
  open_medium: number
  open_low: number
  new_this_week: number
  closed_this_week: number
  top_attack_types: { category: string; count: number }[]
  most_targeted_ports: { port: number; count: number }[]
  critical_incidents: Array<{ id: string; title: string; severity: string; status: string; created_at: string }>
  resolved_incidents: Array<{ id: string; title: string; severity: string; resolved_at: string }>
}

export interface WeeklyReport {
  generated_at: string
  period_start: string
  period_end: string
  security_score: number
  security_grade: string
  security_color: string
  security_status: string
  executive_summary: string
  total_incidents: number
  incidents: WeeklyReportSection
  evidence_count: number
  compliance_met: number
  compliance_total: number
  top_recommendations: Array<{ priority: string; title: string; detail: string }>
  trend: 'improving' | 'stable' | 'worsening'
  trend_reason: string
}

export const reportsApi = {
  weekly: (project_id?: string): Promise<WeeklyReport> =>
    apiClient.get<WeeklyReport>('/api/v1/reports/weekly', {
      params: project_id ? { project_id } : undefined,
    }).then(r => r.data),
}

// ---- Projects ---------------------------------------------------------------
export const projectsApi = {
  list: (includeArchived = false): Promise<ProjectListResponse> =>
    apiClient.get<ProjectListResponse>('/api/v1/projects', {
      params: { include_archived: includeArchived },
    }).then(r => r.data),

  get: (id: string): Promise<Project> =>
    apiClient.get<Project>(`/api/v1/projects/${id}`).then(r => r.data),

  create: (data: ProjectCreate): Promise<Project> =>
    apiClient.post<Project>('/api/v1/projects', data).then(r => r.data),

  update: (id: string, data: ProjectUpdate): Promise<Project> =>
    apiClient.patch<Project>(`/api/v1/projects/${id}`, data).then(r => r.data),

  delete: (id: string): Promise<void> =>
    apiClient.delete(`/api/v1/projects/${id}`).then(() => undefined),

  regenerateKey: (id: string): Promise<Project> =>
    apiClient.post<Project>(`/api/v1/projects/${id}/regenerate-key`).then(r => r.data),

  dashboard: (id: string): Promise<ProjectDashboard> =>
    apiClient.get<ProjectDashboard>(`/api/v1/projects/${id}/dashboard`).then(r => r.data),
}


// ---- Demo data generation ---------------------------------------------------
export interface DemoGenerateResponse {
  incidents_created: number
  notifications_created: number
  evidence_created: number
  compliance_created: number
}

export interface DemoEventsResponse {
  injected:   number
  project_id: string
  message:    string
}

export const demoApi = {
  generate: (projectId?: string): Promise<DemoGenerateResponse> =>
    apiClient.post<DemoGenerateResponse>(
      '/api/v1/demo/generate',
      projectId ? { project_id: projectId } : {},
    ).then(r => r.data),

  injectEvents: (project_id: string, count = 5): Promise<DemoEventsResponse> =>
    apiClient.post<DemoEventsResponse>('/api/v1/demo/events', { project_id, count }).then(r => r.data),
}
