/**
 * IncidentDetailPage — full investigation workspace.
 *
 * Tabs: Overview | Timeline | Raw Event | Evidence | Notes | IOC | Related
 * Right sidebar: Attack Explanation · Recommendations · Actions
 */
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Shield, FileText, Clock, Terminal,
  Lock, StickyNote, Globe, Users, Download,
  AlertTriangle, CheckCircle, TrendingUp, User,
  ChevronUp, ChevronDown, Sparkles, Wrench, BookOpen,
  ExternalLink, Target, Zap,
} from 'lucide-react'
import { SeverityBadge } from '@/components/ui/SeverityBadge'
import { StatusBadge } from '@/components/ui/StatusBadge'
import type { IncidentSeverity, IncidentStatus } from '@/types'
import {
  useIncident, useIncidentExplanation, useNotifications,
} from '@/hooks/useApi'
import { incidentsApi } from '@/api/client'
import { investigationApi } from '@/api/client'
import { getAccessToken } from '@/store/authStore'
import { formatDate, timeAgo, NOTIF_STATUS_CONFIG, JURISDICTION_CONFIG } from '@/utils'
import type { Jurisdiction } from '@/types'

// Tab components
import { OverviewTab  } from '@/components/incidents/tabs/OverviewTab'
import { TimelineTab  } from '@/components/incidents/tabs/TimelineTab'
import { RawEventTab  } from '@/components/incidents/tabs/RawEventTab'
import { EvidenceTab  } from '@/components/incidents/tabs/EvidenceTab'
import { NotesTab     } from '@/components/incidents/tabs/NotesTab'
import { IOCTab       } from '@/components/incidents/tabs/IOCTab'
import { RelatedTab   } from '@/components/incidents/tabs/RelatedTab'

// Shared
const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'
const GREEN  = '#3a7a50'

// ─── Tab definition ─────────────────────────────────────────────────────────

interface Tab { id: string; label: string; icon: React.ReactNode }

const TABS: Tab[] = [
  { id: 'overview',  label: 'Overview',   icon: <Shield    style={{ width: 12, height: 12 }} /> },
  { id: 'timeline',  label: 'Timeline',   icon: <Clock     style={{ width: 12, height: 12 }} /> },
  { id: 'raw',       label: 'Raw Event',  icon: <Terminal  style={{ width: 12, height: 12 }} /> },
  { id: 'evidence',  label: 'Evidence',   icon: <Lock      style={{ width: 12, height: 12 }} /> },
  { id: 'notes',     label: 'Notes',      icon: <StickyNote style={{ width: 12, height: 12 }} /> },
  { id: 'ioc',       label: 'IOC',        icon: <Globe     style={{ width: 12, height: 12 }} /> },
  { id: 'related',   label: 'Related',    icon: <Users     style={{ width: 12, height: 12 }} /> },
]

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 1300 }}>
      <div style={{ height: 14, background: PARCH, borderRadius: 2, width: 120 }} />
      <div style={{ background: BLACK, borderRadius: 4, padding: '20px 24px' }}>
        {[90, 60, 45].map((w, i) => (
          <div key={i} style={{ height: i === 0 ? 36 : 12, background: '#222', borderRadius: 2, width: `${w}%`, marginBottom: 10 }} />
        ))}
      </div>
    </div>
  )
}

// ─── Sidebar: Attack Explanation ─────────────────────────────────────────────

const LIKELIHOOD_COLOR: Record<string, string> = {
  Low: '#22c55e', Medium: '#f59e0b', High: '#f97316', Critical: '#ef4444',
}

