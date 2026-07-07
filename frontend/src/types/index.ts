// ---- Primitives --------------------------------------------------------------------------------------------------------------------------------

/** ISO-8601 datetime string */
export type ISODateString = string & { readonly __brand: 'ISODateString' }

/** UUID v4 string */
export type UUID = string & { readonly __brand: 'UUID' }

/** SHA-256 hex string */
export type SHA256Hash = string & { readonly __brand: 'SHA256Hash' }

// ---- Enums (string unions -- safer than TS enum) ----------------------------------------------------------------

export const INCIDENT_SEVERITIES = ['critical', 'high', 'medium', 'low', 'info'] as const
export type IncidentSeverity = typeof INCIDENT_SEVERITIES[number]

export const INCIDENT_STATUSES = [
  'new', 'triaging', 'contained', 'eradicating', 'recovering', 'closed', 'reopened',
] as const
export type IncidentStatus = typeof INCIDENT_STATUSES[number]

export const JURISDICTIONS = ['GDPR', 'HIPAA', 'DPDPA'] as const
export type Jurisdiction = typeof JURISDICTIONS[number]

export const NOTIFICATION_STATUSES = ['pending', 'approved', 'sent', 'failed'] as const
export type NotificationStatus = typeof NOTIFICATION_STATUSES[number]

export const ATTACK_TYPES = [
  'BENIGN', 'DoS Hulk', 'PortScan', 'DDoS', 'DoS GoldenEye',
  'FTP-Patator', 'SSH-Patator', 'DoS slowloris', 'DoS Slowhttptest',
  'Bot', 'Web Attack -- Brute Force', 'Web Attack -- XSS', 'Infiltration',
  'Web Attack -- Sql Injection', 'Heartbleed',
] as const
export type AttackType = typeof ATTACK_TYPES[number]

export const EVIDENCE_PACKAGE_TYPES = [
  'pcap', 'logs', 'memory-dump', 'disk-image', 'screenshot', 'report',
] as const
export type EvidencePackageType = typeof EVIDENCE_PACKAGE_TYPES[number]

export const WORKER_HEALTH_STATUSES = ['healthy', 'degraded', 'unhealthy'] as const
export type WorkerHealthStatus = typeof WORKER_HEALTH_STATUSES[number]

// ---- Chain of Custody ------------------------------------------------------------------------------------------------------------------

export const CUSTODY_ACTIONS = [
  'COLLECTED', 'HASHED', 'UPLOADED', 'VERIFIED', 'ACCESSED', 'TRANSFERRED', 'SEALED',
] as const
export type CustodyAction = typeof CUSTODY_ACTIONS[number]

export interface ChainOfCustodyEntry {
  readonly id: UUID
  readonly action: string
  readonly performed_by_name: string
  readonly ip_address: string | null
  readonly notes: string | null
  readonly hash_at_time: string | null
  readonly created_at: ISODateString
}

// ---- Incidents ----------------------------------------------------------------------------------------------------------------------------------

export interface TimelineEvent {
  readonly id: UUID
  readonly event_type: string
  readonly actor: string
  readonly description: string
  readonly event_metadata: Record<string, unknown> | null
  readonly occurred_at: ISODateString
}

// Matches backend IncidentResponse schema (app/schemas/incident.py)
export interface Incident {
  readonly id: UUID
  readonly external_id: string | null
  readonly title: string
  readonly description: string | null
  readonly severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  readonly status: IncidentStatus
  readonly attack_category: string | null
  readonly confidence_score: number | null
  readonly ml_model_version: string | null
  readonly needs_analyst_review: boolean
  readonly source_ip: string | null
  readonly destination_ip: string | null
  readonly source_port: number | null
  readonly destination_port: number | null
  readonly protocol: string | null
  readonly flow_duration_ms: number | null
  readonly affected_jurisdictions: readonly string[] | null
  readonly personal_data_involved: boolean
  readonly health_data_involved: boolean
  readonly assigned_to: UUID | null
  readonly created_by: UUID | null
  readonly detected_at: ISODateString
  readonly closed_at: ISODateString | null
  readonly created_at: ISODateString
  readonly updated_at: ISODateString
  readonly actions: readonly IncidentAction[]
}

