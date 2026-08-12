/**
 * ProjectSettingsPage — tabbed project settings (General, Members, API Keys, Danger Zone).
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  RefreshCw, Archive, Trash2, Save, Loader2, AlertTriangle, Copy, Check,
} from 'lucide-react'
import { projectsApi } from '@/api/client'
import { getProjectApiKey } from '@/lib/projectApiKeys'
import { useProjectStore } from '@/store/projectStore'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card } from '@/components/ui/Card'
import { LoadingState } from '@/components/ui/LoadingState'
import { ProjectMembersSection } from '@/components/projects/ProjectMembersSection'
import { LBRO } from '@/lib/tokens'
import type { ProjectEnvironment } from '@/types'

const ENV_OPTIONS: ProjectEnvironment[] = ['development', 'staging', 'production']
type Tab = 'general' | 'members' | 'api-keys' | 'danger'

const TABS: { id: Tab; label: string; adminOnly?: boolean }[] = [
  { id: 'general', label: 'General' },
  { id: 'members', label: 'Members' },
  { id: 'api-keys', label: 'API Keys' },
  { id: 'danger', label: 'Danger Zone', adminOnly: true },
]

export default function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { currentProject, setCurrentProject, clearProject } = useProjectStore()
  const [tab, setTab] = useState<Tab>('general')

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
  })

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [environment, setEnvironment] = useState<ProjectEnvironment>('production')
  const [keyCopied, setKeyCopied] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteText, setDeleteText] = useState('')

  useEffect(() => {
    if (project) {
      setName(project.name)
      setDescription(project.description ?? '')
      setEnvironment(project.environment)
      if (currentProject?.id !== project.id) setCurrentProject(project)
    }
  }, [project, currentProject?.id, setCurrentProject])

  const canManage = project?.my_role === 'admin'

  const updateMutation = useMutation({
    mutationFn: () => projectsApi.update(projectId!, {
      name: name.trim() || undefined,
      description: description.trim() || undefined,
      environment,
    }),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      qc.invalidateQueries({ queryKey: ['projects'] })
      if (currentProject?.id === projectId) setCurrentProject(updated)
    },
  })

  const archiveMutation = useMutation({
    mutationFn: () => projectsApi.update(projectId!, {
      status: project?.status === 'archived' ? 'active' : 'archived',
    }),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      qc.invalidateQueries({ queryKey: ['projects'] })
      if (currentProject?.id === projectId) setCurrentProject(updated)
    },
  })

  const regenKeyMutation = useMutation({
    mutationFn: () => projectsApi.regenerateKey(projectId!),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ['project', projectId] })
      if (currentProject?.id === projectId) setCurrentProject(updated)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => projectsApi.delete(projectId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] })
      if (currentProject?.id === projectId) clearProject()
      navigate('/projects')
    },
  })

  if (isLoading || !project) {
    return <LoadingState label="Loading project settings…" />
  }

  const sessionKey = projectId ? getProjectApiKey(projectId) : null
  const displayKey = sessionKey ?? `${project.api_key_prefix}…`
  const isArchived = project.status === 'archived'
  const visibleTabs = TABS.filter(t => !t.adminOnly || canManage)

  const copyKey = () => {
    if (sessionKey) {
      navigator.clipboard.writeText(sessionKey)
      setKeyCopied(true)
      setTimeout(() => setKeyCopied(false), 2000)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <PageHeader
        compact
        title="Project Settings"
        description="Manage this project's name, members, API keys, and lifecycle."
      />

      <div
        className="flex flex-wrap gap-1 mb-6 p-1 rounded-lg border"
        style={{ background: LBRO.cream, borderColor: LBRO.border }}
        role="tablist"
      >
        {visibleTabs.map(t => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
            style={
              tab === t.id
                ? { background: LBRO.orange, color: '#fff' }
                : { color: LBRO.gray }
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'general' && (
        <Card title="General" description="Project name, description, and environment.">
          <div className="space-y-4">
            <div>
              <label className="block text-xs mb-1" style={{ color: LBRO.gray }}>Project name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                disabled={!canManage}
                className="w-full px-3 py-2 rounded text-sm border outline-none"
                style={{ borderColor: LBRO.border, color: LBRO.black }}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: LBRO.gray }}>Description</label>
              <input
                value={description}
                onChange={e => setDescription(e.target.value)}
                disabled={!canManage}
                className="w-full px-3 py-2 rounded text-sm border outline-none"
                style={{ borderColor: LBRO.border, color: LBRO.black }}
              />
            </div>
            <div>
              <label className="block text-xs mb-2" style={{ color: LBRO.gray }}>Environment</label>
              <div className="flex gap-2">
                {ENV_OPTIONS.map(env => (
                  <button
                    key={env}
                    type="button"
                    disabled={!canManage}
                    onClick={() => setEnvironment(env)}
                    className="flex-1 py-1.5 rounded text-xs capitalize border"
                    style={{
                      borderColor: environment === env ? LBRO.orange : LBRO.border,
                      background: environment === env ? `${LBRO.orange}15` : '#fff',
                      color: environment === env ? LBRO.orange : LBRO.gray,
                    }}
                  >
                    {env}
                  </button>
                ))}
              </div>
            </div>
            {canManage && (
              <button
                type="button"
                onClick={() => updateMutation.mutate()}
                disabled={updateMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 rounded text-sm font-medium text-white disabled:opacity-40"
                style={{ background: LBRO.orange }}
              >
                {updateMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save changes
              </button>
            )}
          </div>
        </Card>
      )}

      {tab === 'members' && (
        <ProjectMembersSection projectId={projectId!} canManage={canManage} />
      )}

      {tab === 'api-keys' && (
        <Card
          title="Project API key"
          description="Use this key in the X-Project-Key header or Authorization Bearer for event ingestion."
        >
          <div className="flex gap-2 mb-3">
            <code
              className="flex-1 px-3 py-2 rounded text-xs font-mono break-all border"
              style={{ borderColor: LBRO.border, color: LBRO.black, background: LBRO.offwhite }}
            >
              {displayKey}
            </code>
            <button
              type="button"
              onClick={copyKey}
              disabled={!sessionKey}
              className="px-3 py-2 rounded border disabled:opacity-40"
              style={{ borderColor: LBRO.border }}
              aria-label="Copy API key"
            >
              {keyCopied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          {canManage && (
            <button
              type="button"
              onClick={() => regenKeyMutation.mutate()}
              disabled={regenKeyMutation.isPending}
              className="inline-flex items-center gap-2 text-sm"
              style={{ color: LBRO.gray }}
            >
              {regenKeyMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Regenerate key
            </button>
          )}
          {!canManage && (
            <p className="text-xs" style={{ color: LBRO.gray }}>Only project admins can regenerate keys.</p>
          )}
        </Card>
      )}

      {tab === 'danger' && canManage && (
        <Card title="Danger zone" description="Archive or permanently delete this project." danger>
          <div className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium" style={{ color: LBRO.black }}>
                  {isArchived ? 'Restore project' : 'Archive project'}
                </p>
                <p className="text-xs mt-0.5" style={{ color: LBRO.gray }}>
                  {isArchived ? 'Make this project active again.' : 'Hide from lists. Data is preserved.'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => archiveMutation.mutate()}
                disabled={archiveMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs border"
                style={{ borderColor: LBRO.border }}
              >
                <Archive className="w-3.5 h-3.5" />
                {isArchived ? 'Restore' : 'Archive'}
              </button>
            </div>

            <div className="border-t pt-4" style={{ borderColor: LBRO.border }}>
              <p className="text-sm font-medium mb-1" style={{ color: LBRO.danger }}>Delete project</p>
              <p className="text-xs mb-3" style={{ color: LBRO.gray }}>
                Permanently delete all incidents, evidence, and reports. Cannot be undone.
              </p>
              {!confirmDelete ? (
                <button
                  type="button"
                  onClick={() => setConfirmDelete(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs border"
                  style={{ borderColor: '#fca5a5', color: LBRO.danger }}
                >
                  <Trash2 className="w-3.5 h-3.5" /> Delete project
                </button>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs text-amber-700">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Type <strong>{project.name}</strong> to confirm
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={deleteText}
                      onChange={e => setDeleteText(e.target.value)}
                      className="flex-1 px-3 py-2 rounded text-sm border"
                      style={{ borderColor: LBRO.border }}
                    />
                    <button
                      type="button"
                      onClick={() => deleteMutation.mutate()}
                      disabled={deleteText !== project.name || deleteMutation.isPending}
                      className="px-4 py-2 rounded text-sm font-medium text-white disabled:opacity-30"
                      style={{ background: LBRO.danger }}
                    >
                      Confirm delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
