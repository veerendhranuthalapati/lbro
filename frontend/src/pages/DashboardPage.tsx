import { useNavigate } from 'react-router-dom'
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { SeverityBadge } from '@/components/ui/SeverityBadge'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useIncidents, useDashboardSummary } from '@/hooks/useApi'
import { timeAgo, truncate } from '@/utils'
import type { IncidentSeverity, IncidentStatus } from '@/types'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '8px 12px', fontSize: 11 }}>
      <div style={{ color: GRAY, marginBottom: 4 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color, display: 'inline-block' }} />
          <span style={{ color: GRAY, textTransform: 'capitalize' }}>{p.name}:</span>
          <span style={{ color: BLACK, fontWeight: 500 }}>{p.value?.toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

function MissingEndpointBanner({ endpoint }: { endpoint: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: 100, flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Endpoint not yet implemented</div>
      <code style={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', color: ORANGE, background: 'rgba(229,78,27,0.06)', border: `1px solid rgba(229,78,27,0.2)`, padding: '3px 8px', borderRadius: 2 }}>
        {endpoint}
      </code>
    </div>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()

  // Real API data — summary for KPIs, incidents for the recent table
  const { data: summary, isLoading: sumLoading } = useDashboardSummary()
  const { data: incidentsData, isLoading: incLoading, isError: incError } = useIncidents({ page_size: 10 })
  // flow/timeline/attack chart data: endpoints not yet implemented on backend
  const flowData = null
  const timelineData = null
  const flowErr = true
  const timelineErr = true

  const incidents = incidentsData?.items ?? []
  const pendingNotifs = summary?.pending_notifications ?? 0
  const critical      = summary?.critical_incidents ?? 0

  const kpis = [
    { label: 'Open incidents',        value: sumLoading ? '...' : (summary?.open_incidents ?? '--'),       note: 'across all severities',   orange: true  },
    { label: 'Critical',              value: sumLoading ? '...' : (summary?.critical_incidents ?? '--'),   note: 'immediate response',      orange: true  },
    { label: 'New (24h)',             value: sumLoading ? '...' : (summary?.new_last_24h ?? '--'),         note: 'detected last 24 hours',  orange: false },
    { label: 'Needs review',          value: sumLoading ? '...' : (summary?.needs_analyst_review ?? '--'), note: 'analyst review flagged',  orange: false },
    { label: 'Pending notifications', value: sumLoading ? '...' : pendingNotifs,                          note: 'GDPR / HIPAA / DPDPA',    orange: pendingNotifs > 0 },
    { label: 'Overdue compliance',    value: sumLoading ? '...' : (summary?.overdue_compliance ?? '--'),   note: 'past deadline, unmet',    orange: (summary?.overdue_compliance ?? 0) > 0 },
    { label: 'Total incidents',       value: sumLoading ? '...' : (summary?.total_incidents ?? '--'),      note: 'all time',                orange: false },
    { label: 'Evidence packages',     value: sumLoading ? '...' : (summary?.total_evidence ?? '--'),       note: 'stored in evidence vault', orange: false },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* ---- Hero block ---- */}
      <div style={{ background: BLACK, borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
        <svg
          viewBox="0 0 700 200"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.07 }}
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <defs>
            <pattern id="pgrid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M40 0L0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="700" height="200" fill="url(#pgrid)" />
          {[0.5, 1, 2].map((o, i) => (
            <g key={i}>
              <line x1="350" y1="0" x2={-50 + i * 200} y2="200" stroke="white" strokeWidth={o * 0.4} opacity={o * 0.4} />
              <line x1="350" y1="0" x2={750 - i * 200} y2="200" stroke="white" strokeWidth={o * 0.4} opacity={o * 0.4} />
            </g>
          ))}
          <rect x="120" y="60"  width="70"  height="28" fill={ORANGE} opacity="0.25" />
          <rect x="310" y="85"  width="100" height="18" fill={ORANGE} opacity="0.2"  />
          <rect x="470" y="50"  width="45"  height="50" fill={ORANGE} opacity="0.12" />
        </svg>

        <div style={{ position: 'relative', padding: '28px 32px' }}>
          <div style={{ fontSize: 10, color: ORANGE, textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 8 }}>
            / Breach Response Orchestrator /
          </div>
          <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 72, lineHeight: 0.9, color: '#f0ebe2', letterSpacing: '0.02em' }}>
            Law-Aware<br />
            <span style={{ color: ORANGE }}>Breach</span><br />
            Response
          </div>
          <div style={{ fontSize: 11, color: '#5a5450', marginTop: 12, maxWidth: 320, lineHeight: 1.7 }}>
            Real-time ML classification, regulatory obligation tracking, and automated compliance workflows.
          </div>

          <div style={{ display: 'flex', gap: 28, marginTop: 24, paddingTop: 20, borderTop: '1px solid #222' }}>
            {[
              { label: 'Open',         value: sumLoading ? '...' : (summary?.open_incidents ?? '--'),   orange: true  },
              { label: 'Critical',     value: sumLoading ? '...' : critical, orange: true  },
              { label: 'Notifications',value: pendingNotifs,                       orange: false },
              { label: 'ML accuracy',  value: '--',                                orange: false },
            ].map(s => (
              <div key={s.label}>
                <div style={{ fontSize: 10, color: '#555', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 34, color: s.orange ? ORANGE : '#f0ebe2', lineHeight: 1 }}>
                  {s.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ---- Status bar ---- */}
      {critical > 0 && (
        <div
          style={{ background: ORANGE, padding: '7px 16px', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer' }}
          onClick={() => navigate('/incidents')}
          role="alert"
        >
          <span style={{ fontSize: 10, color: '#fff', textTransform: 'uppercase', letterSpacing: '0.14em', fontWeight: 500 }}>
            / {critical} critical incident(s) need immediate attention
          </span>
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', marginLeft: 'auto' }}>View all</span>
        </div>
      )}

      {/* ---- KPI grid ---- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {kpis.map(k => (
          <div key={k.label} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>{k.label}</div>
            <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 36, color: k.orange ? ORANGE : BLACK, lineHeight: 1 }}>
              {k.value}
            </div>
            <div style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>{k.note}</div>
          </div>
        ))}
      </div>

      {/* ---- Charts row ---- */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {/* Flow volume */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, color: BLACK, fontWeight: 500 }}>Network flow volume</div>
            <div style={{ fontSize: 10, color: GRAY, marginTop: 2 }}>Benign �� Malicious �� Blocked</div>
          </div>
          {flowErr || !flowData ? (
            <MissingEndpointBanner endpoint="GET /api/v1/analytics/flow-volume" />
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={flowData as any[]} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="benignGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={ORANGE} stopOpacity={0.12} />
                    <stop offset="95%" stopColor={ORANGE} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                <XAxis dataKey="time" tick={{ fill: GRAY, fontSize: 9 }} interval={4} />
                <YAxis tick={{ fill: GRAY, fontSize: 9 }} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="benign"    stroke={ORANGE}   fill="url(#benignGrad)" strokeWidth={1.5} dot={false} />
                <Area type="monotone" dataKey="malicious" stroke="#d97706"  fill="none"              strokeWidth={1.5} dot={false} />
                <Area type="monotone" dataKey="blocked"   stroke={GRAY}     fill="none"              strokeWidth={1}   dot={false} strokeDasharray="4 2" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Incident timeline bar */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, color: BLACK, fontWeight: 500 }}>Incident timeline (24h)</div>
            <div style={{ fontSize: 10, color: GRAY, marginTop: 2 }}>By severity per hour</div>
          </div>
          {timelineErr || !timelineData ? (
            <MissingEndpointBanner endpoint="GET /api/v1/analytics/incident-timeline" />
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={(timelineData as any[]).slice(0, 12)} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                <XAxis dataKey="hour" tick={{ fill: GRAY, fontSize: 9 }} interval={2} />
                <YAxis tick={{ fill: GRAY, fontSize: 9 }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="critical" stackId="a" fill={ORANGE}    />
                <Bar dataKey="high"     stackId="a" fill="#d97706"   />
                <Bar dataKey="medium"   stackId="a" fill={GRAY}      />
                <Bar dataKey="low"      stackId="a" fill="#3a7a50" radius={[2,2,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ---- Recent incidents table ---- */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', borderBottom: `1px solid ${BORDER}` }}>
          <div>
            <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Recent incidents</span>
            <span style={{ fontSize: 10, color: GRAY, marginLeft: 8 }}>Live from API</span>
          </div>
          <button
            onClick={() => navigate('/incidents')}
            style={{ fontSize: 11, color: ORANGE, background: 'none', border: 'none', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          >
            View all
          </button>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['ID', 'Title', 'Severity', 'Status', 'Source IP', 'Detected'].map(h => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500, borderBottom: `1px solid ${BORDER}`, whiteSpace: 'nowrap' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {incLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} style={{ padding: '10px 16px', borderBottom: `1px solid ${BORDER}` }}>
                        <div style={{ height: 11, background: '#e8e2d9', borderRadius: 2, width: j === 1 ? '80%' : '55%' }} />
                      </td>
                    ))}
                  </tr>
                ))
              ) : incidents.slice(0, 6).map(inc => (
                <tr
                  key={inc.id}
                  onClick={() => navigate(`/incidents/${inc.id}`)}
                  className="table-row-hover"
                  style={{ cursor: 'pointer', transition: 'background 0.1s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#e8e2d9')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}
                >
                  <td style={{ padding: '10px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, borderBottom: `1px solid ${BORDER}`, whiteSpace: 'nowrap' }}>
                    {inc.external_id ?? inc.id.slice(0, 10)}
                  </td>
                  <td style={{ padding: '10px 16px', fontSize: 12, color: BLACK, borderBottom: `1px solid ${BORDER}`, fontWeight: 500 }}>
                    {truncate(inc.title, 38)}
                  </td>
                  <td style={{ padding: '10px 16px', borderBottom: `1px solid ${BORDER}` }}>
                    <SeverityBadge severity={inc.severity as IncidentSeverity} size="sm" />
                  </td>
                  <td style={{ padding: '10px 16px', borderBottom: `1px solid ${BORDER}` }}>
                    <StatusBadge status={inc.status as IncidentStatus} size="sm" />
                  </td>
                  <td style={{ padding: '10px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, borderBottom: `1px solid ${BORDER}`, whiteSpace: 'nowrap' }}>
                    {timeAgo(inc.detected_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!incLoading && !incError && incidents.length === 0 && (
            <div style={{ textAlign: 'center', padding: '32px 0', color: GRAY, fontSize: 12 }}>No incidents</div>
          )}
        </div>
      </div>
    </div>
  )
}