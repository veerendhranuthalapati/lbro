/**
 * ProjectsPage — project selector (GitHub-style).
 *
 * Shows all projects owned by the user, lets them create a new one,
 * and switches the active project when one is clicked.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, FolderOpen, Archive, Globe, Code2, Layers, ChevronRight, Key, Loader2 } from 'lucide-react'
import { projectsApi } from '@/api/client'
import { useProjectStore } from '@/store/projectStore'
import type { Project, ProjectEnvironment } from '@/types'

const ENV_ICONS: Record<ProjectEnvironment, React.ReactNode> = {
  production: <Globe className="w-3.5 h-3.5" />,
  staging: <Layers className="w-3.5 h-3.5" />,
  development: <Code2 className="w-3.5 h-3.5" />,
}

const ENV_COLORS: Record<ProjectEnvironment, string> = {
  production: '#ef4444',
  staging: '#f59e0b',
  development: '#22c55e',
}

function CreateProjectModal({ onClose, onCreated }: { onClose: () => void; onCreated: (p: Project) => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [environment, setEnvironment] = useState<ProjectEnvironment>('production')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => projectsApi.create({ name, description: description || undefined, environment }),
    onSuccess: (project) => onCreated(project),
    onError: (e: any) => setError(e?.response?.data?.detail || 'Failed to create project'),
  })

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(0,0,0,0.7)' }}
      onClick={onClose}
    >
      <div
        className="rounded-lg border p-6 w-full max-w-md"
        style={{ background: '#111', borderColor: '#2a2a2a' }}
        onClick={e => e.stopPropagation()}
      >
        <h2 className="font-display text-xl text-white mb-4">New project</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-xs text-zinc-400 mb-1">Project name</label>
            <input
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="My Portfolio"
              className="w-full px-3 py-2 rounded text-sm text-white border outline-none"
              style={{ background: '#1a1a1a', borderColor: '#333', fontSize: 14 }}
              onKeyDown={e => { if (e.key === 'Enter' && name.trim()) mutation.mutate() }}
            />
          </div>

          <div>
            <label className="block text-xs text-zinc-400 mb-1">Description (optional)</label>
            <input
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="What does this project monitor?"
              className="w-full px-3 py-2 rounded text-sm text-white border outline-none"
              style={{ background: '#1a1a1a', borderColor: '#333', fontSize: 14 }}
            />
          </div>

          <div>
            <label className="block text-xs text-zinc-400 mb-1">Environment</label>
            <div className="flex gap-2">
              {(['development', 'staging', 'production'] as ProjectEnvironment[]).map(env => (
                <button
                  key={env}
                  onClick={() => setEnvironment(env)}
                  className="flex-1 py-1.5 rounded text-xs capitalize transition-all border"
                  style={{
                    background: environment === env ? ENV_COLORS[env] + '22' : '#1a1a1a',
                    borderColor: environment === env ? ENV_COLORS[env] : '#333',
                    color: environment === env ? ENV_COLORS[env] : '#666',
                  }}
                >
                  {env}
                </button>
              ))}
            </div>
          </div>

          {error && <p className="text-xs text-red-400">{error}</p>}

          <div className="flex gap-2 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-2 rounded text-sm text-zinc-400 border"
              style={{ borderColor: '#333' }}
            >
              Cancel
            </button>
            <button
              onClick={() => mutation.mutate()}
              disabled={!name.trim() || mutation.isPending}
              className="flex-1 py-2 rounded text-sm font-medium flex items-center justify-center gap-2 transition-opacity disabled:opacity-40"
              style={{ background: '#e54e1b', color: '#fff' }}
            >
              {mutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Create project
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function ProjectCard({ project, onSelect }: { project: Project; onSelect: () => void }) {
  const envColor = ENV_COLORS[project.environment]
  const isArchived = project.status === 'archived'

  return (
    <button
      onClick={onSelect}
      className="w-full text-left rounded-lg border p-4 transition-all group hover:border-zinc-600"
      style={{
        background: '#0f0f0f',
        borderColor: '#222',
        opacity: isArchived ? 0.5 : 1,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded capitalize"
              style={{ color: envColor, background: envColor + '18' }}
            >
              {ENV_ICONS[project.environment]}
              {project.environment}
            </span>
            {isArchived && (
              <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded text-zinc-500" style={{ background: '#1a1a1a' }}>
                <Archive className="w-3 h-3" /> archived
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-white truncate group-hover:text-[#e54e1b] transition-colors">
            {project.name}
          </p>
          {project.description && (
            <p className="text-xs text-zinc-500 mt-0.5 line-clamp-1">{project.description}</p>
          )}
          <div className="flex items-center gap-1 mt-2 text-xs text-zinc-600">
            <Key className="w-3 h-3" />
            <span className="font-mono">{project.api_key.slice(0, 16)}…</span>
          </div>
        </div>
        <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-zinc-300 mt-1 shrink-0 transition-colors" />
      </div>
    </button>
  )
}

export default function ProjectsPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { setCurrentProject, setProjects } = useProjectStore()
  const [showCreate, setShowCreate] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list(),
    staleTime: 30_000,
  })

  const handleSelect = (project: Project) => {
    setCurrentProject(project)
    navigate('/dashboard')
  }

  const handleCreated = (project: Project) => {
    qc.invalidateQueries({ queryKey: ['projects'] })
    setCurrentProject(project)
    if (data) setProjects([...data.items, project])
    setShowCreate(false)
    // Redirect to setup wizard so new users see their API key immediately
    navigate(`/projects/${project.id}/setup`)
  }

  const projects = data?.items ?? []
  const active = projects.filter(p => p.status === 'active')
  const archived = projects.filter(p => p.status === 'archived')

  return (
    <div className="min-h-screen" style={{ background: '#080808' }}>
      {showCreate && (
        <CreateProjectModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />
      )}

      <div className="max-w-2xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="flex items-end justify-between mb-8">
          <div>
            <h1 className="font-display text-3xl text-white">Projects</h1>
            <p className="text-sm text-zinc-500 mt-1">
              Each project monitors a separate application with isolated incidents and reports.
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-opacity hover:opacity-90"
            style={{ background: '#e54e1b', color: '#fff' }}
          >
            <Plus className="w-4 h-4" />
            New project
          </button>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-20 text-zinc-600">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading projects…
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="text-center py-20 text-red-400 text-sm">
            Failed to load projects. Check your connection and try again.
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && projects.length === 0 && (
          <div className="text-center py-20">
            <FolderOpen className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-zinc-400 text-sm mb-4">No projects yet.</p>
            <button
              onClick={() => setShowCreate(true)}
              className="px-4 py-2 rounded text-sm text-white"
              style={{ background: '#e54e1b' }}
            >
              Create your first project
            </button>
          </div>
        )}

        {/* Active projects */}
        {active.length > 0 && (
          <div className="space-y-2 mb-8">
            {active.map(p => (
              <ProjectCard key={p.id} project={p} onSelect={() => handleSelect(p)} />
            ))}
          </div>
        )}

        {/* Archived */}
        {archived.length > 0 && (
          <div>
            <p className="text-xs text-zinc-600 uppercase tracking-widest mb-3">Archived</p>
            <div className="space-y-2">
              {archived.map(p => (
                <ProjectCard key={p.id} project={p} onSelect={() => handleSelect(p)} />
               ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
