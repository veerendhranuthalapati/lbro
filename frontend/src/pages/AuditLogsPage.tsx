/**
 * AuditLogsPage — GET /api/v1/audit/logs
 * Shows user action history: who did what, when, from where.
 */
import { useState } from 'react'
import { ClipboardList, Search, ChevronLeft, ChevronRight, CheckCircle, AlertCircle, XCircle } from 'lucide-react'
import { useAuditLogs } from '@/hooks/useApi'
import { formatDate } from '@/utils'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

function StatusDot({ status }: { status: number | null }) {
  if (!status) return <span style={{ color: GRAY, fontSize: 11 }}>—</span>
  if (status < 300) return <CheckCircle style={{ width: 13, height: 13, color: '#4ade80' }} />
  if (status < 400) return <CheckCircle style={{ width: 13, height: 13, color: '#60a5fa' }} />
  if (status < 500) return <AlertCircle style={{ width: 13, height: 13, color: '#d97706' }} />
  return <XCircle style={{ width: 13, height: 13, color: ORANGE }} />
}

function ActionBadge({ action }: { action: string }) {
  const verb = action.split(':')[0] ?? action
  const color: Record<string, string> = {
    auth:      '#3b82f6',
    incidents: '#a78bfa',
    evidence:  '#4ade80',
    users:     '#d97706',
    compliance:'#10b981',
    audit:     GRAY,
  }
  const bg = color[verb] ?? GRAY
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 6px',
      borderRadius: 2,
      fontSize: 10,
      fontWeight: 600,
      background: `${bg}18`,
      color: bg,
      border: `1px solid ${bg}40`,
      fontFamily: 'JetBrains Mono, monospace',
      letterSpacing: '0.02em',
    }}>
      {action}
    </span>
  )
}

export default function AuditLogsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const PAGE_SIZE = 50

  const { data, isLoading, isError } = useAuditLogs({
    page,
    page_size: PAGE_SIZE,
    action: actionFilter || undefined,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const filtered = search
    ? items.filter((l: any) =>
        l.user_email?.toLowerCase().includes(search.toLowerCase()) ||
        l.action?.toLowerCase().includes(search.toLowerCase()) ||
        l.resource_type?.toLowerCase().includes(search.toLowerCase()) ||
        l.ip_address?.includes(search)
      )
    : items

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, gap: 16 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <ClipboardList style={{ width: 18, height: 18, color: ORANGE }} />
            <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 28, color: BLACK, letterSpacing: '0.04em' }}>
              SECURITY HISTORY
            </h2>
          </div>
          <p style={{ fontSize: 12, color: GRAY }}>
            A complete record of who did what, when, and from where
          </p>
        </div>
        <div style={{ fontSize: 11, color: GRAY, fontFamily: 'JetBrains Mono, monospace', marginTop: 8 }}>
          {total.toLocaleString()} total events
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', width: 13, height: 13, color: GRAY }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by user, action, IP…"
            style={{ width: '100%', paddingLeft: 30, paddingRight: 12, paddingTop: 8, paddingBottom: 8, fontSize: 12, background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, color: BLACK, outline: 'none', boxSizing: 'border-box' }}
          />
        </div>
        <select
          value={actionFilter}
          onChange={e => { setActionFilter(e.target.value); setPage(1) }}
          style={{ padding: '8px 12px', fontSize: 12, background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, color: BLACK, outline: 'none' }}
        >
          <option value="">All Actions</option>
          <option value="auth:login">auth:login</option>
          <option value="auth:logout">auth:logout</option>
          <option value="incidents:create">incidents:create</option>
          <option value="incidents:update">incidents:update</option>
          <option value="evidence:upload">evidence:upload</option>
          <option value="users:update">users:update</option>
        </select>
      </div>

      {/* Table */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
        {/* Table header */}
        <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr 120px 120px 90px 70px', gap: 0, borderBottom: `1px solid ${BORDER}`, padding: '8px 16px' }}>
          {['Timestamp', 'Action', 'User', 'Resource', 'IP Address', 'Status'].map(h => (
            <div key={h} style={{ fontSize: 10, fontWeight: 600, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{h}</div>
          ))}
        </div>

        {isLoading && (
          <div style={{ padding: 48, textAlign: 'center', color: GRAY, fontSize: 12 }}>Loading audit logs…</div>
        )}

        {isError && (
          <div style={{ padding: 24, textAlign: 'center' }}>
            <AlertCircle style={{ width: 18, height: 18, color: '#d97706', margin: '0 auto 8px' }} />
            <div style={{ fontSize: 12, color: GRAY }}>Could not load activity logs. Make sure you're signed in as an admin.</div>
          </div>
        )}

        {!isLoading && !isError && filtered.length === 0 && (
          <div style={{ padding: 48, textAlign: 'center', color: GRAY, fontSize: 12 }}>No audit events found</div>
        )}

        {!isLoading && !isError && filtered.map((log: any, i: number) => (
          <div
            key={log.id ?? i}
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr 120px 120px 90px 70px',
              gap: 0,
              padding: '10px 16px',
              borderBottom: `1px solid ${PARCH}`,
              alignItems: 'center',
              background: i % 2 === 0 ? CREAM : '#f4efe8',
            }}
          >
            <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: GRAY }}>
              {log.created_at ? formatDate(log.created_at) : '—'}
            </div>
            <div>
              <ActionBadge action={log.action ?? '—'} />
            </div>
            <div style={{ fontSize: 11, color: BLACK, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={log.user_email}>
              {log.user_email ?? '—'}
            </div>
            <div style={{ fontSize: 11, color: GRAY, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {log.resource_type ? (
                <span>{log.resource_type}{log.resource_id ? <span style={{ opacity: 0.6 }}> #{log.resource_id.slice(0, 8)}</span> : null}</span>
              ) : '—'}
            </div>
            <div style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', color: GRAY }}>
              {log.ip_address ?? '—'}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <StatusDot status={log.response_status} />
              {log.response_status && <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', color: GRAY }}>{log.response_status}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
          <div style={{ fontSize: 11, color: GRAY }}>
            Page {page} of {totalPages} · {total} total events
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', background: page === 1 ? PARCH : CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, fontSize: 11, color: page === 1 ? GRAY : BLACK, cursor: page === 1 ? 'not-allowed' : 'pointer' }}
            >
              <ChevronLeft style={{ width: 12, height: 12 }} /> Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 12px', background: page === totalPages ? PARCH : CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, fontSize: 11, color: page === totalPages ? GRAY : BLACK, cursor: page === totalPages ? 'not-allowed' : 'pointer' }}
            >
              Next <ChevronRight style={{ width: 12, height: 12 }} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
