import type { IncidentSeverity, IncidentStatus, NotificationStatus, Jurisdiction } from '@/types'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Shield, Clock, Database, FileText,
  CheckCircle, AlertCircle, Terminal, Lock, Globe,
} from 'lucide-react'
import { SeverityBadge } from '@/components/ui/SeverityBadge'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useIncident, useEvidence, useNotifications } from '@/hooks/useApi'
import {
  formatDate, timeAgo, formatBytes, shortHash,
  NOTIF_STATUS_CONFIG, JURISDICTION_CONFIG,
} from '@/utils'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16, ...style }}>
      {children}
    </div>
  )
}

function CardHead({ icon, title, extra }: { icon: React.ReactNode; title: string; extra?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
      {icon}
      <span style={{ fontSize: 11, fontWeight: 500, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{title}</span>
      {extra && <span style={{ marginLeft: 'auto' }}>{extra}</span>}
    </div>
  )
}

function SkeletonRow() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {[90, 70, 80].map((w, i) => (
        <div key={i} style={{ height: 12, background: PARCH, borderRadius: 2, width: `${w}%` }} />
      ))}
    </div>
  )
}

export default function IncidentDetailPage() {
  const { id }   = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Guard: 'new' is not a UUID — hooks must be called unconditionally (Rules of Hooks),
  // so we pass enabled:false instead of skipping the call.
  const isNew = id === 'new' || !id
  const { data: incident,      isLoading: incLoading,  isError: incError  } = useIncident(isNew ? '' : id!)
  const { data: evidenceList,  isLoading: evLoading,   isError: evError   } = useEvidence(isNew ? '' : id!)
  const { data: notifResponse, isLoading: notifLoading                     } = useNotifications(isNew ? undefined : { incidentId: id })

  const evidence      = evidenceList ?? []
  const notifications = notifResponse?.items ?? []

  // Redirect 'new' to the dedicated create page
  if (isNew) {
    navigate('/incidents/new', { replace: true })
    return null
  }

  // Loading state
  if (incLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1100 }}>
        <div style={{ height: 14, background: PARCH, borderRadius: 2, width: 120 }} />
        <div style={{ background: BLACK, borderRadius: 4, padding: '20px 24px' }}>
          <SkeletonRow />
        </div>
      </div>
    )
  }

  // Error / not found state
  if (incError || !incident) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0', color: GRAY }}>
        <Shield style={{ width: 40, height: 40, opacity: 0.2, margin: '0 auto 12px' }} aria-hidden="true" />
        <p style={{ fontSize: 12 }}>
          {incError ? `Failed to load incident from GET /api/v1/incidents/${id}` : 'Incident not found'}
        </p>
        <button onClick={() => navigate('/incidents')} style={{ marginTop: 12, color: ORANGE, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>
          Back to incidents
        </button>
      </div>
    )
  }

  // Build timeline from real incident data (actions + timeline events from IncidentDetail)
  const timelineBase = [
    {
      type: 'DETECTION',
      actor: incident.ml_model_version ? `ML v${incident.ml_model_version}` : 'ML classifier',
      desc: `Breach detected. Confidence: ${incident.confidence_score != null ? Math.round(incident.confidence_score * 100) + '%' : 'N/A'}.`,
      time: incident.detected_at,
      color: ORANGE,
    },
    {
      type: 'TRIAGE',
      actor: 'lbro-api',
      desc: `Severity: ${incident.severity}. Jurisdictions: ${incident.affected_jurisdictions?.join(', ') || 'none'}.`,
      time: new Date(new Date(incident.detected_at).getTime() + 30000).toISOString(),
      color: '#d97706',
    },
    ...(incident.closed_at ? [{ type: 'CLOSED', actor: 'analyst', desc: 'Incident reviewed and closed.', time: incident.closed_at, color: '#3a7a50' }] : []),
  ]

  // Append real timeline events from IncidentDetail if available
  const detailTimeline = (incident as any).timeline as Array<{ event_type: string; actor: string; description: string; occurred_at: string }> | undefined
  const timeline = detailTimeline?.length
    ? detailTimeline.map(t => ({ type: t.event_type, actor: t.actor, desc: t.description, time: t.occurred_at, color: GRAY }))
    : timelineBase

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1100 }}>
      {/* Back + Header */}
      <div>
        <button
          onClick={() => navigate('/incidents')}
          style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: GRAY, background: 'none', border: 'none', cursor: 'pointer', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.08em' }}
        >
          <ArrowLeft style={{ width: 14, height: 14 }} aria-hidden="true" />
          Back to incidents
        </button>

        <div style={{ background: BLACK, borderRadius: 4, padding: '20px 24px' }}>
          <div style={{ fontSize: 10, color: ORANGE, textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 6 }}>
            / {incident.severity} -- {incident.external_id ?? id} /
          </div>
          <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 42, color: '#f0ebe2', letterSpacing: '0.03em', lineHeight: 1, marginBottom: 8 }}>
            {incident.title}
          </h1>
          <p style={{ fontSize: 11, color: '#5a5450', marginBottom: 14, maxWidth: 600 }}>{incident.description}</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <SeverityBadge severity={incident.severity as IncidentSeverity} pulse={incident.severity === 'critical'} />
            <StatusBadge status={incident.status as IncidentStatus} />
            {incident.external_id && <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#444' }}>{incident.external_id}</span>}
          </div>
        </div>
      </div>

      {/* Meta row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {[
          { label: 'Attack category', value: incident.attack_category ?? '--',                           icon: Shield,   mono: false },
          { label: 'Source IP',       value: incident.source_ip ?? '--',                                 icon: Globe,    mono: true  },
          { label: 'Detected',        value: timeAgo(incident.detected_at),                             icon: Clock,    mono: false },
          { label: 'Confidence',      value: incident.confidence_score != null ? `${Math.round(incident.confidence_score * 100)}%` : '--', icon: Database, mono: true },
        ].map(({ label, value, icon: Icon, mono }) => (
          <div key={label} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: GRAY, marginBottom: 6 }}>
              <Icon style={{ width: 11, height: 11 }} aria-hidden="true" />
              {label}
            </div>
            <div style={{ fontSize: 13, fontWeight: 500, color: BLACK, fontFamily: mono ? 'JetBrains Mono, monospace' : undefined }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Main grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16 }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Timeline */}
          <Card>
            <CardHead icon={<Clock style={{ width: 14, height: 14, color: ORANGE }} />} title="Attack Timeline" />
            <div>
              {timeline.map((evt, i) => (
                <div key={i} style={{ display: 'flex', gap: 12, paddingBottom: i < timeline.length - 1 ? 14 : 0, position: 'relative' }}>
                  {i < timeline.length - 1 && (
                    <div style={{ position: 'absolute', left: 6, top: 18, bottom: 0, width: 1, background: BORDER }} />
                  )}
                  <div style={{ width: 13, height: 13, borderRadius: '50%', background: evt.color, flexShrink: 0, marginTop: 2, zIndex: 1 }} />
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: evt.color }}>{evt.type}</span>
                      <span style={{ fontSize: 10, color: GRAY }}>· {evt.actor}</span>
                    </div>
                    <p style={{ fontSize: 12, color: BLACK, marginTop: 2 }}>{evt.desc}</p>
                    <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: GRAY, marginTop: 2 }}>{formatDate(evt.time)}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Evidence */}
          <Card>
            <CardHead
              icon={<Lock style={{ width: 14, height: 14, color: ORANGE }} />}
              title="Forensic Evidence"
              extra={<span style={{ fontSize: 10, color: GRAY }}>S3 Object Lock (WORM)</span>}
            />
            {evLoading ? (
              <SkeletonRow />
            ) : evError ? (
              <p style={{ fontSize: 11, color: GRAY }}>
                Failed to load from <code style={{ fontFamily: 'JetBrains Mono, monospace' }}>GET /api/v1/incidents/{id}/evidence</code>
              </p>
            ) : evidence.length === 0 ? (
              <p style={{ fontSize: 11, color: GRAY }}>No evidence packages collected.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {evidence.map(ev => (
                  <div key={ev.id} style={{ border: `1px solid ${BORDER}`, borderRadius: 4, padding: '10px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
                      <div>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: ORANGE }}>
                          {ev.content_type.split('/').pop()?.toUpperCase() ?? 'FILE'}
                        </span>
                        {ev.file_size > 0 && <span style={{ fontSize: 10, color: GRAY, marginLeft: 8 }}>{formatBytes(ev.file_size)}</span>}
                        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, marginTop: 2 }}>{ev.filename}</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, fontSize: 10 }}>
                          <span style={{ color: GRAY }}>SHA-256:</span>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: '#3a7a50' }}>{shortHash(ev.sha256_hash)}</span>
                        </div>
                      </div>
                      <button style={{ fontSize: 10, color: ORANGE, border: `1px solid rgba(229,78,27,0.3)`, padding: '4px 10px', borderRadius: 2, background: 'rgba(229,78,27,0.06)', cursor: 'pointer', flexShrink: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        Download
                      </button>
                    </div>
                    <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 8 }}>
                      <p style={{ fontSize: 10, color: GRAY, marginBottom: 5, fontWeight: 500 }}>Chain of custody</p>
                      {ev.custody_chain.map((c, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, marginBottom: 3 }}>
                          <CheckCircle style={{ width: 11, height: 11, color: '#3a7a50', flexShrink: 0 }} aria-hidden="true" />
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: GRAY, width: 64, flexShrink: 0 }}>{formatDate(c.created_at, 'HH:mm:ss')}</span>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: ORANGE, fontWeight: 600 }}>{c.action}</span>
                          {c.notes && <span style={{ color: GRAY }}>· {c.notes}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Regulatory notifications */}
          <Card>
            <CardHead icon={<FileText style={{ width: 14, height: 14, color: ORANGE }} />} title="Regulatory Notifications" />
            {notifLoading ? (
              <SkeletonRow />
            ) : notifications.length === 0 ? (
              <p style={{ fontSize: 11, color: GRAY }}>No notifications required.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {notifications.map(n => {
                  // Use real API field names: n.regulation, n.authority, n.deadline
                  const regKey = (n.regulation ?? n.jurisdiction) as Jurisdiction
                  const jcfg   = JURISDICTION_CONFIG[regKey]
                  const deadlineMs = new Date(n.deadline).getTime()
                  const hoursLeft  = (deadlineMs - Date.now()) / (1000 * 3600)
                  const isOverdue  = deadlineMs < Date.now()
                  const deadlineColor = isOverdue ? ORANGE : hoursLeft < 12 ? '#d97706' : '#3a7a50'

                  const STATUS_CFG: Record<string, { label: string }> = {
                    pending:  { label: 'Pending'  },
                    approved: { label: 'Approved' },
                    sent:     { label: 'Sent'     },
                    failed:   { label: 'Failed'   },
                  }
                  const sc = STATUS_CFG[n.status] ?? { label: n.status }

                  return (
                    <div key={n.id} style={{ border: `1px solid ${BORDER}`, borderRadius: 4, padding: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 13, fontWeight: 500, color: BLACK }}>{jcfg?.flag} {regKey}</span>
                        <span style={{ fontSize: 9, padding: '2px 6px', border: `1px solid ${BORDER}`, borderRadius: 2, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          {sc.label}
                        </span>
                      </div>
                      <p style={{ fontSize: 10, color: GRAY, marginBottom: 8 }}>{n.authority}</p>
                      {[
                        ['Deadline', formatDate(n.deadline, 'MMM dd HH:mm')],
                        ['Remaining', isOverdue ? `${Math.abs(Math.round(hoursLeft))}h OVERDUE` : `${Math.round(hoursLeft)}h`],
                      ].map(([k, v], i) => (
                        <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginBottom: 4 }}>
                          <span style={{ color: GRAY }}>{k}</span>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: i === 1 ? deadlineColor : BLACK }}>{v}</span>
                        </div>
                      ))}
                      {!isOverdue && (
                        <div style={{ marginTop: 6, height: 3, background: PARCH, borderRadius: 2, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.min(100, (hoursLeft / (jcfg?.hours ?? 72)) * 100)}%`, background: deadlineColor, borderRadius: 2 }} />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          {/* Network details */}
          {(incident.destination_ip || incident.protocol) && (
            <Card>
              <CardHead icon={<AlertCircle style={{ width: 14, height: 14, color: '#d97706' }} />} title="Network Details" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  ['Destination IP',   incident.destination_ip ?? '--'],
                  ['Destination Port', incident.destination_port?.toString() ?? '--'],
                  ['Protocol',         incident.protocol ?? '--'],
                  ['Source Port',      incident.source_port?.toString() ?? '--'],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: GRAY }}>{k}</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BLACK }}>{v}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Data classification */}
          <Card>
            <CardHead icon={<Shield style={{ width: 14, height: 14, color: ORANGE }} />} title="Data Classification" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                { label: 'Personal data',   active: incident.personal_data_involved,                    color: '#7c3aed' },
                { label: 'Health data',     active: incident.health_data_involved,                      color: ORANGE   },
                { label: 'GDPR notifiable', active: incident.affected_jurisdictions?.includes('EU'),    color: '#3b82f6' },
                { label: 'HIPAA notifiable',active: incident.affected_jurisdictions?.includes('US'),    color: '#a78bfa' },
                { label: 'DPDPA notifiable',active: incident.affected_jurisdictions?.includes('IN'),    color: ORANGE   },
              ].map(({ label, active, color }) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                  <span style={{ color: GRAY }}>{label}</span>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: active ? color : BORDER }}>
                    {active ? 'YES' : 'NO'}
                  </span>
                  </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
