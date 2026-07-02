import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Clock, AlertTriangle, CheckCircle,
  ChevronDown, ChevronUp, ExternalLink, Shield, Bell,
} from 'lucide-react'
import { useNotifications, useIncidents } from '@/hooks/useApi'
import { formatDate, JURISDICTION_CONFIG } from '@/utils'
import type { Jurisdiction } from '@/types'

// ---- Design tokens --------------------------------------------------------------------------------------------------------------------------
const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

// ---- Regulation config ------------------------------------------------------------------------------------------------------------------
const REGULATIONS = {
  GDPR: {
    full:        'General Data Protection Regulation',
    flag:        '🇪🇺',
    authority:   'Data Protection Commission',
    deadline_h:  72,
    color:       '#3b82f6',
    scope:       'Personal data of EU/EEA residents',
    obligations: [
      { id: 'g1', text: 'Notify supervisory authority within 72 hours',       critical: true  },
      { id: 'g2', text: 'Notify affected data subjects without undue delay',    critical: true  },
      { id: 'g3', text: 'Document breach in Article 33(5) register',           critical: false },
      { id: 'g4', text: 'Assess risk to natural persons',                       critical: false },
      { id: 'g5', text: 'Appoint or consult Data Protection Officer',           critical: false },
    ],
  },
  HIPAA: {
    full:        'Health Insurance Portability and Accountability Act',
    flag:        '🇺🇸',
    authority:   'HHS Office for Civil Rights',
    deadline_h:  1440,
    color:       '#a78bfa',
    scope:       'Protected Health Information (PHI)',
    obligations: [
      { id: 'h1', text: 'Notify HHS within 60 days of discovery',              critical: true  },
      { id: 'h2', text: 'Notify affected individuals without unreasonable delay',critical: true  },
      { id: 'h3', text: 'Notify media if breach affects >500 state residents',  critical: false },
      { id: 'h4', text: 'Maintain breach log for minimum 6 years',              critical: false },
    ],
  },
  DPDPA: {
    full:        'Digital Personal Data Protection Act',
    flag:        '🇮🇳',
    authority:   'Data Protection Board of India',
    deadline_h:  72,
    color:       ORANGE,
    scope:       'Personal data of Indian citizens',
    obligations: [
      { id: 'd1', text: 'Notify Data Protection Board within 72 hours',         critical: true  },
      { id: 'd2', text: 'Notify affected data principals',                       critical: true  },
      { id: 'd3', text: 'Submit detailed breach report to Board',                critical: false },
    ],
  },
}

// ---- Obligation compliance state (local UI state -- persisted per session) ------------
// TODO: backend endpoint needed: GET/POST /api/v1/compliance/obligations/{incidentId}
const INITIAL_STATE: Record<string, Record<string, boolean>> = {
  GDPR:  { g1: false, g2: false, g3: false, g4: false, g5: false },
  HIPAA: { h1: false, h2: false, h3: false, h4: false             },
  DPDPA: { d1: false, d2: false, d3: false                        },
}

// ---- Ring component ------------------------------------------------------------------------------------------------------------------------
function Ring({ pct, color, size = 64, stroke = 5 }: { pct: number; color: string; size?: number; stroke?: number }) {
  const r   = (size - stroke * 2) / 2
  const c   = 2 * Math.PI * r
  const off = c * (1 - pct / 100)
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={BORDER}  strokeWidth={stroke} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color}   strokeWidth={stroke}
        strokeDasharray={c} strokeDashoffset={off}
        strokeLinecap="round" transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
    </svg>
  )
}

function getScore(metState: Record<string, Record<string, boolean>>, reg: string) {
  const state = metState[reg] ?? {}
  const all   = Object.keys(state)
  const met   = Object.values(state).filter(Boolean).length
  return all.length ? Math.round((met / all.length) * 100) : 0
}

