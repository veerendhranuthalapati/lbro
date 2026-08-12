/**
 * Project members + invitation management (admin only).
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Loader2, Mail, Trash2, UserPlus, Check } from 'lucide-react'
import { projectsApi } from '@/api/client'
import type { ProjectMemberRole } from '@/types'
import { LBRO } from '@/lib/tokens'

const ROLES: ProjectMemberRole[] = ['admin', 'analyst', 'viewer']

interface Props {
  projectId: string
  canManage: boolean
}

export function ProjectMembersSection({ projectId, canManage }: Props) {
  const qc = useQueryClient()
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<ProjectMemberRole>('analyst')
  const [inviteError, setInviteError] = useState('')
  const [lastToken, setLastToken] = useState<string | null>(null)
  const [tokenCopied, setTokenCopied] = useState(false)

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ['project-members', projectId],
    queryFn: () => projectsApi.listMembers(projectId),
    enabled: !!projectId,
  })

  const { data: invitations } = useQuery({
    queryKey: ['project-invitations', projectId],
    queryFn: () => projectsApi.listInvitations(projectId),
    enabled: !!projectId && canManage,
  })

  const inviteMutation = useMutation({
    mutationFn: () => projectsApi.createInvitation(projectId, inviteEmail.trim(), inviteRole),
    onSuccess: (inv) => {
      setInviteError('')
      setInviteEmail('')
      setLastToken(inv.invite_token)
      qc.invalidateQueries({ queryKey: ['project-invitations', projectId] })
    },
    onError: (e: { response?: { data?: { detail?: string | { message?: string } } } }) => {
      const d = e?.response?.data?.detail
      setInviteError(typeof d === 'string' ? d : d?.message ?? 'Failed to send invitation')
    },
  })

  const updateRoleMutation = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: ProjectMemberRole }) =>
      projectsApi.updateMember(projectId, memberId, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project-members', projectId] }),
  })

  const removeMutation = useMutation({
    mutationFn: (memberId: string) => projectsApi.removeMember(projectId, memberId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project-members', projectId] }),
  })

  const cancelInviteMutation = useMutation({
    mutationFn: (invitationId: string) => projectsApi.cancelInvitation(projectId, invitationId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['project-invitations', projectId] }),
  })

  const copyToken = () => {
    if (lastToken) {
      navigator.clipboard.writeText(lastToken)
      setTokenCopied(true)
      setTimeout(() => setTokenCopied(false), 2000)
    }
  }

  return (
    <section className="rounded-lg border p-5 mb-4" style={{ background: LBRO.card, borderColor: LBRO.border }}>
      <h2 className="text-sm font-medium mb-1" style={{ color: LBRO.black }}>Members</h2>
      <p className="text-xs mb-4" style={{ color: LBRO.gray }}>
        People with access to this project. Email delivery is not configured — share the invite link manually.
      </p>

      {membersLoading ? (
        <Loader2 className="w-4 h-4 animate-spin text-zinc-500" />
      ) : (
        <div className="overflow-x-auto mb-4">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-zinc-500 border-b" style={{ borderColor: '#2a2a2a' }}>
                <th className="text-left py-2 pr-3 font-medium">User</th>
                <th className="text-left py-2 pr-3 font-medium">Role</th>
                <th className="text-left py-2 font-medium">Status</th>
                {canManage && <th className="py-2 w-20" />}
              </tr>
            </thead>
            <tbody>
              {(members?.items ?? []).map(m => (
                <tr key={m.id} className="border-b" style={{ borderColor: '#1a1a1a' }}>
                  <td className="py-2.5 pr-3">
                    <div className="text-white">{m.full_name ?? m.email}</div>
                    <div className="text-zinc-500">{m.email}</div>
                  </td>
                  <td className="py-2.5 pr-3">
                    {canManage && !m.is_owner ? (
                      <select
                        value={m.role}
                        onChange={e => updateRoleMutation.mutate({
                          memberId: m.id,
                          role: e.target.value as ProjectMemberRole,
                        })}
                        className="px-2 py-1 rounded border text-zinc-300 capitalize"
                        style={{ background: '#1a1a1a', borderColor: '#333' }}
                      >
                        {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                    ) : (
                      <span className="capitalize text-zinc-300">{m.is_owner ? 'owner' : m.role}</span>
                    )}
                  </td>
                  <td className="py-2.5 text-green-500">Active</td>
                  {canManage && (
                    <td className="py-2.5 text-right">
                      {!m.is_owner && (
                        <button
                          onClick={() => removeMutation.mutate(m.id)}
                          disabled={removeMutation.isPending}
                          className="p-1 text-zinc-500 hover:text-red-400"
                          title="Remove member"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {canManage && (
        <>
          <div className="border-t pt-4 mb-4" style={{ borderColor: '#2a2a2a' }}>
            <p className="text-xs text-zinc-400 mb-2 flex items-center gap-1">
              <UserPlus className="w-3.5 h-3.5" /> Invite by email
            </p>
            <div className="flex flex-wrap gap-2">
              <input
                type="email"
                value={inviteEmail}
                onChange={e => setInviteEmail(e.target.value)}
                placeholder="friend@example.com"
                className="flex-1 min-w-[180px] px-3 py-2 rounded text-sm text-white border outline-none"
                style={{ background: '#1a1a1a', borderColor: '#333' }}
              />
              <select
                value={inviteRole}
                onChange={e => setInviteRole(e.target.value as ProjectMemberRole)}
                className="px-3 py-2 rounded text-sm border capitalize text-zinc-300"
                style={{ background: '#1a1a1a', borderColor: '#333' }}
              >
                {ROLES.filter(r => r !== 'admin').map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
                <option value="admin">admin</option>
              </select>
              <button
                onClick={() => inviteMutation.mutate()}
                disabled={!inviteEmail.trim() || inviteMutation.isPending}
                className="px-4 py-2 rounded text-sm font-medium disabled:opacity-40"
                style={{ background: '#e54e1b', color: '#fff' }}
              >
                {inviteMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send invitation'}
              </button>
            </div>
            {inviteError && <p className="text-xs text-red-400 mt-2">{inviteError}</p>}
            {lastToken && (
              <div className="mt-3 p-3 rounded border" style={{ background: '#1a1a1a', borderColor: '#333' }}>
                <p className="text-xs text-amber-400 mb-1 flex items-center gap-1">
                  <Mail className="w-3.5 h-3.5" /> Share this invite token (shown once):
                </p>
                <div className="flex gap-2">
                  <code className="flex-1 text-xs text-zinc-300 break-all font-mono">{lastToken}</code>
                  <button onClick={copyToken} className="text-zinc-400 hover:text-white shrink-0">
                    {tokenCopied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            )}
          </div>

          {(invitations?.items.length ?? 0) > 0 && (
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-widest mb-2">Pending invitations</p>
              <ul className="space-y-2">
                {invitations!.items.map(inv => (
                  <li
                    key={inv.id}
                    className="flex items-center justify-between gap-2 text-xs py-2 px-3 rounded border"
                    style={{ background: '#141414', borderColor: '#2a2a2a' }}
                  >
                    <span className="text-zinc-300">{inv.invited_email} · {inv.role}</span>
                    <button
                      onClick={() => cancelInviteMutation.mutate(inv.id)}
                      className="text-zinc-500 hover:text-red-400"
                    >
                      Cancel
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}