export interface IncidentAction {
  readonly id: UUID
  readonly action_type: string
  readonly description: string
  readonly automated: boolean
  readonly result: string | null
  readonly created_at: ISODateString
}

export interface IncidentDetail extends Incident {
  readonly timeline: readonly TimelineEvent[]
}

export interface IncidentCreate {
  title: string
  description?: string
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info'
  source_ip?: string
  destination_ip?: string
  source_port?: number
  destination_port?: number
  protocol?: string
  affected_jurisdictions?: string[]
  personal_data_involved?: boolean
  health_data_involved?: boolean
  network_features?: Record<string, number | null>
}

export interface IncidentUpdate {
  title?: string
  description?: string
  status?: IncidentStatus
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info'
  assigned_to?: UUID
  affected_jurisdictions?: string[]
  personal_data_involved?: boolean
  health_data_involved?: boolean
  containment_actions?: string[]
}

// ---- Evidence ------------------------------------------------------------------------------------------------------------------------------------

export interface EvidencePackage {
  readonly id: UUID
  readonly incident_id: UUID
  readonly filename: string
  readonly original_filename: string
  readonly content_type: string
  readonly file_size: number
  readonly sha256_hash: SHA256Hash
  readonly description: string | null
  readonly tags: string | null
  readonly is_immutable: boolean
  readonly uploaded_by: UUID | null
  readonly created_at: ISODateString
  readonly custody_chain: readonly ChainOfCustodyEntry[]
  readonly download_url: string | null
}

// ---- Regulatory Notifications ----------------------------------------------------------------------------------------------------

export interface RegulatoryNotification {
  readonly id: UUID
  readonly incident_id: UUID
  readonly regulation: string
  readonly jurisdiction: string
  readonly authority: string
  readonly authority_email: string | null
  readonly status: string
  readonly subject: string
  readonly body: string
  readonly deadline: ISODateString
  readonly sent_at: ISODateString | null
  readonly approved_at: ISODateString | null
  readonly retry_count: number
  readonly last_error: string | null
  readonly created_at: ISODateString
  readonly updated_at: ISODateString
}

/** Alias for backwards-compat */
export type Notification = RegulatoryNotification

// ---- User --------------------------------------------------------------------------------------------------------------------------------------------

export interface User {
  readonly id: UUID
  readonly email: string
  readonly username: string
  readonly full_name: string
  readonly role: string
  readonly is_active: boolean
  readonly is_verified: boolean
  readonly mfa_enabled: boolean
  readonly last_login: ISODateString | null
  readonly created_at: ISODateString
  readonly updated_at: ISODateString
}

// ---- Pagination ----------------------------------------------------------------------------------------------------------------------------------

export interface PagedResponse<T> {
  readonly total: number
  readonly page: number
  readonly page_size: number
  readonly items: readonly T[]
}

export type PagedIncidentResponse = PagedResponse<Incident>

export interface CursorPagedResponse<T> {
  readonly items: readonly T[]
  readonly next_cursor: string | null
  readonly prev_cursor: string | null
  readonly total_estimate: number
}

// ---- Health ----------------------------------------------------------------------------------------------------------------------------------------

export interface HealthCheck {
  readonly status: 'ok' | 'degraded' | 'unhealthy'
  readonly version: string
}

// ---- Auth --------------------------------------------------------------------------------------------------------------------------------------------

export type { PermissionValue as Permission, Role as UserRole } from '@/types/rbac'
import type { PermissionValue } from '@/types/rbac'
import type { Role } from '@/types/rbac'

export interface AuthUser {
  readonly id: UUID
  readonly name: string
  readonly email: string
  readonly role: Role
  readonly permissions: readonly PermissionValue[]
  readonly last_login: ISODateString | null
}

export interface AuthState {
  readonly user: AuthUser | null
  readonly isAuthenticated: boolean
  readonly sessionExpiresAt: number | null
  readonly loginAttempts: number
  readonly lockedUntil: number | null
  login: (accessToken: string, refreshToken: string | null, user: AuthUser) => void
  logout: () => void
  setUser: (user: AuthUser) => void
  incrementLoginAttempts: () => void
  resetLoginAttempts: () => void
  isLocked: () => boolean
}

