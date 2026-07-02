import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SeverityBadge } from '@/components/ui/SeverityBadge'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { useIncidents } from '@/hooks/useApi'
import { timeAgo } from '@/utils'
import type { IncidentSeverity, IncidentStatus } from '@/types'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

const SEV_DOT: Record<string, string> = {
  critical: '#e54e1b',
  high:     '#d97706',
  medium:   '#6b6560',
  low:      '#4ade80',
  info:     '#3b82f6',
}

export default function IncidentsPage() {
  const navigate = useNavigate()
  const [severityFilter, setSeverityFilter] = useState<IncidentSeverity | 'all'>('all')
  const [statusFilter,   setStatusFilter]   = useState<IncidentStatus | 'all'>('all')

  const { data, isLoading, isError } = useIncidents({
    severity:  severityFilter !== 'all' ? severityFilter : undefined,
    status:    statusFilter   !== 'all' ? statusFilter   : undefined,
    page_size: 100,
  })

  const incidents  = data?.items ?? []
  const totalCount = data?.total ?? 0

  const severities: (IncidentSeverity | 'all')[] = ['all', 'critical', 'high', 'medium', 'low', 'info']
  const statuses: (IncidentStatus | 'all')[] = ['all', 'new', 'triaging', 'contained', 'eradicating', 'recovering', 'closed', 'reopened']

  const filterBtn = (active: boolean) => ({
    padding: '5px 12px',
    fontSize: 10,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
    fontWeight: 500,
    border: `1px solid ${active ? ORANGE : BORDER}`,
    borderRadius: 2,
    background: active ? 'rgba(229,78,27,0.08)' : 'transparent',
    color: active ? ORANGE : GRAY,
    cursor: 'pointer',
    transition: 'all 0.1s',
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* ---- Header ---- */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
            All Incidents
          </h2>
          <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
            {isLoading ? 'Loading…' : `${totalCount} incident${totalCount !== 1 ? 's' : ''} · ML-classified threats`}
          </p>
        </div>
        <button
          onClick={() => navigate('/incidents/new')}
          style={{
            padding: '9px 20px',
            background: ORANGE,
            color: '#fff',
            border: 'none',
            borderRadius: 2,
            fontSize: 11,
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            cursor: 'pointer',
          }}
        >
          + New incident
        </button>
      </div>

      {/* ---- Filters ---- */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '12px 16px', display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
        <span style={{ fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginRight: 4 }}>Severity</span>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {severities.map(s => (
            <button key={s} onClick={() => setSeverityFilter(s)} style={filterBtn(severityFilter === s)}>
              {s === 'all' ? 'All' : s}
            </button>
          ))}
        </div>
        <div style={{ width: 1, height: 20, background: BORDER }} />
        <span style={{ fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginRight: 4 }}>Status</span>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {statuses.map(s => (
            <button key={s} onClick={() => setStatusFilter(s as any)} style={filterBtn(statusFilter === s)}>
              {s === 'all' ? 'All' : s}
            </button>
          ))}
        </div>
      </div>

      {/* ---- Error state ---- */}
      {isError && (
        <div style={{ background: 'rgba(229,78,27,0.06)', border: `1px solid rgba(229,78,27,0.3)`, borderLeft: `3px solid ${ORANGE}`, borderRadius: 4, padding: '12px 16px', fontSize: 12, color: BLACK }}>
          Failed to load incidents from <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>GET /api/v1/incidents</code> -- check that the backend is running.
        </div>
      )}

      {/* ---- Table ---- */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: PARCH }}>
              {['#', 'Title', 'Severity', 'Status', 'Source IP', 'Regulations', 'Confidence', 'Age'].map(h => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500, borderBottom: `1px solid ${BORDER}`, whiteSpace: 'nowrap' }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${BORDER}` }}>
                  {Array.from({ length: 8 }).map((_, j) => (
                    <td key={j} style={{ padding: '11px 14px' }}>
                      <div style={{ height: 12, background: PARCH, borderRadius: 2, width: j === 1 ? '80%' : '60%', animation: 'pulse 1.5s ease-in-out infinite' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : incidents.map((inc, idx) => (
              <tr
                key={inc.id}
                onClick={() => navigate(`/incidents/${inc.id}`)}
                style={{ cursor: 'pointer', transition: 'background 0.1s', borderBottom: `1px solid ${BORDER}` }}
                onMouseEnter={e => (e.currentTarget.style.background = PARCH)}
                onMouseLeave={e => (e.currentTarget.style.background = '')}
              >
                <td style={{ padding: '11px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, whiteSpace: 'nowrap' }}>
                  {String(idx + 1).padStart(3, '0')}
                </td>
                <td style={{ padding: '11px 14px', fontSize: 12, color: BLACK, fontWeight: 500, maxWidth: 280 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: SEV_DOT[inc.severity] ?? GRAY }} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{inc.title}</span>
                  </div>
                  {(inc.personal_data_involved || inc.health_data_involved) && (
                    <div style={{ marginTop: 3, display: 'flex', gap: 4 }}>
                      {inc.personal_data_involved && (
                        <span style={{ fontSize: 9, padding: '1px 5px', border: '1px solid rgba(124,58,237,0.3)', color: '#7c3aed', borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>PII</span>
                      )}
                      {inc.health_data_involved && (
                        <span style={{ fontSize: 9, padding: '1px 5px', border: '1px solid rgba(229,78,27,0.3)', color: ORANGE, borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>PHI</span>
                      )}
                    </div>
                  )}
                </td>
                <td style={{ padding: '11px 14px' }}>
                  <SeverityBadge severity={inc.severity as IncidentSeverity} size="sm" />
                </td>
                <td style={{ padding: '11px 14px' }}>
                  <StatusBadge status={inc.status as IncidentStatus} size="sm" />
                </td>
                <td style={{ padding: '11px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, whiteSpace: 'nowrap' }}>
                  {inc.source_ip ?? '--'}
                </td>
                <td style={{ padding: '11px 14px' }}>
                  {inc.affected_jurisdictions?.length ? (
                    <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                      {inc.affected_jurisdictions.map(j => (
                        <span key={j} style={{ fontSize: 9, padding: '1px 6px', border: `1px solid ${BORDER}`, borderRadius: 2, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          {j}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span style={{ fontSize: 10, color: BORDER }}>--</span>
                  )}
                </td>
                <td style={{ padding: '11px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, whiteSpace: 'nowrap' }}>
                  {inc.confidence_score != null ? `${Math.round(inc.confidence_score * 100)}%` : '--'}
                </td>
                <td style={{ padding: '11px 14px', fontSize: 10, color: GRAY, whiteSpace: 'nowrap' }}>
                  {timeAgo(inc.detected_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {!isLoading && !isError && incidents.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 0', color: GRAY }}>
            <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 32, color: BORDER, marginBottom: 8 }}>No Incidents</div>
            <div style={{ fontSize: 12 }}>No incidents match the current filters</div>
          </div>
        )}
      </div>
    </div>
  )
}