export default function CompliancePage() {
  const navigate  = useNavigate()
  const [expanded, setExpanded] = useState<string | null>('GDPR')
  const [metState, setMetState] = useState(INITIAL_STATE)

  const { data: notifResponse, isLoading: notifsLoading, isError: notifsError } = useNotifications()
  const { data: incidentsData } = useIncidents({ page_size: 100 })

  const toggle   = (reg: string) => setExpanded(v => v === reg ? null : reg)
  const markDone = (reg: string, id: string) =>
    setMetState(prev => ({ ...prev, [reg]: { ...prev[reg], [id]: !prev[reg]?.[id] } }))

  const notifList = notifResponse?.items ?? []

  // Compute derived fields from real API data (deadline, hours_remaining, is_overdue use real `deadline` field)
  const overdueCount    = notifList.filter(n => new Date(n.deadline).getTime() < Date.now()).length
  const pendingCount    = notifList.filter(n => n.status === 'pending').length
  const sentCount       = notifList.filter(n => n.status === 'sent').length
  const overall         = Math.round(
    Object.keys(REGULATIONS).map(r => getScore(metState, r)).reduce((a, b) => a + b, 0) /
    Object.keys(REGULATIONS).length
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 1060 }}>

      {/* ---- Page header ---- */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
            Compliance Center
          </h2>
          <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
            GDPR · HIPAA · DPDPA -- breach notification obligations and deadlines
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 52, color: overall >= 80 ? '#3a7a50' : overall >= 60 ? '#d97706' : ORANGE, lineHeight: 1 }}>
            {overall}%
          </div>
          <div style={{ fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: 2 }}>Overall score</div>
        </div>
      </div>

      {/* ---- API error state ---- */}
      {notifsError && (
        <div style={{ background: 'rgba(229,78,27,0.06)', border: `1px solid rgba(229,78,27,0.3)`, borderLeft: `3px solid ${ORANGE}`, borderRadius: 4, padding: '12px 16px', fontSize: 12, color: BLACK }}>
          Failed to load notifications from <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>GET /api/v1/notifications</code>
        </div>
      )}

      {/* ---- Overdue alert ---- */}
      {overdueCount > 0 && (
        <div
          role="alert"
          style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: 'rgba(229,78,27,0.06)', border: `1px solid rgba(229,78,27,0.3)`, borderLeft: `3px solid ${ORANGE}`, borderRadius: 4 }}
        >
          <AlertTriangle style={{ width: 15, height: 15, color: ORANGE, flexShrink: 0 }} aria-hidden="true" />
          <span style={{ fontSize: 12, color: BLACK }}>
            <strong style={{ color: ORANGE }}>{overdueCount} notification{overdueCount > 1 ? 's' : ''} overdue.</strong>
            <span style={{ color: GRAY, marginLeft: 6 }}>Regulatory deadlines missed -- immediate action required.</span>
          </span>
        </div>
      )}

      {/* ---- KPI strip ---- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {[
          { label: 'Pending dispatch', value: notifsLoading ? '…' : pendingCount, color: '#d97706', icon: Clock         },
          { label: 'Overdue',          value: notifsLoading ? '…' : overdueCount, color: ORANGE,    icon: AlertTriangle  },
          { label: 'Sent',             value: notifsLoading ? '…' : sentCount,    color: '#3a7a50', icon: CheckCircle    },
          { label: 'Total',            value: notifsLoading ? '…' : notifList.length, color: BLACK, icon: Bell          },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{label}</span>
              <Icon style={{ width: 13, height: 13, color }} aria-hidden="true" />
            </div>
            <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 36, color, lineHeight: 1 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* ---- Regulation breakdown + obligation checklists ---- */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {(Object.entries(REGULATIONS) as [keyof typeof REGULATIONS, typeof REGULATIONS.GDPR][]).map(([key, reg]) => {
          const score     = getScore(metState, key)
          const isOpen    = expanded === key
          const state     = metState[key] ?? {}
          const metCount  = Object.values(state).filter(Boolean).length
          const totalObl  = reg.obligations.length
          const r = 22, c = 2 * Math.PI * r, off = c * (1 - score / 100)

          return (
            <div key={key} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
              <button
                onClick={() => toggle(key)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
              >
                <div style={{ position: 'relative', width: 48, height: 48, flexShrink: 0 }}>
                  <svg width="48" height="48" viewBox="0 0 48 48" aria-hidden="true">
                    <circle cx="24" cy="24" r={r} fill="none" stroke={BORDER} strokeWidth="3.5" />
                    <circle cx="24" cy="24" r={r} fill="none" stroke={reg.color} strokeWidth="3.5"
                      strokeDasharray={c} strokeDashoffset={off}
                      strokeLinecap="round" transform="rotate(-90 24 24)"
                    />
                  </svg>
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, color: reg.color }}>
                    {score}%
                  </div>
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                    <span style={{ fontSize: 15 }}>{reg.flag}</span>
                    <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 20, color: reg.color, letterSpacing: '0.04em' }}>{key}</span>
                    <span style={{ fontSize: 11, color: GRAY }}>-- {reg.full}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 10, color: GRAY }}>
                    <span>{reg.authority}</span>
                    <span>·</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: reg.color, fontWeight: 700 }}>
                      {reg.deadline_h < 100 ? `${reg.deadline_h}h` : `${reg.deadline_h / 24} days`} deadline
                    </span>
                    <span>·</span>
                    <span>{metCount}/{totalObl} obligations met</span>
                  </div>
                </div>

                <div style={{ width: 120, flexShrink: 0 }}>
                  <div style={{ height: 4, background: PARCH, borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${score}%`, background: reg.color, borderRadius: 2, transition: 'width 0.5s ease' }} />
                  </div>
                </div>

                <div style={{ color: GRAY, marginLeft: 4 }}>
                  {isOpen ? <ChevronUp style={{ width: 15, height: 15 }} /> : <ChevronDown style={{ width: 15, height: 15 }} />}
                </div>
              </button>

              {isOpen && (
                <div style={{ borderTop: `1px solid ${BORDER}`, padding: '16px 16px 16px 78px' }}>
                  <p style={{ fontSize: 11, color: GRAY, marginBottom: 14, lineHeight: 1.6 }}>
                    <strong style={{ color: BLACK }}>Scope:</strong> {reg.scope}
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {reg.obligations.map(obl => {
                      const done = !!state[obl.id]
                      return (
                        <div
                          key={obl.id}
                          onClick={() => markDone(key, obl.id)}
                          style={{
                            display: 'flex', alignItems: 'flex-start', gap: 10, padding: '9px 12px',
                            border: `1px solid ${done ? 'rgba(58,122,80,0.3)' : obl.critical ? 'rgba(229,78,27,0.25)' : BORDER}`,
                            background: done ? 'rgba(58,122,80,0.04)' : 'transparent',
                            borderRadius: 4, cursor: 'pointer', transition: 'background 0.12s',
                          }}
                          onMouseEnter={e => { if (!done) (e.currentTarget as HTMLElement).style.background = PARCH }}
                          onMouseLeave={e => { if (!done) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                        >
                          <div style={{
                            width: 16, height: 16, borderRadius: 2, flexShrink: 0, marginTop: 1,
                            border: `1.5px solid ${done ? '#3a7a50' : obl.critical ? ORANGE : BORDER}`,
                            background: done ? '#3a7a50' : 'transparent',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            transition: 'background 0.12s, border-color 0.12s',
                          }}>
                            {done && (
                              <svg width="9" height="7" viewBox="0 0 9 7" fill="none" aria-hidden="true">
                                <path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                              </svg>
                            )}
                          </div>
                          <div style={{ flex: 1 }}>
                            <span style={{ fontSize: 12, color: done ? GRAY : BLACK, textDecoration: done ? 'line-through' : 'none' }}>
                              {obl.text}
                            </span>
                            {obl.critical && !done && (
                              <span style={{ marginLeft: 8, fontSize: 9, color: ORANGE, border: `1px solid rgba(229,78,27,0.3)`, padding: '1px 5px', borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                                Critical
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* ---- Overall health rings ---- */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
          <Shield style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
          <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Compliance health overview</span>
        </div>
        <div style={{ display: 'flex', gap: 0, alignItems: 'center' }}>
          {[
            ...Object.entries(REGULATIONS).map(([key, r]) => ({ label: key, pct: getScore(metState, key), color: r.color, sub: `${r.obligations.length} obligations` })),
            { label: 'Overall', pct: overall, color: '#3a7a50', sub: 'weighted average' },
          ].map(({ label, pct, color, sub }, i, arr) => (
            <div key={label} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '0 8px', borderRight: i < arr.length - 1 ? `1px solid ${BORDER}` : 'none' }}>
              <div style={{ position: 'relative', width: 72, height: 72 }}>
                <Ring pct={pct} color={color} size={72} stroke={5} />
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: pct >= 80 ? '#3a7a50' : pct >= 60 ? '#d97706' : ORANGE }}>{pct}%</span>
                </div>
              </div>
              <div style={{ fontSize: 11, fontWeight: 500, color: color, marginTop: 8, letterSpacing: '0.04em' }}>{label}</div>
              <div style={{ fontSize: 10, color: GRAY, marginTop: 2 }}>{sub}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ---- Notification obligations table ---- */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '13px 16px', borderBottom: `1px solid ${BORDER}` }}>
          <Bell style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
          <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Regulatory notification obligations</span>
          <span style={{ marginLeft: 'auto', fontSize: 10, color: GRAY }}>{notifList.length} total · live from API</span>
        </div>

        {notifsLoading ? (
          <div style={{ padding: '24px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[80, 65, 90, 70].map((w, i) => (
              <div key={i} style={{ height: 12, background: PARCH, borderRadius: 2, width: `${w}%` }} />
            ))}
          </div>
        ) : notifList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 0', color: GRAY, fontSize: 12 }}>
            No regulatory notifications
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: PARCH }}>
                {['Regulation', 'Incident', 'Authority', 'Deadline', 'Remaining', 'Status'].map(h => (
                  <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500, borderBottom: `1px solid ${BORDER}`, whiteSpace: 'nowrap' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {notifList.map((n, i) => {
                // Use real API field names: n.regulation, n.authority, n.deadline
                const regKey     = (n.regulation ?? n.jurisdiction) as keyof typeof REGULATIONS
                const jcfg       = JURISDICTION_CONFIG[regKey as Jurisdiction]
                const jxCfg      = REGULATIONS[regKey]
                const accent     = jxCfg?.color ?? GRAY
                const deadlineMs = new Date(n.deadline).getTime()
                const hoursLeft  = (deadlineMs - Date.now()) / (1000 * 3600)
                const isOverdue  = deadlineMs < Date.now()
                const urgColor   = isOverdue ? ORANGE : hoursLeft < 12 ? '#d97706' : '#3a7a50'

                const STATUS_CFG: Record<string, { label: string; color: string }> = {
                  pending:  { label: 'Pending',  color: '#d97706' },
                  approved: { label: 'Approved', color: '#3b82f6' },
                  sent:     { label: 'Sent',     color: '#3a7a50' },
                  failed:   { label: 'FAILED',   color: ORANGE    },
                }
                const sc = STATUS_CFG[n.status] ?? { label: n.status, color: GRAY }

                return (
                  <tr
                    key={n.id}
                    style={{ borderBottom: i < notifList.length - 1 ? `1px solid ${BORDER}` : 'none', cursor: 'default' }}
                    onMouseEnter={e => (e.currentTarget.style.background = PARCH)}
                    onMouseLeave={e => (e.currentTarget.style.background = '')}
                  >
                    <td style={{ padding: '11px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <span style={{ fontSize: 13 }}>{jcfg?.flag}</span>
                        <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 14, color: accent, letterSpacing: '0.04em' }}>{regKey}</span>
                      </div>
                    </td>
                    <td style={{ padding: '11px 14px' }}>
                      <button
                        onClick={() => navigate(`/incidents/${n.incident_id}`)}
                        style={{ fontSize: 11, color: ORANGE, background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'JetBrains Mono, monospace', padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}
                      >
                        {String(n.incident_id).slice(0, 10)}
                        <ExternalLink style={{ width: 10, height: 10, opacity: 0.6 }} aria-hidden="true" />
                      </button>
                    </td>
                    <td style={{ padding: '11px 14px', fontSize: 11, color: GRAY }}>{n.authority}</td>
                    <td style={{ padding: '11px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, whiteSpace: 'nowrap' }}>
                      {formatDate(n.deadline, 'MMM dd, HH:mm')}
                    </td>
                    <td style={{ padding: '11px 14px', minWidth: 100 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: urgColor, flexShrink: 0 }}>
                          {isOverdue ? `${Math.abs(Math.round(hoursLeft))}h OD` : `${Math.round(hoursLeft)}h`}
                        </span>
                        {!isOverdue && (
                          <div style={{ flex: 1, height: 3, background: PARCH, borderRadius: 2, overflow: 'hidden', minWidth: 36 }}>
                            <div style={{ height: '100%', width: `${Math.min(100, (hoursLeft / (jxCfg?.deadline_h ?? 72)) * 100)}%`, background: urgColor, borderRadius: 2 }} />
                          </div>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: '11px 14px' }}>
                      <span style={{ fontSize: 10, padding: '2px 7px', border: `1px solid`, borderColor: `${sc.color}40`, background: `${sc.color}0d`, borderRadius: 2, color: sc.color, fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                        {sc.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* ---- Regulation reference cards ---- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {(Object.entries(REGULATIONS) as [keyof typeof REGULATIONS, typeof REGULATIONS.GDPR][]).map(([key, reg]) => (
          <div key={key} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderTop: `3px solid ${reg.color}`, borderRadius: 4, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
              <span style={{ fontSize: 18 }}>{reg.flag}</span>
              <div>
                <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 18, color: reg.color, letterSpacing: '0.04em', lineHeight: 1 }}>{key}</div>
                <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Reference</div>
              </div>
            </div>
            <p style={{ fontSize: 10, color: BLACK, fontWeight: 500, marginBottom: 3 }}>{reg.full}</p>
            <p style={{ fontSize: 10, color: GRAY, marginBottom: 12, lineHeight: 1.6 }}>{reg.scope}</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5, fontSize: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderTop: `1px solid ${BORDER}` }}>
                <span style={{ color: GRAY }}>Authority</span>
                <span style={{ color: BLACK, fontWeight: 500, textAlign: 'right', maxWidth: '55%' }}>{reg.authority}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderTop: `1px solid ${BORDER}` }}>
                <span style={{ color: GRAY }}>Notification window</span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, color: reg.color }}>
                  {reg.deadline_h < 100 ? `${reg.deadline_h}h` : `${reg.deadline_h / 24} days`}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderTop: `1px solid ${BORDER}` }}>
                <span style={{ color: GRAY }}>Obligations</span>
                <span style={{ color: BLACK }}>{reg.obligations.length} items</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