export interface LoginResponse {
  readonly access_token: string
  readonly refresh_token: string
  readonly token_type: string
  readonly expires_in: number
}

// ---- CICIDS2017 ----------------------------------------------------------------------------------------------------------------------------------

export interface CICIDSFlow {
  readonly flow_id: string
  readonly timestamp: ISODateString
  readonly src_ip: string
  readonly dst_ip: string
  readonly src_port: number
  readonly dst_port: number
  readonly protocol: 'TCP' | 'UDP' | 'ICMP'
  readonly attack_type: AttackType
  readonly flow_duration: number
  readonly total_fwd_packets: number
  readonly total_bwd_packets: number
  readonly total_fwd_bytes: number
  readonly total_bwd_bytes: number
  readonly flow_bytes_per_sec: number
  readonly flow_packets_per_sec: number
  readonly fwd_iat_mean: number
  readonly bwd_iat_mean: number
  readonly confidence_score: number
  readonly is_false_positive: boolean
  readonly mitre_technique: string | null
  readonly label: AttackType
}

export interface CICIDSPrediction {
  readonly attack_type: AttackType
  readonly confidence: number
  readonly model_version: string
  readonly features_used: readonly string[]
  readonly explanation: Record<string, number>
}

// ---- MITRE ATT&CK --------------------------------------------------------------------------------------------------------------------------

export interface MitreTechnique {
  readonly technique_id: string
  readonly name: string
  readonly tactic: string
  readonly description: string
  readonly url: string
  readonly mitigations: readonly string[]
}

// ---- Dashboard Stats ----------------------------------------------------------------------------------------------------------------------

export interface DashboardStats {
  readonly active_incidents: number
  readonly resolved_today: number
  readonly critical_count: number
  readonly high_count: number
  readonly medium_count: number
  readonly low_count: number
  readonly avg_response_time_seconds: number
  readonly evidence_packages: number
  readonly pending_notifications: number
  readonly overdue_notifications: number
  readonly compliance_score: number
  readonly mttr_seconds: number
  readonly false_positive_rate: number
}

// ---- AWS Infrastructure ----------------------------------------------------------------------------------------------------------------

export interface ECSServiceStatus {
  readonly name: string
  readonly tasks_running: number
  readonly tasks_desired: number
  readonly cpu_percent: number
  readonly memory_percent: number
  readonly last_deployment_at: ISODateString
}

export interface SQSQueueStatus {
  readonly name: string
  readonly depth: number
  readonly oldest_message_age_seconds: number
  readonly dlq_depth: number
}

export interface AWSStatus {
  readonly ecs_services: readonly ECSServiceStatus[]
  readonly sqs_queues: readonly SQSQueueStatus[]
  readonly rds_connections: number
  readonly rds_cpu_percent: number
  readonly rds_free_storage_gb: number
  readonly s3_evidence_size_gb: number
  readonly api_latency_p50_ms: number
  readonly api_latency_p95_ms: number
  readonly api_latency_p99_ms: number
  readonly worker_health: WorkerHealthStatus
  readonly checked_at: ISODateString
}

// ---- API error ----------------------------------------------------------------------------------------------------------------------------------

export interface ApiError {
  readonly detail: string
  readonly code: string
  readonly request_id: string | null
}

// ---- Audit log ----------------------------------------------------------------------------------------------------------------------------------

export interface AuditLogEntry {
  readonly id: UUID
  readonly user_id: UUID
  readonly user_name: string
  readonly action: string
  readonly resource_type: string
  readonly resource_id: UUID
  readonly ip_address: string
  readonly user_agent: string
  readonly occurred_at: ISODateString
  readonly outcome: 'success' | 'failure' | 'denied'
  readonly metadata: Record<string, unknown>
}

// ---- Brand helpers (safe casts for sample data only) ------------------------------------------------------
// Use ONLY in /data/ files. Real API data arrives already typed correctly.
export const asISO = (s: string): ISODateString => s as unknown as ISODateString
export const asUUID = (s: string): UUID => (s as unknown) as UUID
export const asHash = (s: string): SHA256Hash => (s as unknown) as SHA256Hash
