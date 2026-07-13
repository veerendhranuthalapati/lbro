/**
 * ProjectOverviewPage — per-project stats dashboard.
 *
 * Shows security score, open incidents, evidence, compliance, API key,
 * last activity, most common attack, most targeted port, and recommendations.
 */
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ShieldCheck, ShieldAlert, Lock, FileText, Clock,
  AlertTriangle, Target, Key, Settings, ArrowLeft,
  Globe, Layers, Code2, Loader2, Zap, Activity, Terminal,
} from 'lucide-react'
import { projectsApi } from '@/api/client'
import { useProjectStore } from '@/store/projectStore'
import type { ProjectEnvironment } from '@/types'

const ENV_COLORS: Record<ProjectEnvironment, string> = {
  production: '#ef4444',
  staging: '#f59e0b',
  development: '#22c55e',
}

const GRADE_COLORS: Record<string, string> = {
  A: '#22c55e', B: '#84cc16', C: '#f59e0b', D: '#f97316', F: '#ef4444',
}

function StatCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border p-4" style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}>
      <div className="flex items-start justify-between mb-3">
        <span className="text-zinc-500">{icon}</span>
      </div>
      <p className="text-2xl font-display text-white">{value}</p>
      <p className="text-xs text-zinc-500 mt-1">{label}</p>
      {sub && <p className="text-xs text-zinc-600 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function ProjectOverviewPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { setCurrentProject } = useProjectStore()

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
  })

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['project-dashboard', projectId],
    queryFn: () => projectsApi.dashboard(projectId!),
    enabled: !!projectId,
    refetchInterval: 60_000,
  })

  const handleUseProject = () => {
    if (project) {
      setCurrentProject(project)
      navigate('/dashboard')
    }
  }

  if (isLoading || !dashboard) {
    return (
      <div className="flex items-center justify-center min-h-screen" style={{ background: '#080808' }}>
        <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
      </div>
    )
  }

  const envColor = ENV_COLORS[dashboard.environment as ProjectEnvironment] ?? '#666'
  const gradeColor = GRADE_COLORS[dashboard.security_grade] ?? '#666'
  const lastActivity = dashboard.last_activity
    ? new Date(dashboard.last_activity).toLocaleDateString()
    : 'Never'

  return (
    <div className="min-h-screen" style={{ background: '#080808' }}>
      <div className="max-w-4xl mx-auto px-6 py-10">

        {/* Back + header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/projects')}
            className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 mb-4 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> All projects
          </button>

          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="text-xs px-2 py-0.5 rounded capitalize"
                  style={{ color: envColor, background: envColor + '18' }}
                >
                  {dashboard.environment}
                </span>
                {dashboard.status === 'archived' && (
                  <span className="text-xs px-2 py-0.5 rounded text-zinc-500" style={{ background: '#1a1a1a' }}>
                    archived
                  </span>
                )}
              </div>
              <h1 className="font-display text-3xl text-white">{dashboard.project_name}</h1>
              <p className="text-xs text-zinc-600 mt-1 font-mono">
                Created {project ? new Date(project.created_at).toLocaleDateString() : '—'}
              </p>
            </div>

            <div className="flex gap-2 shrink-0">
              <button
                onClick={handleUseProject}
                className="px-3 py-1.5 rounded text-sm font-medium flex items-center gap-1.5 transition-opacity hover:opacity-90"
                style={{ background: '#e54e1b', color: '#fff' }}
              >
                <Zap className="w-3.5 h-3.5" /> Use this project
              </button>
              <Link
                to={`/projects/${projectId}/events`}
                className="px-3 py-1.5 rounded text-sm border flex items-center gap-1.5 text-zinc-400 hover:text-white transition-colors"
                style={{ borderColor: '#333' }}
              >
                <Activity className="w-3.5 h-3.5" /> Live events
              </Link>
              <Link
                to={`/projects/${projectId}/integrations`}
                className="px-3 py-1.5 rounded text-sm border flex items-center gap-1.5 text-zinc-400 hover:text-white transition-colors"
                style={{ borderColor: '#333' }}
              >
                <Terminal className="w-3.5 h-3.5" /> Integrations
              </Link>
              <Link
                to={`/projects/${projectId}/settings`}
                className="px-3 py-1.5 rounded text-sm border flex items-center gap-1.5 text-zinc-400 hover:text-white transition-colors"
                style={{ borderColor: '#333' }}
              >
                <Settings className="w-3.5 h-3.5" /> Settings
              </Link>
            </div>
          </div>
        </div>

        {/* Security score hero */}
        <div
          className="rounded-lg border p-6 mb-6 flex items-center gap-6"
          style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}
        >
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center font-display text-4xl shrink-0"
            style={{ border: `3px solid ${gradeColor}`, color: gradeColor }}
          >
            {dashboard.security_grade}
          </div>
          <div className="flex-1">
            <p className="text-xs text-zinc-500 mb-1">Security Score</p>
            <p className="text-4xl font-display text-white">{dashboard.security_score}<span className="text-xl text-zinc-600">/100</span></p>
            <p className="text-xs text-zinc-500 mt-1">Last updated {new Date().toLocaleDateString()}</p>
          </div>
          {dashboard.top_recommendations.length > 0 && (
            <div className="hidden md:block max-w-xs">
              <p className="text-xs text-zinc-500 mb-2">Top priority</p>
              <p className="text-sm text-white leading-snug">
                {dashboard.top_recommendations[0].title}
              </p>
            </div>
          )}
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard
            icon={<ShieldAlert className="w-4 h-4" />}
            label="Open incidents"
            value={dashboard.open_incidents}
          />
          <StatCard
            icon={<AlertTriangle className="w-4 h-4" />}
            label="Critical incidents"
            value={dashboard.critical_incidents}
          />
          <StatCard
            icon={<Lock className="w-4 h-4" />}
            label="Evidence files"
            value={dashboard.evidence_count}
          />
          <StatCard
            icon={<FileText className="w-4 h-4" />}
            label="Overdue compliance"
            value={dashboard.overdue_compliance}
          />
        </div>

        {/* Details row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
          <div className="rounded-lg border p-4" style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}>
            <p className="text-xs text-zinc-500 mb-2 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" /> Last activity
            </p>
            <p className="text-sm text-white">{lastActivity}</p>
          </div>

          <div className="rounded-lg border p-4" style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}>
            <p className="text-xs text-zinc-500 mb-2 flex items-center gap-1.5">
              <Target className="w-3.5 h-3.5" /> Most common attack
            </p>
            <p className="text-sm text-white">{dashboard.most_common_attack ?? '—'}</p>
          </div>

          <div className="rounded-lg border p-4" style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}>
            <p className="text-xs text-zinc-500 mb-2 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5" /> Most targeted port
            </p>
            <p className="text-sm text-white">{dashboard.most_targeted_port ?? '—'}</p>
          </div>
        </div>

        {/* API Key */}
        <div className="rounded-lg border p-4 mb-6" style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}>
          <p className="text-xs text-zinc-500 mb-2 flex items-center gap-1.5">
            <Key className="w-3.5 h-3.5" /> Project API key
            <span className="text-zinc-700">— send this in <code className="text-zinc-500">X-Project-Key</code> header when submitting incidents</span>
          </p>
          <p className="font-mono text-sm text-zinc-300 break-all">{dashboard.api_key}</p>
        </div>

        {/* Recommendations */}
        {dashboard.top_recommendations.length > 0 && (
          <div className="rounded-lg border p-4" style={{ background: '#0f0f0f', borderColor: '#1e1e1e' }}>
            <p className="text-xs text-zinc-500 mb-3">Recommendations</p>
            <div className="space-y-2">
              {dashboard.top_recommendations.map((rec, i) => (
       
                <div key={i} className="flex items-start gap-2">
                  <span
                    className="text-xs px-1.5 py-0.5 rounded mt-0.5 shrink-0 capitalize"
                    style={{
                      color: rec.priority === 'critical' ? '#ef4444' : rec.priority === 'medium' ? '#f59e0b' : '#22c55e',
                      background: (rec.priority === 'critical' ? '#ef4444' : rec.priority === 'medium' ? '#f59e0b' : '#22c55e') + '18',
                    }}
                  >
                    {rec.priority}
                  </span>
                  <p className="text-sm text-zinc-300">{rec.title}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
