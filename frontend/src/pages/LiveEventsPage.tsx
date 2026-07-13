/**
 * LiveEventsPage — real-time SSE event stream for a project.
 *
 * Route: /projects/:projectId/events
 *
 * Connects to GET /api/v1/events/stream (Bearer proj_* auth).
 * Falls back to polling GET /api/v1/events every 5 s if SSE is unavailable.
 * Includes a "Fire demo events" button that calls POST /api/v1/demo/events.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  ArrowLeft, Zap, Activity, Circle, Loader2, Terminal,
  AlertTriangle, Shield, Wifi, WifiOff, Trash2, Pause, Play,
} from 'lucide-react'
import { projectsApi, apiClient } from '@/api/client'
import { getAccessToken } from '@/store/authStore'

const BG     = '#080808'
const CARD   = '#0f0f0f'
const BORDER = '#1e1e1e'
const ORANGE = '#e54e1b'

// ── Severity styles ────────────────────────────────────────────────────────
const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#f59e0b',
  low:      '#22c55e',
  info:     '#3b82f6',
}

const SEV_BG: Record<string, string> = {
  critical: '#ef444418',
  high:     '#f9731618',
  medium:   '#f59e0b18',
  low:      '#22c55e18',
  info:     '#3b82f618',
}

// ── Types ──────────────────────────────────────────────────────────────────
interface LiveEvent {
  id:                string
  project_id:        string
  event_type:        string
  severity:          string
  processing_status: string
  incident_id:       string | null
  ml_attack_category: string | null
  ml_confidence:     number | null
  created_at:        string
  source_ip?:        string
  message?:          string
  _ts:               number   // local receipt timestamp
}

// ── Helpers ────────────────────────────────────────────────────────────────
function timeStr(iso: string) {
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function EventRow({ ev, isNew }: { ev: LiveEvent; isNew: boolean }) {
  const color = SEV_COLOR[ev.severity] ?? '#888'
  const bg    = SEV_BG[ev.severity]   ?? '#88888818'

  return (
    <div
      className="flex items-start gap-3 px-4 py-3 transition-all duration-500 border-b"
      style={{
        borderColor: BORDER,
        background: isNew ? bg : 'transparent',
      }}
    >
      <Circle className="w-2 h-2 mt-1.5 shrink-0 fill-current" style={{ color }} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-mono font-medium" style={{ color }}>
            {ev.severity.toUpperCase()}
          </span>
          <span className="text-xs text-zinc-400">{ev.event_type.replace(/_/g, ' ')}</span>
          {ev.ml_attack_category && (
            <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: color + '22', color }}>
              {ev.ml_attack_category}
            </span>
          )}
          {ev.incident_id && (
            <span className="text-xs px-1.5 py-0.5 rounded text-zinc-400" style={{ background: '#22222260' }}>
              incident created
            </span>
          )}
        </div>
        <p className="text-xs text-zinc-500 mt-0.5 truncate">
          {ev.message ? '[Demo] ' + ev.message.replace('[Demo] ', '') : ev.event_type}
          {ev.ml_confidence ? ` · ${(ev.ml_confidence * 100).toFixed(0)}% confidence` : ''}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-xs text-zinc-600 font-mono">{timeStr(ev.created_at)}</p>
        <p className="text-xs text-zinc-700 font-mono">{ev.id.slice(0, 8)}</p>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────
export default function LiveEventsPage() {
  const { projectId } = useParams<{ projectId: string }>()

  const [events,   setEvents]   = useState<LiveEvent[]>([])
  const [newIds,   setNewIds]   = useState<Set<string>>(new Set())
  const [paused,   setPaused]   = useState(false)
  const [sseState, setSseState] = useState<'connecting'|'connected'|'polling'|'disconnected'>('connecting')
  const [stats,    setStats]    = useState({ total: 0, critical: 0, high: 0 })

  const bufferRef  = useRef<LiveEvent[]>([])
  const esRef      = useRef<EventSource | null>(null)
  const pollRef    = useRef<number | null>(null)
  const pausedRef  = useRef(false)
  const MAX_EVENTS = 200

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn:  () => projectsApi.get(projectId!),
    enabled:  !!projectId,
  })

  // ── Flush buffer into state ──────────────────────────────────────────────
  const flush = useCallback((incoming: LiveEvent[]) => {
    if (!incoming.length) return
    const ids = new Set(incoming.map(e => e.id))
    setNewIds(ids)
    setTimeout(() => setNewIds(new Set()), 2000)
    setEvents(prev => {
      const combined = [...incoming, ...prev]
      return combined.slice(0, MAX_EVENTS)
    })
    setStats(prev => ({
      total:    prev.total + incoming.length,
      critical: prev.critical + incoming.filter(e => e.severity === 'critical').length,
      high:     prev.high    + incoming.filter(e => e.severity === 'high').length,
    }))
  }, [])

  const addEvent = useCallback((ev: LiveEvent) => {
    if (pausedRef.current) {
      bufferRef.current = [ev, ...bufferRef.current].slice(0, 50)
    } else {
      flush([ev])
    }
  }, [flush])

  // ── SSE connection ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!projectId || !project?.api_key) return

    // EventSource doesn't support custom headers — use fetch with ReadableStream
    let cancelled = false
    const apiKey = project.api_key

    async function connectSSE() {
      setSseState('connecting')
      try {
        const resp = await fetch(`/api/v1/events/stream`, {
          headers: { Authorization: 'Bearer ' + apiKey },
        })
        if (!resp.ok || !resp.body) throw new Error('SSE failed: ' + resp.status)
        setSseState('connected')

        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''

        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const payload = JSON.parse(line.slice(6))
                if (payload.type !== 'connected') {
                  addEvent({ ...payload, _ts: Date.now() })
                }
              } catch { /* ignore parse errors */ }
            }
          }
        }
      } catch (err) {
        if (!cancelled) {
          setSseState('polling')
          startPolling()
        }
      }
    }

    // ── Polling fallback ─────────────────────────────────────────────────
    let lastSeenId = ''

    async function startPolling() {
      if (cancelled) return
      try {
        const resp = await apiClient.get(`/api/v1/events`, {
          headers: { Authorization: 'Bearer ' + apiKey },
          params:  { page_size: 20 },
        })
        const items: LiveEvent[] = (resp.data.items ?? []).map((e: any) => ({ ...e, _ts: Date.now() }))
        if (items.length && items[0].id !== lastSeenId) {
          const fresh = lastSeenId ? items.filter(e => e._ts > Date.now() - 10000) : items.slice(0, 5)
          lastSeenId = items[0]?.id ?? ''
          if (!cancelled) flush(fresh)
        }
      } catch { /* ignore */ }
      if (!cancelled) {
        pollRef.current = window.setTimeout(startPolling, 5000)
      }
    }

    connectSSE()

    return () => {
      cancelled = true
      setSseState('disconnected')
      if (pollRef.current) clearTimeout(pollRef.current)
    }
  }, [projectId, project?.api_key, addEvent, flush])

  // ── Pause / resume ───────────────────────────────────────────────────────
  const togglePause = () => {
    const next = !paused
    setPaused(next)
    pausedRef.current = next
    if (!next && bufferRef.current.length) {
      flush(bufferRef.current)
      bufferRef.current = []
    }
  }

  // ── Demo event injection ─────────────────────────────────────────────────
  const demoMutation = useMutation({
    mutationFn: () => apiClient.post('/api/v1/demo/events', {
      project_id: projectId,
      count: 5,
    }).then(r => r.data),
  })

  const statusDot = {
    connecting:  '#f59e0b',
    connected:   '#22c55e',
    polling:     '#3b82f6',
    disconnected:'#ef4444',
  }[sseState]

  const statusLabel = {
    connecting:  'Connecting…',
    connected:   'Live',
    polling:     'Polling (5s)',
    disconnected:'Disconnected',
  }[sseState]

  return (
    <div className="min-h-screen" style={{ background: BG }}>
      <div className="max-w-5xl mx-auto px-6 py-10">

        {/* Header */}
        <div className="mb-8">
          <Link to={`/projects/${projectId}`} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 mb-4 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to project
          </Link>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h1 className="font-display text-3xl text-white">Live Events</h1>
              <p className="text-sm text-zinc-500 mt-1">{project?.name ?? '—'} · real-time security event stream</p>
            </div>

            <div className="flex items-center gap-2">
              {/* SSE status */}
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs" style={{ background: '#0f0f0f', border: '1px solid #1e1e1e' }}>
                <div className="w-2 h-2 rounded-full" style={{ background: statusDot, boxShadow: `0 0 6px ${statusDot}` }} />
                {sseState === 'connected' ? <Wifi className="w-3 h-3 text-green-400" /> : <WifiOff className="w-3 h-3 text-zinc-500" />}
                <span style={{ color: statusDot }}>{statusLabel}</span>
              </div>

              <button
                onClick={togglePause}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-all"
                style={{ background: '#1a1a1a', color: paused ? ORANGE : '#888', border: '1px solid #2a2a2a' }}
              >
                {paused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                {paused ? `Resume (${bufferRef.current.length})` : 'Pause'}
              </button>

              <button
                onClick={() => { setEvents([]); setStats({ total: 0, critical: 0, high: 0 }) }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-all"
                style={{ background: '#1a1a1a', color: '#888', border: '1px solid #2a2a2a' }}
              >
                <Trash2 className="w-3 h-3" /> Clear
              </button>
            </div>
          </div>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: 'Total events', value: stats.total, color: '#888',     icon: <Activity className="w-4 h-4" /> },
            { label: 'Critical',     value: stats.critical, color: '#ef4444', icon: <AlertTriangle className="w-4 h-4" /> },
            { label: 'High',         value: stats.high,     color: '#f97316', icon: <Shield className="w-4 h-4" /> },
          ].map(({ label, value, color, icon }) => (
            <div key={label} className="rounded-xl border p-4" style={{ background: CARD, borderColor: BORDER }}>
              <div className="flex items-center justify-between mb-1">
                <span style={{ color }}>{icon}</span>
                <span className="text-2xl font-display" style={{ color }}>{value}</span>
              </div>
              <p className="text-xs text-zinc-500">{label}</p>
            </div>
          ))}
        </div>

        {/* Demo events banner */}
        <div className="rounded-xl border p-4 mb-6 flex items-center justify-between gap-4" style={{ background: '#0a0f0a', borderColor: '#1e3a1e' }}>
          <div>
            <p className="text-sm font-medium text-white">No traffic yet?</p>
            <p className="text-xs text-zinc-500">Fire 5 simulated attacks to see the stream in action. Incidents will be auto-created.</p>
          </div>
          <button
            onClick={() => demoMutation.mutate()}
            disabled={demoMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:opacity-90 shrink-0"
            style={{ background: '#22c55e', color: '#fff' }}
          >
            {demoMutation.isPending
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Zap className="w-4 h-4" />}
            {demoMutation.isPending ? 'Injecting…' : 'Fire demo attacks'}
          </button>
        </div>

        {/* Event feed */}
        <div className="rounded-xl border overflow-hidden" style={{ background: CARD, borderColor: BORDER }}>
          <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: BORDER, background: '#0f0f0f' }}>
            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-zinc-500" />
              <span className="text-sm font-medium text-white">Event stream</span>
            </div>
            <span className="text-xs text-zinc-600">{events.length} / {MAX_EVENTS} events shown</span>
          </div>

          {events.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center px-6">
              {sseState === 'connecting'
                ? <Loader2 className="w-6 h-6 animate-spin text-zinc-600 mb-4" />
                : <div className="w-10 h-10 rounded-full border-2 border-dashed flex items-center justify-center mb-4" style={{ borderColor: '#2a2a2a' }}>
                    <Activity className="w-5 h-5 text-zinc-700" />
                  </div>}
              <p className="text-sm text-zinc-400 mb-1">
                {sseState === 'connecting' ? 'Connecting to live stream…' : 'Waiting for events'}
              </p>
              <p className="text-xs text-zinc-600">
                {sseState === 'connected'
                  ? 'Send a request to your API or fire demo attacks above'
                  : sseState === 'connecting'
                    ? 'Establishing connection'
                    : 'Stream reconnecting…'}
              </p>
            </div>
          ) : (
            <div className="max-h-[600px] overflow-y-auto">
              {events.map(ev => (
                <EventRow key={ev.id} ev={ev} isNew={newIds.has(ev.id)} />
              ))}
            </div>
          )}
        </div>

        {/* Integration links */}
        <div className="flex gap-4 mt-4 text-xs text-zinc-600">
          <Link to={`/projects/${projectId}/integrations`} className="hover:text-zinc-400 transition-colors">
            Connect your application →
          </Link>
          <Link to="/docs" className="hover:text-zinc-400 transition-colors">
            API documentation →
          </Link>
        </div>
      </div>
    </div>
  )
}
