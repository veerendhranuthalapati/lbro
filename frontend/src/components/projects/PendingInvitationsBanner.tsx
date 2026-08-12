/**
 * Shows pending project invitations for the logged-in user.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Mail, Loader2 } from 'lucide-react'
import { invitationsApi, projectsApi } from '@/api/client'
import { useSwitchProject } from '@/hooks/useSwitchProject'

export function PendingInvitationsBanner() {
  const qc = useQueryClient()
  const switchProject = useSwitchProject()

  const { data, isLoading } = useQuery({
    queryKey: ['invitations', 'pending'],
    queryFn: () => invitationsApi.listPending(),
    staleTime: 30_000,
  })

  const acceptMutation = useMutation({
    mutationFn: (invitationId: string) => invitationsApi.accept(invitationId),
    onSuccess: async () => {
      qc.invalidateQueries({ queryKey: ['invitations'] })
      qc.invalidateQueries({ queryKey: ['projects'] })
      const projects = await projectsApi.list()
      qc.setQueryData(['projects'], projects)
    },
  })

  const declineMutation = useMutation({
    mutationFn: (invitationId: string) => invitationsApi.decline(invitationId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invitations'] }),
  })

  if (isLoading || !data?.items.length) return null

  return (
    <div
      className="mx-6 mt-4 mb-0 rounded-lg border px-4 py-3"
      style={{ background: '#1a1208', borderColor: '#e54e1b44' }}
    >
      <div className="flex items-center gap-2 text-sm text-amber-200 mb-2">
        <Mail className="w-4 h-4" />
        You have pending project invitations
      </div>
      <ul className="space-y-2">
        {data.items.map(inv => (
          <li key={inv.id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="text-zinc-300">
              <strong className="text-white">{inv.project_name ?? 'Project'}</strong>
              {' '}as {inv.role} · {inv.invited_email}
            </span>
            <span className="flex gap-2">
              <button
                onClick={async () => {
                  await acceptMutation.mutateAsync(inv.id)
                  const project = await projectsApi.get(inv.project_id)
                  switchProject(project)
                }}
                disabled={acceptMutation.isPending}
                className="px-3 py-1 rounded text-white disabled:opacity-40"
                style={{ background: '#e54e1b' }}
              >
                {acceptMutation.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Accept'}
              </button>
              <button
                onClick={() => declineMutation.mutate(inv.id)}
                disabled={declineMutation.isPending}
                className="px-3 py-1 rounded border text-zinc-400 hover:text-white"
                style={{ borderColor: '#444' }}
              >
                Decline
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
