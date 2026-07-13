/**
 * ApiDocsPage — public-facing API reference.
 *
 * Route: /docs
 * Shows every public endpoint with auth, request, response, errors.
 */
import { useState } from 'react'
import {
  ChevronRight, Copy, Check, Globe, Lock, Zap,
  ArrowUpRight, Terminal, Code2, Activity,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const BG     = '#080808'
const CARD   = '#0f0f0f'
const BORDER = '#1e1e1e'
const ORANGE = '#e54e1b'

const METHOD_COLOR: Record<string, string> = {
  GET:    '#3b82f6',
  POST:   '#22c55e',
  PATCH:  '#f59e0b',
  DELETE: '#ef4444',
}

// ── Data ──────────────────────────────────────────────────────────────────
const ENDPOINTS = [
  {
    id:      'ingest-event',
    method:  'POST',
    path:    '/api/v1/events',
    summary: 'Ingest a single security event',
    auth:    'Bearer proj_<api_key>',
    desc:    'Submit one security event. The project is resolved from the API key — never from the request body. The server runs ML classification, auto-creates incidents for critical/high severity, and marks the event as processed.',
    request: `{
  "event_type":   "sql_injection",       // required — see Event Types below
  "severity":     "critical",            // required — critical|high|medium|low|info
  "source_ip":    "185.220.101.42",      // optional
  "source_host":  "web-01.example.com",  // optional
  "source_application": "myapp",         // optional
  "message":      "SQLi probe on /api/users",  // optional
  "event_timestamp": "2024-01-15T10:30:00Z",   // optional, UTC ISO8601
  "payload": {                           // optional — any JSON
    "destination_port": 443,
    "flow_packets_per_sec": 1200
  }
}`,
    response: `HTTP 202 Accepted
{
  "id":                 "evt_01j...",
  "project_id":         "prj_01j...",
  "event_type":         "sql_injection",
  "severity":           "critical",
  "processing_status":  "processed",
  "incident_id":        "inc_01j...",   // null if not auto-created
  "ml_attack_category": "Web Attack - Sql Injection",
  "ml_confidence":      0.94,
  "created_at":         "2024-01-15T10:30:00.123Z"
}`,
    errors: [
      { code: '401', msg: 'Missing or invalid API key' },
      { code: '422', msg: 'Unknown event_type or severity value' },
      { code: '429', msg: 'Rate limit exceeded (60 req/min per key)' },
    ],
  },
  {
    id:      'ingest-batch',
    method:  'POST',
    path:    '/api/v1/events/batch',
    summary: 'Ingest up to 1,000 events',
    auth:    'Bearer proj_<api_key>',
    desc:    'Submit a batch of events in a single request. Partial success is supported — invalid events are skipped and reported in the errors array. Ideal for log shipping and bulk uploads.',
    request: `{
  "events": [
    { "event_type": "auth_failure", "severity": "medium", "source_ip": "1.2.3.4" },
    { "event_type": "port_scan",    "severity": "low",    "source_ip": "5.6.7.8" }
  ]
}`,
    response: `HTTP 202 Accepted
{
  "accepted": 2,
  "rejected": 0,
  "events": [ /* array of SecurityEventResponse objects */ ],
  "errors":  []   // [ { "index": N, "error": "..." } ]
}`,
    errors: [
      { code: '401', msg: 'Missing or invalid API key' },
      { code: '422', msg: 'events list empty or exceeds 1,000 items' },
    ],
  },
  {
    id:      'list-events',
    method:  'GET',
    path:    '/api/v1/events',
    summary: 'List events for this project',
    auth:    'Bearer proj_<api_key>',
    desc:    'Returns a paginated list of SecurityEvents belonging to the authenticated project. Always scoped to the API key — cross-project reads are blocked.',
    request: `# Query parameters
?page=1              # default 1
&page_size=100       # default 100, max 1000
&event_type=sql_injection   # optional filter`,
    response: `HTTP 200 OK
{
  "project_id": "prj_01j...",
  "items":      [ /* SecurityEventResponse objects */ ],
  "total":      142,
  "page":       1,
  "page_size":  100
}`,
    errors: [
      { code: '401', msg: 'Missing or invalid API key' },
    ],
  },
  {
    id:      'stream-events',
    method:  'GET',
    path:    '/api/v1/events/stream',
    summary: 'Live SSE event stream',
    auth:    'Bearer proj_<api_key>',
    desc:    'Server-Sent Events stream. Events are pushed to connected clients immediately after ingestion. A keepalive comment is sent every ~25 s. Use fetch() with ReadableStream (EventSource does not support custom headers).',
    request: `// JavaScript
const resp = await fetch("/api/v1/events/stream", {
  headers: { Authorization: "Bearer proj_..." }
});
const reader = resp.body.getReader();
const dec = new TextDecoder();
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  const lines = dec.decode(value).split("\\n");
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const event = JSON.parse(line.slice(6));
      console.log(event);
    }
  }
}`,
    response: `# SSE stream (text/event-stream)
data: {"type":"connected","project_id":"prj_01j..."}

data: {"id":"evt_01j...","event_type":"sql_injection","severity":"critical",...}

: keepalive   ← every ~25 s`,
    errors: [
      { code: '401', msg: 'Missing or invalid API key' },
    ],
  },
  {
    id:      'auth-login',
    method:  'POST',
    path:    '/api/v1/auth/login',
    summary: 'Obtain a JWT access token',
    auth:    'None (public)',
    desc:    'Authenticates a user and returns a short-lived access token (30 min) and a refresh token (7 days). The access token is used for all dashboard API calls.',
    request: `{
  "email":    "user@example.com",
  "password": "SuperSecret123!"
}`,
    response: `HTTP 200 OK
{
  "access_token":  "eyJ...",
  "refresh_token": "ref_...",
  "token_type":    "bearer",
  "expires_in":    1800
}`,
    errors: [
      { code: '401', msg: 'Wrong email or password' },
      { code: '423', msg: 'Account locked (too many failed attempts)' },
    ],
  },
  {
    id:      'demo-events',
    method:  'POST',
    path:    '/api/v1/demo/events',
    summary: 'Inject demo security events',
    auth:    'Bearer <JWT>',
    desc:    'Injects simulated attack events into a project to test the live stream and incident pipeline. Rate limited to 10 s between calls per project. For testing only.',
    request: `{
  "project_id": "prj_01j...",
  "count":      5            // 1-10
}`,
    response: `HTTP 201 Created
{
  "injected":   5,
  "project_id": "prj_01j...",
  "message":    "Injected 5 demo security events into project."
}`,
    errors: [
      { code: '404', msg: 'Project not found' },
      { code: '429', msg: 'Rate limited — wait before retrying' },
    ],
  },
]

const EVENT_TYPES = [
  { name: 'auth_failure',       desc: 'Failed login or auth bypass attempt' },
  { name: 'sql_injection',      desc: 'SQL injection probe or attack' },
  { name: 'xss',                desc: 'Cross-site scripting payload' },
  { name: 'brute_force',        desc: 'Password or credential brute force' },
  { name: 'port_scan',          desc: 'Network port or service scan' },
  { name: 'suspicious_request', desc: 'Anomalous HTTP request or path traversal' },
  { name: 'system_log',         desc: 'OS-level security event (malware, priv-esc)' },
  { name: 'application_log',    desc: 'Application-level security event' },
  { name: 'nginx_log',          desc: 'Nginx access/error log entry' },
  { name: 'apache_log',         desc: 'Apache access/error log entry' },
  { name: 'firewall_event',     desc: 'Firewall block or policy violation' },
  { name: 'windows_event',      desc: 'Windows Event Log entry (Security/System)' },
  { name: 'linux_audit',        desc: 'Linux auditd or auth.log entry' },
  { name: 'custom',             desc: 'Any other event — classified as BENIGN by default' },
]

// ── CopyButton ─────────────────────────────────────────────────────────────
function CopyBtn({ text }: { text: string }) {
  const [ok, setOk] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1800) }) }}
      className="flex items-center gap-1 text-xs transition-colors"
      style={{ color: ok ? '#22c55e' : '#555' }}
    >
      {ok ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      {ok ? 'Copied' : 'Copy'}
    </button>
  )
}