function ExplainPanel({ incidentId }: { incidentId: string }) {
  const [open, setOpen] = useState(false)
  const { data, isLoading, isError } = useIncidentExplanation(open ? incidentId : '')
  const lc = data ? (LIKELIHOOD_COLOR[data.likelihood] ?? ORANGE) : ORANGE

  return (
    <div style={{ border: `1px solid ${ORANGE}30`, borderLeft: `3px solid ${ORANGE}`, borderRadius: 4, overflow: 'hidden', marginBottom: 10 }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: `${ORANGE}05`, border: 'none', cursor: 'pointer', textAlign: 'left' }}
      >
        <Sparkles style={{ width: 13, height: 13, color: ORANGE, flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: BLACK, flex: 1 }}>Attack Explanation</span>
        {open ? <ChevronUp style={{ width: 12, height: 12, color: GRAY }} /> : <ChevronDown style={{ width: 12, height: 12, color: GRAY }} />}
      </button>
      {open && (
        <div style={{ padding: '12px 14px', background: CREAM, borderTop: `1px solid ${BORDER}` }}>
          {isLoading && <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>{[80,60,90].map((w,i)=><div key={i} style={{ height: 10, background: PARCH, borderRadius: 2, width: `${w}%` }}/>)}</div>}
          {isError && <p style={{ fontSize: 11, color: GRAY }}>Could not load explanation.</p>}
          {data && (
            <>
              <p style={{ fontSize: 11, color: BLACK, lineHeight: 1.7, marginBottom: 10 }}>{data.plain_english}</p>
              {data.context && <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: GRAY, background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 3, padding: '6px 9px', marginBottom: 10 }}>{data.context}</p>}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: lc, background: `${lc}15`, border: `1px solid ${lc}40`, borderRadius: 2, padding: '2px 8px' }}>{data.likelihood}</span>
                <span style={{ fontSize: 10, color: GRAY }}>escalation risk</span>
              </div>
              {data.owasp && <div style={{ marginBottom: 6 }}><span style={{ fontSize: 9, color: '#3b82f6', background: '#3b82f615', border: '1px solid #3b82f640', borderRadius: 2, padding: '2px 7px', fontFamily: 'JetBrains Mono, monospace' }}>{data.owasp}</span></div>}
              {data.mitre_attack?.length > 0 && data.mitre_attack.map(m => <span key={m} style={{ display: 'inline-block', fontSize: 9, color: '#8b5cf6', background: '#8b5cf615', border: '1px solid #8b5cf640', borderRadius: 2, padding: '2px 7px', marginRight: 4, marginBottom: 4, fontFamily: 'JetBrains Mono, monospace' }}>{m}</span>)}
              {data.learn_more_url && <a href={data.learn_more_url} target="_blank" rel="noopener noreferrer" style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: ORANGE, marginTop: 6, textDecoration: 'none', fontFamily: 'JetBrains Mono, monospace' }}><Target style={{ width: 10, height: 10 }} />Learn more<ExternalLink style={{ width: 9, height: 9 }} /></a>}
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Sidebar: Recommendations ─────────────────────────────────────────────────

