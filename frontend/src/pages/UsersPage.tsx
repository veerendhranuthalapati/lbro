import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/api/client'
import { useUsers } from '@/hooks/useApi'
import { User } from '@/types'
import { timeAgo } from '@/utils'
import { Users, Shield, RefreshCw, Lock, Unlock, KeyRound, X } from 'lucide-react'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

const ROLE_STYLE: Record<string, { color: string; border: string; bg: string }> = {
  admin:     { color: ORANGE,    border: 'rgba(229,78,27,0.3)',  bg: 'rgba(229,78,27,0.08)'  },
  analyst:   { color: '#3b82f6', border: 'rgba(59,130,246,0.3)', bg: 'rgba(59,130,246,0.08)' },
  responder: { color: '#d97706', border: 'rgba(217,119,6,0.3)',  bg: 'rgba(217,119,6,0.08)'  },
  viewer:    { color: GRAY,      border: BORDER,                  bg: 'rgba(107,101,96,0.08)' },
}

export default function UsersPage() {
  const qc = useQueryClient()
  const [rotatingKey, setRotatingKey] = useState<string | null>(null)
  const [newKey, setNewKey] = useState<{ userId: string; key: string } | null>(null)

  const { data: usersData, isLoading } = useUsers()
  const users = (usersData?.items ?? []) as User[]

  const rotateKeyMutation = useMutation({
    mutationFn: async (userId: string) => {
      const res = await authApi.rotateApiKey()
      return { userId, key: res.api_key }
    },
    onSuccess: (data) => { setNewKey(data); setRotatingKey(null); qc.invalidateQueries({ queryKey: ['users'] }) },
    onError: () => setRotatingKey(null),
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Users style={{ width: 20, height: 20, color: ORANGE }} aria-hidden="true" />
        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
          User Management
        </h1>
      </div>

      {/* New API key banner */}
      {newKey && (
        <div
          role="alert"
          style={{ background: 'rgba(58,122,80,0.08)', border: '1px solid rgba(58,122,80,0.3)', borderRadius: 4, padding: '14px 16px' }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
            <div>
              <p style={{ fontSize: 12, fontWeight: 500, color: '#3a7a50', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <KeyRound style={{ width: 14, height: 14 }} aria-hidden="true" />
                New API key generated -- copy it now, it won't be shown again
              </p>
              <code style={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace', background: PARCH, border: `1px solid ${BORDER}`, padding: '6px 10px', borderRadius: 2, display: 'block', wordBreak: 'break-all', color: BLACK }}>
                {newKey.key}
              </code>
            </div>
            <button
              onClick={() => setNewKey(null)}
              aria-label="Dismiss"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: GRAY, flexShrink: 0 }}
            >
              <X style={{ width: 16, height: 16 }} />
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} style={{ height: 56, background: PARCH }} />
            ))}
          </div>
        ) : !users?.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px 0', color: GRAY }}>
            <Users style={{ width: 36, height: 36, opacity: 0.2, marginBottom: 12 }} aria-hidden="true" />
            <p style={{ fontSize: 12 }}>No users found</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: PARCH }}>
                {['User', 'Role', 'Status', 'Last seen', 'Actions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500, borderBottom: `1px solid ${BORDER}` }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(user => {
                const rs = ROLE_STYLE[user.role] ?? ROLE_STYLE.viewer
                return (
                  <tr
                    key={user.id}
                    style={{ borderBottom: `1px solid ${BORDER}`, transition: 'background 0.1s' }}
                    onMouseEnter={e => (e.currentTarget.style.background = PARCH)}
                    onMouseLeave={e => (e.currentTarget.style.background = '')}
                  >
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>{user.full_name ?? user.email}</div>
                      <div style={{ fontSize: 10, color: GRAY, marginTop: 2 }}>{user.email}</div>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10, padding: '2px 8px', border: `1px solid ${rs.border}`, background: rs.bg, color: rs.color, borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500 }}>
                        <Shield style={{ width: 10, height: 10 }} aria-hidden="true" />
                        {user.role}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      {user.is_active ? (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#3a7a50' }}>
                          <Unlock style={{ width: 11, height: 11 }} aria-hidden="true" /> Active
                        </span>
                      ) : (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: ORANGE }}>
                          <Lock style={{ width: 11, height: 11 }} aria-hidden="true" /> Locked
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px 14px', fontSize: 11, color: GRAY }}>
                      {user.last_login ? timeAgo(user.last_login) : 'Never'}
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <button
                        onClick={() => { setRotatingKey(user.id); rotateKeyMutation.mutate(user.id) }}
                        disabled={rotatingKey === user.id || rotateKeyMutation.isPending}
                        style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', background: 'transparent', border: `1px solid ${BORDER}`, borderRadius: 2, fontSize: 10, color: GRAY, cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em', opacity: (rotatingKey === user.id || rotateKeyMutation.isPending) ? 0.5 : 1 }}
                      >
                        <RefreshCw style={{ width: 11, height: 11, animation: rotatingKey === user.id ? 'spin 1s linear infinite' : 'none' }} aria-hidden="true" />
                        Rotate key
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