function CodeBlock({ code, lang }: { code: string; lang?: string }) {
  return (
    <div className="rounded-lg overflow-hidden" style={{ border: '1px solid #1e1e1e' }}>
      <div className="flex items-center justify-between px-3 py-1.5" style={{ background: '#0f0f0f', borderBottom: '1px solid #1e1e1e' }}>
        <span className="text-xs text-zinc-600">{lang ?? 'json'}</span>
        <CopyBtn text={code} />
      </div>
      <pre className="p-4 text-xs leading-relaxed overflow-x-auto" style={{ background: '#0a0a0a', color: '#d4d4d4', fontFamily: 'monospace', margin: 0 }}>
        {code}
      </pre>
    </div>
  )
}

function MethodBadge({ method }: { method: string }) {
  const c = METHOD_COLOR[method] ?? '#888'
  return (
    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded" style={{ color: c, background: c + '22' }}>
      {method}
    </span>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────
export default function ApiDocsPage() {
  const [active, setActive] = useState('ingest-event')

  const ep = ENDPOINTS.find(e => e.id === active)!

  return (
    <div className="min-h-screen" style={{ background: BG }}>
      <div className="max-w-6xl mx-auto px-6 py-10">

        {/* Hero */}
        <div className="mb-10">
          <div className="flex items-center gap-2 mb-3">
            <Globe className="w-4 h-4 text-zinc-500" />
            <span className="text-xs text-zinc-500 uppercase tracking-widest">API Reference</span>
          </div>
          <h1 className="font-display text-4xl text-white mb-3">LBRO API</h1>
          <p className="text-zinc-400 max-w-xl">
            REST API for security event ingestion, live streaming, and platform management.
            All event endpoints authenticate via project API keys (Bearer <code className="text-xs bg-zinc-900 px-1 rounded">proj_*</code>).
          </p>
          <div className="flex flex-wrap gap-4 mt-4 text-xs text-zinc-500">
            <span className="flex items-center gap-1.5"><Lock className="w-3 h-3" /> TLS required in production</span>
            <span className="flex items-center gap-1.5"><Zap className="w-3 h-3" /> 60 req / min per API key</span>
            <span className="flex items-center gap-1.5"><Activity className="w-3 h-3" /> 202 Accepted on ingest (async)</span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">

          {/* Sidebar nav */}
          <div className="lg:col-span-1">
            <p className="text-xs text-zinc-600 uppercase tracking-wider mb-3 font-medium">Endpoints</p>
            <nav className="space-y-0.5">
              {ENDPOINTS.map(ep => (
                <button
                  key={ep.id}
                  onClick={() => setActive(ep.id)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all"
                  style={{
                    background:  active === ep.id ? '#1a1a1a' : 'transparent',
                    border:      '1px solid ' + (active === ep.id ? '#2a2a2a' : 'transparent'),
                  }}
                >
                  <MethodBadge method={ep.method} />
                  <span className="text-xs text-zinc-300 truncate">{ep.summary}</span>
                </button>
              ))}
            </nav>

            <div className="mt-6 pt-4" style={{ borderTop: '1px solid #1e1e1e' }}>
              <p className="text-xs text-zinc-600 uppercase tracking-wider mb-3 font-medium">Resources</p>
              <div className="space-y-1">
                <Link to="/projects" className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 py-1 transition-colors">
                  <Code2 className="w-3 h-3" /> Projects
                </Link>
                <Link to="/projects" className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 py-1 transition-colors">
                  <Terminal className="w-3 h-3" /> Integrations
                </Link>
              </div>
            </div>
          </div>

          {/* Main content */}
          <div className="lg:col-span-3 space-y-6">
            {/* Endpoint header */}
            <div>
              <div className="flex items-center gap-3 mb-2">
                <MethodBadge method={ep.method} />
                <code className="text-sm font-mono text-white">{ep.path}</code>
              </div>
              <h2 className="text-xl font-display text-white mb-2">{ep.summary}</h2>
              <p className="text-sm text-zinc-400 leading-relaxed">{ep.desc}</p>
            </div>

            {/* Auth */}
            <div className="rounded-lg border p-4" style={{ background: CARD, borderColor: BORDER }}>
              <div className="flex items-center gap-2 mb-1">
                <Lock className="w-3.5 h-3.5 text-zinc-500" />
                <p className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Authentication</p>
              </div>
              <code className="text-sm text-green-400 font-mono">Authorization: Bearer {ep.auth}</code>
            </div>

            {/* Request */}
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2 font-medium">Request</p>
              <CodeBlock code={ep.request} lang={ep.method === 'GET' ? 'bash' : 'json'} />
            </div>

            {/* Response */}
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2 font-medium">Response</p>
              <CodeBlock code={ep.response} lang="json" />
            </div>

            {/* Errors */}
            {ep.errors.length > 0 && (
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2 font-medium">Error codes</p>
                <div className="rounded-lg overflow-hidden" style={{ border: '1px solid #1e1e1e' }}>
                  {ep.errors.map((e, i) => (
                    <div key={e.code} className="flex items-center gap-4 px-4 py-2.5" style={{ background: i % 2 === 0 ? '#0a0a0a' : CARD, borderBottom: i < ep.errors.length - 1 ? '1px solid #1e1e1e' : 'none' }}>
                      <code className="text-xs font-mono font-bold w-10 shrink-0" style={{ color: '#ef4444' }}>{e.code}</code>
                      <span className="text-xs text-zinc-400">{e.msg}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Event types table */}
        <div className="mt-12 pt-8" style={{ borderTop: '1px solid #1e1e1e' }}>
          <h2 className="font-display text-2xl text-white mb-2">Event Types</h2>
          <p className="text-sm text-zinc-500 mb-6">Valid values for the <code className="text-xs bg-zinc-900 px-1 rounded">event_type</code> field.</p>
          <div className="rounded-xl overflow-hidden" style={{ border: '1px solid #1e1e1e' }}>
            {EVENT_TYPES.map((et, i) => (
              <div key={et.name} className="flex items-center gap-4 px-5 py-3" style={{ background: i % 2 === 0 ? '#0a0a0a' : CARD, borderBottom: i < EVENT_TYPES.length - 1 ? '1px solid #1e1e1e' : 'none' }}>
                <code className="text-xs font-mono text-green-400 w-44 shrink-0">{et.name}</code>
                <span className="text-xs text-zinc-400">{et.desc}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Rate limits */}
        <div className="mt-10 pt-8" style={{ borderTop: '1px solid #1e1e1e' }}>
          <h2 className="font-display text-2xl text-white mb-2">Rate Limits</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
            {[
              { limit: '60 req / min', scope: 'Per project API key', note: 'POST /events, GET /events' },
              { limit: '1,000 events', scope: 'Per batch request',   note: 'POST /events/batch' },
              { limit: '10 s cooldown', scope: 'Demo injection',     note: 'POST /demo/events' },
            ].map(r => (
              <div key={r.limit} className="rounded-xl border p-4" style={{ background: CARD, borderColor: BORDER }}>
                <p className="text-xl font-display text-white mb-1">{r.limit}</p>
                <p className="text-xs text-zinc-400">{r.scope}</p>
                <p className="text-xs text-zinc-600 mt-1">{r.note}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