function RecsPanel({ incidentId }: { incidentId: string }) {
  const [open, setOpen] = useState(false)
  const { data } = useIncidentExplanation(open ? incidentId : '')

  return (
    <div style={{ border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden', marginBottom: 10 }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: PARCH, border: 'none', cursor: 'pointer', textAlign: 'left' }}
      >
        <Wrench style={{ width: 12, height: 12, color: GREEN, flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: BLACK, flex: 1 }}>Recommendations</span>
        {open ? <ChevronUp style={{ width: 12, height: 12, color: GRAY }} /> : <ChevronDown style={{ width: 12, height: 12, color: GRAY }} />}
      </button>
      {open && (
        <div style={{ padding: '10px 12px', background: CREAM, borderTop: `1px solid ${BORDER}` }}>
          {!data ? <p style={{ fontSize: 11, color: GRAY }}>Loading…</p> : (
            <>
              <p style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>Immediate Actions</p>
              {data.recommended_fixes.slice(0, 3).map((fix, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 7 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: ORANGE, flexShrink: 0 }}>{i + 1}.</span>
                  <p style={{ fontSize: 11, color: BLACK, lineHeight: 1.6, margin: 0 }}>{fix}</p>
                </div>
              ))}
              {data.recommended_fixes.length > 3 && (
                <>
                  <p style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.07em', margin: '10px 0 8px' }}>Long-term Remediation</p>
                  {data.recommended_fixes.slice(3).map((fix, i) => (
                    <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 7 }}>
                      <span style={{ fontSize: 10, color: GRAY, flexShrink: 0 }}>◦</span>
                      <p style={{ fontSize: 11, color: BLACK, lineHeight: 1.6, margin: 0 }}>{fix}</p>
                    </div>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Sidebar: Compliance Alerts ───────────────────────────────────────────────

function CompliancePanel({ incidentId }: { incidentId: string }) {
  const { data: notifResponse } = useNotifications({ incidentId })
  const notifications = notifResponse?.items ?? []
  if (notifications.length === 0) return null

  return (
    <div style={{ border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: PARCH }}>
        <FileText style={{ width: 12, height: 12, color: '#3b82f6', flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: BLACK }}>Compliance Alerts</span>
        <span style={{ marginLeft: 'auto', fontSize: 9, color: GRAY }}>{notifications.length}</span>
      </div>
      <div style={{ padding: '8px 10px', background: CREAM }}>
        {notifications.slice(0, 3).map(n => {
          const regKey = (n.regulation ?? n.jurisdiction) as Jurisdiction
          const jcfg = JURISDICTION_CONFIG[regKey]
          const hoursLeft = (new Date(n.deadline).getTime() - Date.now()) / 3_600_000
          const isOverdue = hoursLeft < 0
          const dc = isOverdue ? ORANGE : hoursLeft < 12 ? '#d97706' : GREEN
          return (
            <div key={n.id} style={{ border: `1px solid ${BORDER}`, borderRadius: 3, padding: '7px 9px', marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>{jcfg?.flag} {regKey}</span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, fontWeight: 700, color: dc }}>
                  {isOverdue ? `${Math.abs(Math.round(hoursLeft))}h OVERDUE` : `${Math.round(hoursLeft)}h left`}
                </span>
              </div>
              <p style={{ fontSize: 9, color: GRAY }}>{n.authority}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Sidebar: Actions ─────────────────────────────────────────────────────────

function ActionsPanel({ incidentId, incidentTitle }: { incidentId: string; incidentTitle: string }) {
  const navigate = useNavigate()
  const [downloading, setDownloading] = useState<string | null>(null)

  const downloadReport = async () => {
    setDownloading('report')
    try {
      const token = getAccessToken()
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(`/api/v1/incidents/${incidentId}/report`, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const cd = res.headers.get('content-disposition') ?? ''
      const m = cd.match(/filename="?([^"]+)"?/)
      const a = document.createElement('a')
      a.href = url; a.download = m?.[1] ?? `incident_report_${incidentId.slice(0,8)}.pdf`
      a.click(); URL.revokeObjectURL(url)
    } catch { alert('Report generation failed.') }
    finally { setDownloading(null) }
  }

  const downloadIOC = async () => {
    setDownloading('ioc')
    try {
      const d = await investigationApi.ioc(incidentId)
      const lines = [
        `# LBRO IOC Export — ${incidentId}`,
        '', '## Source IPs', ...d.ips.filter(i=>i.role==='source').map(i=>i.ip),
        '', '## Destination IPs', ...d.ips.filter(i=>i.role==='destination').map(i=>i.ip),
        '', '## SHA-256 Hashes', ...d.hashes.map(h=>`${h.hash}  ${h.filename}`),
        '', '## Ports', ...d.ports.map(p=>`${p.port}/${p.protocol}`),
        '', '## Protocols', ...d.protocols,
        '', '## MITRE', ...d.mitre_techniques,
        `\nOWASP: ${d.owasp_category ?? 'N/A'}`,
      ]
      const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `ioc_${incidentId.slice(0,8)}.txt`; a.click()
      URL.revokeObjectURL(url)
    } catch { alert('IOC export failed.') }
    finally { setDownloading(null) }
  }

  const btn = (label: string, onClick: ()=>void, key: string, color=GRAY) => (
    <button
      key={key}
      onClick={onClick}
      disabled={downloading === key}
      style={{
        width: '100%', textAlign: 'left', fontSize: 10, color: downloading === key ? GRAY : color,
        border: `1px solid ${BORDER}`, background: 'white', borderRadius: 2,
        padding: '7px 10px', cursor: downloading === key ? 'wait' : 'pointer',
        marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.06em',
        fontWeight: 500, transition: 'border-color .15s',
      }}
    >
      {downloading === key ? 'Generating…' : label}
    </button>
  )

  return (
    <div style={{ border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: PARCH }}>
        <Zap style={{ width: 12, height: 12, color: ORANGE, flexShrink: 0 }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: BLACK }}>Incident Actions</span>
      </div>
      <div style={{ padding: '8px 10px', background: CREAM }}>
        {btn('Generate PDF Report', downloadReport, 'report', ORANGE)}
        {btn('Download IOC File',   downloadIOC,    'ioc')}
        {btn('Open in New Tab', () => window.open(window.location.href, '_blank'), 'newtab')}
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function IncidentDetailPage() {
  const { id }   = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('overview')

  const isNew = id === 'new' || !id
  const { data: incident, isLoading, isError } = useIncident(isNew ? '' : id!)

  if (isNew) { navigate('/incidents/new', { replace: true }); return null }
  if (isLoading) return <Skeleton />

  if (isError || !incident) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0', color: GRAY }}>
        <Shield style={{ width: 40, height: 40, opacity: 0.2, margin: '0 auto 12px' }} />
        <p style={{ fontSize: 12 }}>Incident not found or could not be loaded.</p>
        <button onClick={() => navigate('/incidents')} style={{ marginTop: 12, color: ORANGE, background: 'none', border: 'none', cursor: 'pointer', fontSize: 12 }}>
          ← Back to incidents
        </button>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxWidth: 1300 }}>

      {/* ── Back nav ─────────────────────────────────────────────────────── */}
      <button
        onClick={() => navigate('/incidents')}
        style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: GRAY, background: 'none', border: 'none', cursor: 'pointer', marginBottom: 14, textTransform: 'uppercase', letterSpacing: '0.08em', alignSelf: 'flex-start' }}
      >
        <ArrowLeft style={{ width: 13, height: 13 }} />
        All incidents
      </button>

      {/* ── Hero header ──────────────────────────────────────────────────── */}
      <div style={{ background: BLACK, borderRadius: 4, padding: '20px 24px', marginBottom: 16 }}>
        <div style={{ fontSize: 9, color: ORANGE, textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 6 }}>
          / {incident.severity.toUpperCase()} — {incident.external_id ?? id?.slice(0, 8)} /
        </div>
        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 38, color: '#f0ebe2', letterSpacing: '0.03em', lineHeight: 1, marginBottom: 10 }}>
          {incident.title}
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <SeverityBadge severity={incident.severity as IncidentSeverity} pulse={incident.severity === 'critical'} />
          <StatusBadge   status={incident.status   as IncidentStatus}   />
          {incident.attack_category && (
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#8b5cf6', background: '#8b5cf615', border: '1px solid #8b5cf640', borderRadius: 2, padding: '2px 8px' }}>
              {incident.attack_category}
            </span>
          )}
          {incident.confidence_score != null && (
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#5a5450' }}>
              {Math.round(incident.confidence_score * 100)}% confidence
            </span>
          )}
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#5a5450', marginLeft: 'auto' }}>
            {timeAgo(incident.detected_at)}
          </span>
        </div>
      </div>

      {/* ── Main layout: tabs + sidebar ──────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 16, alignItems: 'start' }}>

        {/* Left: tab nav + content */}
        <div>
          {/* Tab bar */}
          <div style={{ display: 'flex', gap: 2, marginBottom: 14, borderBottom: `1px solid ${BORDER}`, overflowX: 'auto' }}>
            {TABS.map(tab => {
              const active = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 5, padding: '8px 14px',
                    fontSize: 10, fontWeight: active ? 700 : 400,
                    color: active ? ORANGE : GRAY,
                    background: 'none', border: 'none',
                    borderBottom: active ? `2px solid ${ORANGE}` : '2px solid transparent',
                    cursor: 'pointer', letterSpacing: '0.06em', textTransform: 'uppercase',
                    whiteSpace: 'nowrap', transition: 'color .15s',
                  }}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Tab content */}
          {activeTab === 'overview' && <OverviewTab incident={incident as any} />}
          {activeTab === 'timeline' && <TimelineTab incidentId={id!} />}
          {activeTab === 'raw'      && <RawEventTab incident={incident as any} />}
          {activeTab === 'evidence' && <EvidenceTab incidentId={id!} />}
          {activeTab === 'notes'    && <NotesTab    incidentId={id!} />}
          {activeTab === 'ioc'      && <IOCTab      incidentId={id!} />}
          {activeTab === 'related'  && <RelatedTab  incidentId={id!} />}
        </div>

        {/* Right sidebar */}
        <div style={{ position: 'sticky', top: 16, display: 'flex', flexDirection: 'column', gap: 0 }}>
          <ExplainPanel    incidentId={id!} />
          <RecsPanel       incidentId={id!} />
          <CompliancePanel incidentId={id!} />
          <ActionsPanel    incidentId={id!} incidentTitle={incident.title} />
        </div>

      </div>
    </div>
  )
}
