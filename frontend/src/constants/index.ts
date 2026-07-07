// ---- API ----------------------------------------------------------------------------------------------------------------------------------------------
// Empty string → relative URLs → requests go through Vite dev-proxy and MSW can intercept.
// Set VITE_API_URL to the absolute API origin only in production deployments.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''
export const API_TIMEOUT_MS = 15_000
export const API_VERSION = 'v1'

// ---- Auth ------------------------------------------------------------------------------------------------------------------------------------------
export const AUTH_STORAGE_KEY = 'lbro-auth'
export const AUTH_HEADER = 'Authorization'
export const SESSION_TIMEOUT_MS = 8 * 60 * 60 * 1000 // 8 hours

// ---- Rate limiting ------------------------------------------------------------------------------------------------------------------------
export const LOGIN_MAX_ATTEMPTS = 5
export const LOGIN_LOCKOUT_MS = 15 * 60 * 1000 // 15 minutes
export const UPLOAD_RATE_LIMIT_MB_PER_MIN = 100
export const REQUEST_THROTTLE_MS = 200

// ---- Polling intervals ----------------------------------------------------------------------------------------------------------------
export const POLL_INCIDENTS_MS = 15_000
export const POLL_NOTIFICATIONS_MS = 30_000
export const POLL_HEALTH_MS = 30_000
export const POLL_INFRA_MS = 60_000

// ---- Pagination ------------------------------------------------------------------------------------------------------------------------------
export const DEFAULT_PAGE_SIZE = 25
export const MAX_PAGE_SIZE = 100
export const INFINITE_SCROLL_THRESHOLD = 0.9 // 90% scroll trigger

// ---- Retry ----------------------------------------------------------------------------------------------------------------------------------------
export const MAX_RETRIES = 3
export const RETRY_BASE_DELAY_MS = 1_000
export const RETRY_MAX_DELAY_MS = 30_000

// ---- Stale times ----------------------------------------------------------------------------------------------------------------------------
export const STALE_INCIDENTS_MS = 10_000
export const STALE_EVIDENCE_MS = 60_000
export const STALE_NOTIFICATIONS_MS = 20_000
export const STALE_HEALTH_MS = 15_000

// ---- CICIDS2017 --------------------------------------------------------------------------------------------------------------------------------
export const CICIDS_MODEL_VERSION = '2017-v1.0'
export const CICIDS_MIN_CONFIDENCE = 0.75 // Minimum ML confidence to surface alert
export const CICIDS_FALSE_POSITIVE_THRESHOLD = 0.15

// ---- MITRE ATT&CK --------------------------------------------------------------------------------------------------------------------------
export const MITRE_BASE_URL = 'https://attack.mitre.org/techniques'

// ---- Compliance deadlines ----------------------------------------------------------------------------------------------------------
export const COMPLIANCE_DEADLINE_HOURS: Record<string, number> = {
  GDPR: 72,
  HIPAA: 1440, // 60 days
  DPDPA: 72,
}

// ---- Evidence ----------------------------------------------------------------------------------------------------------------------------------
export const MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024 // 100 MB — matches backend limit
export const ALLOWED_EVIDENCE_MIME_TYPES = [
  'application/octet-stream',
  'application/gzip',
  'application/zip',
  'application/x-pcap',
  'text/plain',
  'application/json',
  'application/pdf',
]

// ---- UI ------------------------------------------------------------------------------------------------------------------------------------------------
export const TOAST_DURATION_MS = 5_000
export const DEBOUNCE_SEARCH_MS = 350
export const ANIMATION_DURATION_MS = 200

// ---- CSP nonce (injected at build via vite plugin in production) ------------------------------
export const CSP_NONCE = (window as Window & { __LBRO_CSP_NONCE__?: string }).__LBRO_CSP_NONCE__ ?? ''

// ---- Roles ----------------------------------------------------------------------------------------------------------------------------------------
// Re-export from canonical RBAC types file
export { ROLES, ROLE_LABELS, ROLE_PERMISSIONS, Permission } from '@/types/rbac'
export type { Role as UserRole, PermissionValue } from '@/types/rbac'
