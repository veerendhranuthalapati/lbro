import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { notificationsApi } from '@/api/client'
import { useNotifications } from '@/hooks/useApi'
import { type RegulatoryNotification as Notification } from '@/types'
import { timeAgo } from '@/utils'
import { Bell, CheckCircle, Clock, Send, AlertTriangle } from 'lucide-react'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

const REG_ACCENT: Record<string, string> = {
  GDPR:  '#3b82f6',
  HIPAA: '#a78bfa',
  DPDPA: ORANGE,
}

const STATUS_STYLE: Record<string, { color: string; border: string; bg: string }> = {
  pending:  { color: '#d97706', border: 'rgba(217,119,6,0.3)',  bg: 'rgba(217,119,6,0.08)'  },
  approved: { color: '#3b82f6', border: 'rgba(59,130,246,0.3)', bg: 'rgba(59,130,246,0.08)' },
  sent:     { color: '#3a7a50', border: 'rgba(58,122,80,0.3)',  bg: 'rgba(58,122,80,0.08)'  },
  failed:   { color: ORANGE,    border: 'rgba(229,78,27,0.3)',  bg: 'rgba(229,78,27,0.08)'  },
}

export default function NotificationsPage() {
  const qc = useQueryClient()
  const [filter, setFilter] = useState<string>('all')

  const { data, isLoading } = useNotifications({ status: filter === 'all' ? undefined : filter })

  const approveMutation  = useMutation({ mutationFn: (id: string) => notificationsApi.approve(id),  onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }) })
  const dispatchMutation = useMutation({ mutationFn: (id: string) => notificationsApi.dispatch(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }) })

  const notifications: Notification[] = data?.items ?? []
  const counts = {
    all:     notifications.length,
    pending: notifications.filter(n => n.status === 'pending').length,
    overdue: notifications.filter(n => n.deadline && new Date(n.deadline) < new Date() && n.status !== 'sent').length,
    sent:    notifications.filter(n => n.status === 'sent').length,
  }

  const btnStyle = (active: boolean) => ({
    padding: '5px 14px',
    fontSize: 10,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
    fontWeight: 500,
    border: `1px solid ${active ? ORANGE : BORDER}`,
    borderRadius: 2,
    background: active ? 'rgba(229,78,27,0.08)' : 'transparent',
    color: active ? ORANGE : GRAY,
    cursor: 'pointer',
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Bell style={{ width: 20, height: 20, color: ORANGE }} aria-hidden="true" />
          <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
            Compliance Alerts
          </h1>
        </div>
        {counts.overdue > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, border: `1px solid rgba(229,78,27,0.35)`, background: 'rgba(229,78,27,0.08)', borderRadius: 4, padding: '6px 12px' }}>
            <AlertTriangle style={{ width: 14, height: 14, color: ORANGE }} aria-hidden="true" />
            <span style={{ fontSize: 11, color: ORANGE, fontWeight: 500 }}>{counts.overdue} overdue</span>
          </div>
        )}
      </div>

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 6 }}>
        {(['all', 'pending', 'overdue', 'sent'] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)} style={btnStyle(filter === f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)}
            {counts[f] > 0 && (
              <span style={{ marginLeft: 5, fontSize: 9, opacity: 0.7 }}>{counts[f]}</span>
            )}
          </button>
        ))}
      </div>

      {/* List */}
      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} style={{ height: 80, background: PARCH, borderRadius: 4, animation: 'pulse 1.5s infinite' }} />
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px 0', color: GRAY }}>
          <Bell style={{ width: 36, height: 36, opacity: 0.2, marginBottom: 12 }} aria-hidden="true" />
          <p style={{ fontSize: 12 }}>No notifications match this filter</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {notifications.map(n => {
            const st = STATUS_STYLE[n.status] ?? STATUS_STYLE.pending
            const regAccent = REG_ACCENT[n.regulation] ?? GRAY
            const isOverdue = n.deadline && new Date(n.deadline) < new Date() && n.status !== 'sent'
            return (
              <div
                key={n.id}
                style={{
                  background: CREAM,
                  border: `1px solid ${isOverdue ? 'rgba(229,78,27,0.35)' : BORDER}`,
                  borderLeft: `3px solid ${regAccent}`,
                  borderRadius: 4,
                  padding: '14px 16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 18, color: regAccent, letterSpacing: '0.04em' }}>
                        {n.regulation}
                      </span>
                      <span style={{ fontSize: 11, color: GRAY }}>·</span>
                      <span style={{ fontSize: 11, color: GRAY }}>{n.jurisdiction}</span>
                      <span
                        style={{ marginLeft: 'auto', fontSize: 10, padding: '2px 8px', border: `1px solid ${st.border}`, background: st.bg, color: st.color, borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500 }}
                      >
                        {n.status}
                      </span>
                    </div>

                    <p style={{ fontSize: 12, color: BLACK, marginBottom: 8, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any }}>
                      {n.subject}
                    </p>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 10, color: GRAY }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Clock style={{ width: 11, height: 11 }} aria-hidden="true" />
                        Due: {n.deadline ? new Date(n.deadline).toLocaleDateString() : 'N/A'}
                      </span>
                      {n.authority && <span>Authority: {n.authority}</span>}
                      <span>Created {timeAgo(n.created_at)}</span>
                      {n.retry_count > 0 && <span style={{ color: '#d97706' }}>Retry #{n.retry_count}</span>}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                    {n.status === 'pending' && (
                      <button
                        onClick={() => approveMutation.mutate(n.id)}
                        disabled={approveMutation.isPending}
                        style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', borderRadius: 2, fontSize: 10, fontWeight: 500, color: '#3b82f6', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em', opacity: approveMutation.isPending ? 0.5 : 1 }}
                      >
                        <CheckCircle style={{ width: 12, height: 12 }} aria-hidden="true" />
                        Approve
                      </button>
                    )}
                    {(n.status === 'approved' || n.status === 'pending') && (
                      <button
                        onClick={() => dispatchMutation.mutate(n.id)}
                        disabled={dispatchMutation.isPending}
                        style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', background: 'rgba(229,78,27,0.1)', border: `1px solid rgba(229,78,27,0.35)`, borderRadius: 2, fontSize: 10, fontWeight: 500, color: ORANGE, cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em', opacity: dispatchMutation.isPending ? 0.5 : 1 }}
                      >
                        <Send style={{ width: 12, height: 12 }} aria-hidden="true" />
                        Dispatch
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
