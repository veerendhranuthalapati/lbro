/**
 * ProjectSettingsPage — rename, regenerate key, archive, delete.
 */
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, RefreshCw, Archive, Trash2, Save, Loader2, AlertTriangle, Copy, Check } from 'lucide-react'
import { projectsApi } from '@/api/client'
import { useProjectStore } from '@/store/projectStore'
import type { ProjectEnvironment } from '@/types'

const ENV_OPTIONS: ProjectEnvironment[] = ['development', 'staging', 'production']

export default function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { currentProject, setCurrentProject, clearProject } = useProjectStore()

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

  // Populate fields once project loads
  useState(() => {
    if (project) {
      setName(project.name)
      setDescription(project.description ?? '')
      setEnvironment(project.environment)
    }
  })

  // Sync state when project changes
  if (project && !name) {
    setName(project.name)
    setDescription(project.description ?? '')
    setEnvironment(project.environment)
  }

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

  const copyKey = () => {
    if (project) {
      navigator.clipboard.writeText(project.api_key)
      setKeyCopied(true)
      setTimeout(() => setKeyCopied(false), 2000)
    }
  }

  if (isLoading || !project) {
    return (
      <div className="flex items-center justify-center min-h-screen" style={{ background: '#080808' }}>
        <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
      </div>
    )
  }

  const isArchived = project.status === 'archived'

  return (
    <div className="min-h-screen" style={{ background: '#080808' }}>
      <div className="max-w-2xl mx-auto px-6 py-10">

        {/* Back */}
        <button
          onClick={() => navigate(`/projects/${projectId}`)}
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 mb-6 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to {project.name}
        </button>

        <h1 className="font-display text-2xl text-white mb-8">Project Settings</h1>

        {/* General */}
        <section className="rounded-lg border p-5 mb-4" style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}>
          <h2 className="text-sm font-medium text-white mb-4">General</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Project name</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full px-3 py-2 rounded text-sm text-white border outline-none"
                style={{ background: '#1a1a1a', borderColor: '#333' }}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Description</label>
              <input
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="Optional description"
                className="w-full px-3 py-2 rounded text-sm text-white border outline-none"
                style={{ background: '#1a1a1a', borderColor: '#333' }}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-2">Environment</label>
              <div className="flex gap-2">
                {ENV_OPTIONS.map(env => {
                  const color = env === 'production' ? '#ef4444' : env === 'staging' ? '#f59e0b' : '#22c55e'
                  return (
                    <button
                      key={env}
                      onClick={() => setEnvironment(env)}
                      className="flex-1 py-1.5 rounded text-xs capitalize border transition-all"
                      style={{
                        background: environment === env ? color + '22' : '#1a1a1a',
                        borderColor: environment === env ? color : '#333',
                        color: environment === env ? color : '#666',
                      }}
                    >
                      {env}
                    </button>
                  )
                })}
              </div>
            </div>

            <button
              onClick={() => updateMutation.mutate()}
              disabled={updateMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded text-sm font-medium disabled:opacity-40 transition-opacity"
              style={{ background: '#e54e1b', color: '#fff' }}
            >
              {updateMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              Save changes
            </button>
            {updateMutation.isSuccess && (
              <p className="text-xs text-green-500">Saved.</p>
            )}
          </div>
        </section>

        {/* API Key */}
        <section className="rounded-lg border p-5 mb-4" style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}>
          <h2 className="text-sm font-medium text-white mb-1">API Key</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Send this key in the <code className="text-zinc-400">X-Project-Key</code> header when your app submits incidents to LBRO.
            Regenerating immediately invalidates the old key.
          </p>
          <div className="flex gap-2 mb-3">
            <code
              className="flex-1 px-3 py-2 rounded text-xs text-zinc-300 border font-mono break-all"
              style={{ background: '#1a1a1a', borderColor: '#333' }}
            >
              {project.api_key}
            </code>
            <button
              onClick={copyKey}
              title="Copy"
              className="px-3 py-2 rounded border text-zinc-400 hover:text-white transition-colors shrink-0"
              style={{ borderColor: '#333' }}
            >
              {keyCopied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <button
            onClick={() => regenKeyMutation.mutate()}
            disabled={regenKeyMutation.isPending}
            className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white transition-colors disabled:opacity-40"
          >
            {regenKeyMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Regenerate key
          </button>
        </section>

        {/* Danger zone */}
        <section className="rounded-lg border p-5" style={{ background: '#0f0f0f', borderColor: '#3a1a1a' }}>
          <h2 className="text-sm font-medium text-red-400 mb-4">Danger zone</h2>
          <div className="space-y-4">

            {/* Archive */}
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm text-white">{isArchived ? 'Restore project' : 'Archive project'}</p>
                <p className="text-xs text-zinc-500 mt-0.5">
                  {isArchived
                    ? 'Make this project active again.'
                    : 'Hide from the project list. Data is preserved.'}
                </p>
              </div>
              <button
                onClick={() => archiveMutation.mutate()}
                disabled={archiveMutation.isPending}
                className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded text-xs border text-zinc-400 hover:text-white transition-colors disabled:opacity-40"
                style={{ borderColor: '#444' }}
              >
                {archiveMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Archive className="w-3.5 h-3.5" />}
                {isArchived ? 'Restore' : 'Archive'}
              </button>
            </div>

            {/* Delete */}
            <div className="border-t pt-4" style={{ borderColor: '#2a2a2a' }}>
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <p className="text-sm text-red-400">Delete project</p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Permanently delete this project and all its incidents, evidence, and reports.
                    This cannot be undone.
                  </p>
                </div>
                <button
                  onClick={() => setConfirmDelete(!confirmDelete)}
                  className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded text-xs border text-red-400 hover:text-red-300 transition-colors"
                  style={{ borderColor: '#5a2020' }}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete
                </button>
              </div>

              {confirmDelete && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs text-amber-400">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Type <strong>{project.name}</strong> to confirm
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={deleteText}
                      onChange={e => setDeleteText(e.target.value)}
                      placeholder={project.name}
                      className="flex-1 px-3 py-2 rounded text-sm text-white border outline-none"
                      style={{ background: '#1a1a1a', borderColor: '#5a2020' }}
                    />
                    <button
                      onClick={() => deleteMutation.mutate()}
                      disabled={deleteText !== project.name || deleteMutation.isPending}
                      className="px-4 py-2 rounded text-sm font-medium disabled:opacity-30 flex items-center gap-1.5 transition-opacity"
                      style={{ background: '#ef4444', color: '#fff' }}
                    >
                      {deleteMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                      Confirm delete
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
