/**
 * IntegrationsPage — all integration code snippets for a project.
 *
 * Route: /projects/:projectId/integrations
 */
import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft, Copy, Check, Terminal, ChevronRight,
  Search, ExternalLink,
} from 'lucide-react'
import { projectsApi } from '@/api/client'

const BG     = '#080808'
const CARD   = '#0f0f0f'
const BORDER = '#1e1e1e'
const ORANGE = '#e54e1b'

// ── Integration catalog ────────────────────────────────────────────────────
interface Integration {
  id:       string
  name:     string
  icon:     string
  color:    string
  category: string
  tags:     string[]
}

const CATALOG: Integration[] = [
  { id:'python',   name:'Python',         icon:'🐍', color:'#3b82f6', category:'SDK',    tags:['backend','script'] },
  { id:'nodejs',   name:'Node.js',        icon:'⬢',  color:'#22c55e', category:'SDK',    tags:['backend','javascript'] },
  { id:'java',     name:'Java',           icon:'☕', color:'#f59e0b', category:'SDK',    tags:['backend','jvm'] },
  { id:'go',       name:'Go',             icon:'🐹', color:'#06b6d4', category:'SDK',    tags:['backend','compiled'] },
  { id:'express',  name:'Express',        icon:'🚂', color:'#6b7280', category:'SDK',    tags:['nodejs','web'] },
  { id:'fastapi',  name:'FastAPI',        icon:'⚡', color:'#22c55e', category:'SDK',    tags:['python','web','async'] },
  { id:'flask',    name:'Flask',          icon:'🧪', color:'#a855f7', category:'SDK',    tags:['python','web'] },
  { id:'django',   name:'Django',         icon:'🎸', color:'#22c55e', category:'SDK',    tags:['python','web'] },
  { id:'spring',   name:'Spring Boot',    icon:'🍃', color:'#22c55e', category:'SDK',    tags:['java','web'] },
  { id:'aspnet',   name:'ASP.NET',        icon:'🟣', color:'#a855f7', category:'SDK',    tags:['dotnet','web'] },
  { id:'laravel',  name:'Laravel',        icon:'🎨', color:'#ef4444', category:'SDK',    tags:['php','web'] },
  { id:'php',      name:'PHP',            icon:'🐘', color:'#6366f1', category:'SDK',    tags:['web','scripting'] },
  { id:'docker',   name:'Docker',         icon:'🐳', color:'#3b82f6', category:'Agent',  tags:['container','infra'] },
  { id:'nginx',    name:'Nginx',          icon:'⚡', color:'#22c55e', category:'Agent',  tags:['web server','proxy'] },
  { id:'apache',   name:'Apache',         icon:'🪶', color:'#ef4444', category:'Agent',  tags:['web server'] },
  { id:'windows',  name:'Windows Events', icon:'🪟', color:'#3b82f6', category:'Agent',  tags:['windows','siem'] },
  { id:'syslog',   name:'Linux Syslog',   icon:'🐧', color:'#f59e0b', category:'Agent',  tags:['linux','siem'] },
]

// ── Snippets (same as Wizard — inlined for standalone page) ───────────────
function buildSnippet(id: string, apiKey: string): { install: string; code: string } {
  const k    = apiKey || 'proj_your_api_key_here'
  const BASE = typeof window !== 'undefined' ? window.location.origin : 'https://your-lbro-instance.com'

  const MAP: Record<string, { install: string; code: string }> = {
    python: {
      install: 'pip install requests',
      code:
`import requests

LBRO = requests.Session()
LBRO.headers.update({
    "Authorization": "Bearer ${k}",
    "Content-Type":  "application/json",
})

def send_event(event_type, severity, message, source_ip=None, payload=None):
    resp = LBRO.post("${BASE}/api/v1/events", json={
        "event_type": event_type,
        "severity":   severity,
        "message":    message,
        "source_ip":  source_ip,
        "payload":    payload or {},
    })
    resp.raise_for_status()
    return resp.json()

# Example — report a brute-force attack
send_event("brute_force", "high", "Login flood: 200 attempts in 30s", "203.0.113.1")`,
    },
    nodejs: {
      install: 'npm install node-fetch',
      code:
`const fetch = require("node-fetch");

const LBRO_KEY  = "${k}";
const LBRO_BASE = "${BASE}";

async function sendEvent({ eventType, severity, message, sourceIp, payload = {} }) {
  const res = await fetch(\`\${LBRO_BASE}/api/v1/events\`, {
    method: "POST",
    headers: {
      "Authorization": \`Bearer \${LBRO_KEY}\`,
      "Content-Type":  "application/json",
    },
    body: JSON.stringify({ event_type: eventType, severity, message, source_ip: sourceIp, payload }),
  });
  if (!res.ok) throw new Error(\`LBRO \${res.status}\`);
  return res.json();
}

// Example — report SQL injection probe
sendEvent({ eventType: "sql_injection", severity: "critical", message: "SQLi on /api/users", sourceIp: "185.220.101.42" });`,
    },
    java: {
      install: '// Uses java.net.http — requires Java 11+, no extra deps',
      code:
`import java.net.URI;
import java.net.http.*;
import java.net.http.HttpRequest.BodyPublishers;

public class LBROClient {
    private static final String API_KEY  = "${k}";
    private static final String BASE_URL = "${BASE}";
    private final HttpClient http = HttpClient.newHttpClient();

    public String sendEvent(String type, String severity, String message) throws Exception {
        String json = String.format(
            "{\\"event_type\\":\\"%s\\",\\"severity\\":\\"%s\\",\\"message\\":\\"%s\\"}",
            type, severity, message);
        var req = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/v1/events"))
            .header("Authorization", "Bearer " + API_KEY)
            .header("Content-Type", "application/json")
            .POST(BodyPublishers.ofString(json)).build();
        return http.send(req, HttpResponse.BodyHandlers.ofString()).body();
    }

    // Example
    public static void main(String[] args) throws Exception {
        new LBROClient().sendEvent("port_scan", "medium", "SYN scan detected");
    }
}`,
    },
    go: {
      install: '// Standard library only — no modules to add',
      code:
`package lbro

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

const APIKey  = "${k}"
const BaseURL = "${BASE}"

type Event struct {
    EventType string         \`json:"event_type"\`
    Severity  string         \`json:"severity"\`
    Message   string         \`json:"message"\`
    SourceIP  string         \`json:"source_ip,omitempty"\`
    Payload   map[string]any \`json:"payload,omitempty"\`
}

func Send(e Event) error {
    body, _ := json.Marshal(e)
    req, _  := http.NewRequest("POST", BaseURL+"/api/v1/events", bytes.NewReader(body))
    req.Header.Set("Authorization", "Bearer "+APIKey)
    req.Header.Set("Content-Type", "application/json")
    resp, err := http.DefaultClient.Do(req)
    if err != nil { return err }
    defer resp.Body.Close()
    if resp.StatusCode != 202 { return fmt.Errorf("LBRO: %d", resp.StatusCode) }
    return nil
}`,
    },
    fastapi: {
      install: 'pip install requests',
      code:
`from fastapi import FastAPI, Request
import requests, time

app = FastAPI()
_LBRO = requests.Session()
_LBRO.headers["Authorization"] = "Bearer ${k}"

@app.middleware("http")
async def lbro_security_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = int((time.perf_counter() - start) * 1000)

    if response.status_code >= 400:
        severity = "critical" if response.status_code >= 500 else "high" if response.status_code == 403 else "medium"
        _LBRO.post("${BASE}/api/v1/events", json={
            "event_type": "suspicious_request",
            "severity":   severity,
            "message":    f"{request.method} {request.url.path} -> {response.status_code}",
            "source_ip":  request.client.host if request.client else None,
            "payload":    {"status_code": response.status_code, "duration_ms": ms},
        })
    return response`,
    },
    express: {
      install: 'npm install node-fetch',
      code:
`const fetch = require("node-fetch");

const LBRO_KEY  = "${k}";
const LBRO_BASE = "${BASE}";

// Drop-in Express middleware
function lbroMiddleware(req, res, next) {
  res.on("finish", () => {
    if (res.statusCode >= 400) {
      fetch(\`\${LBRO_BASE}/api/v1/events\`, {
        method: "POST",
        headers: { "Authorization": \`Bearer \${LBRO_KEY}\`, "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: res.statusCode === 401 || res.statusCode === 403 ? "auth_failure" : "suspicious_request",
          severity:   res.statusCode >= 500 ? "high" : "medium",
          message:    \`\${req.method} \${req.originalUrl} -> \${res.statusCode}\`,
          source_ip:  req.ip,
        }),
      }).catch(() => {});
    }
  });
  next();
}

module.exports = lbroMiddleware;
// Usage: app.use(require("./lbro-middleware"));`,
    },
    flask: {
      install: 'pip install requests',
      code:
`from flask import Flask, request
import requests

app = Flask(__name__)
_LBRO = requests.Session()
_LBRO.headers["Authorization"] = "Bearer ${k}"

@app.after_request
def lbro_log(response):
    if response.status_code >= 400:
        _LBRO.post("${BASE}/api/v1/events", json={
            "event_type": "suspicious_request",
            "severity":   "high" if response.status_code >= 500 else "medium",
            "message":    f"{request.method} {request.path} -> {response.status_code}",
            "source_ip":  request.remote_addr,
        })
    return response`,
    },
    django: {
      install: 'pip install requests',
      code:
`# myapp/middleware.py
import requests

class LBROMiddleware:
    _lbro = requests.Session()
    _lbro.headers["Authorization"] = "Bearer ${k}"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code >= 400:
            self._lbro.post("${BASE}/api/v1/events", json={
                "event_type": "suspicious_request",
                "severity":   "high" if response.status_code >= 500 else "medium",
                "message":    f"{request.method} {request.path} -> {response.status_code}",
                "source_ip":  request.META.get("REMOTE_ADDR"),
            })
        return response

# settings.py → MIDDLEWARE list:
# "myapp.middleware.LBROMiddleware",`,
    },
    spring: {
      install: '// spring-boot-starter-web — no extra dependency',
      code:
`import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import javax.servlet.*;
import javax.servlet.http.*;
import java.io.IOException;
import java.util.Map;

@Component
public class LBROFilter implements Filter {
    private static final String KEY  = "${k}";
    private static final String URL  = "${BASE}/api/v1/events";
    private final RestTemplate rest  = new RestTemplate();

    @Override public void doFilter(
            ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {
        chain.doFilter(req, res);
        int status = ((HttpServletResponse) res).getStatus();
        if (status >= 400) {
            org.springframework.http.HttpHeaders h = new org.springframework.http.HttpHeaders();
            h.set("Authorization", "Bearer " + KEY);
            h.setContentType(org.springframework.http.MediaType.APPLICATION_JSON);
            rest.postForEntity(URL, new org.springframework.http.HttpEntity<>(
                Map.of("event_type","suspicious_request","severity","medium","message","HTTP "+status), h),
                String.class);
        }
    }
}`,
    },
    aspnet: {
      install: '// System.Net.Http — built into .NET',
      code:
`// Middleware/LBROMiddleware.cs
using System.Net.Http;
using System.Text;
using System.Text.Json;

public class LBROMiddleware {
    const string ApiKey  = "${k}";
    const string BaseUrl = "${BASE}/api/v1/events";
    readonly RequestDelegate _next;
    static readonly HttpClient _http = new();

    public LBROMiddleware(RequestDelegate next) { _next = next; }

    public async Task InvokeAsync(HttpContext ctx) {
        await _next(ctx);
        if (ctx.Response.StatusCode >= 400) {
            var payload = JsonSerializer.Serialize(new {
                event_type = "suspicious_request",
                severity   = ctx.Response.StatusCode >= 500 ? "high" : "medium",
                message    = $"HTTP {ctx.Response.StatusCode} {ctx.Request.Path}",
                source_ip  = ctx.Connection.RemoteIpAddress?.ToString(),
            });
            using var msg = new HttpRequestMessage(HttpMethod.Post, BaseUrl) {
                Content = new StringContent(payload, Encoding.UTF8, "application/json")
            };
            msg.Headers.Add("Authorization", "Bearer " + ApiKey);
            await _http.SendAsync(msg);
        }
    }
}
// Program.cs → app.UseMiddleware<LBROMiddleware>();`,
    },
    laravel: {
      install: '# Built-in Http client — Laravel 7+',
      code:
`<?php
// app/Http/Middleware/LBRO.php
namespace App\\Http\\Middleware;
use Closure;
use Illuminate\\Support\\Facades\\Http;

class LBRO {
    const KEY  = "${k}";
    const BASE = "${BASE}";

    public function handle($request, Closure $next) {
        $response = $next($request);
        if ($response->status() >= 400) {
            Http::withToken(self::KEY)->post(self::BASE . "/api/v1/events", [
                "event_type" => "suspicious_request",
                "severity"   => $response->status() >= 500 ? "high" : "medium",
                "message"    => "HTTP {$response->status()} on {$request->path()}",
                "source_ip"  => $request->ip(),
            ]);
        }
        return $response;
    }
}
// Kernel.php → \\App\\Http\\Middleware\\LBRO::class`,
    },
    php: {
      install: '# Uses built-in cURL',
      code:
`<?php
function lbro_event(string $type, string $severity, string $message, ?string $ip = null): array {
    $ch = curl_init("${BASE}/api/v1/events");
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => [
            "Authorization: Bearer ${k}",
            "Content-Type: application/json",
        ],
        CURLOPT_POSTFIELDS => json_encode([
            "event_type" => $type,
            "severity"   => $severity,
            "message"    => $message,
            "source_ip"  => $ip,
        ]),
    ]);
    $result = json_decode(curl_exec($ch), true);
    curl_close($ch);
    return $result ?? [];
}

// Example — 401 guard
if (!$_SESSION['user']) {
    lbro_event("auth_failure", "medium", "Unauthenticated request to " . $_SERVER["REQUEST_URI"], $_SERVER["REMOTE_ADDR"]);
}`,
    },
    docker: {
      install: '# docker-compose.yml',
      code:
`services:
  your-app:
    image: your-app:latest
    # ... existing config

  lbro-agent:
    image: lbro/agent:latest
    environment:
      LBRO_API_KEY:  "${k}"
      LBRO_BASE_URL: "${BASE}"
      LBRO_APP_NAME: "my-app"
    volumes:
      - /var/log/nginx:/logs/nginx:ro
      - /var/log/apache2:/logs/apache:ro
      - /var/log/syslog:/logs/syslog:ro
      # Mount app-specific log files:
      # - /var/log/myapp:/logs/app:ro
    restart: unless-stopped
    depends_on:
      - your-app`,
    },
    nginx: {
      install: '# wget https://releases.lbro.io/agent/latest/lbro-agent-linux-amd64',
      code:
`# /etc/lbro-agent/config.yaml
api_key:  "${k}"
base_url: "${BASE}"
app_name: "nginx-prod"

log_files:
  - path:   /var/log/nginx/access.log
    format: nginx
    follow: true
  - path:   /var/log/nginx/error.log
    format: nginx
    follow: true

# /etc/systemd/system/lbro-agent.service
# [Service]
# ExecStart=/usr/local/bin/lbro-agent --config /etc/lbro-agent/config.yaml
# Restart=always

# systemctl enable --now lbro-agent`,
    },
    apache: {
      install: '# wget https://releases.lbro.io/agent/latest/lbro-agent-linux-amd64',
      code:
`# /etc/lbro-agent/config.yaml
api_key:  "${k}"
base_url: "${BASE}"
app_name: "apache-prod"

log_files:
  - path:   /var/log/apache2/access.log
    format: apache
    follow: true
  - path:   /var/log/apache2/error.log
    format: apache
    follow: true

# systemctl enable --now lbro-agent`,
    },
    windows: {
      install: '# Download: https://releases.lbro.io/agent/latest/lbro-agent-windows-amd64.exe',
      code:
`# PowerShell — run as Administrator
$configDir  = "C:\\ProgramData\\lbro-agent"
$configFile = "$configDir\\config.json"

New-Item -ItemType Directory -Force $configDir | Out-Null
@{
    api_key  = "${k}"
    base_url = "${BASE}"
    sources  = @(
        @{
            type     = "windows_event_log"
            channels = @("Security", "System", "Application")
            level    = "warning"   # warning, error, critical
        }
    )
} | ConvertTo-Json -Depth 5 | Set-Content $configFile

# Install and start as a Windows Service
New-Service -Name "LBROAgent" \`
    -BinaryPathName "C:\\lbro-agent.exe --service --config $configFile" \`
    -DisplayName "LBRO Security Agent" \`
    -StartupType Automatic
Start-Service LBROAgent`,
    },
    syslog: {
      install: '# wget https://releases.lbro.io/agent/latest/lbro-agent-linux-amd64',
      code:
`# /etc/lbro-agent/config.yaml
api_key:  "${k}"
base_url: "${BASE}"
app_name: "linux-prod"

syslog_listener:
  address:  "127.0.0.1:5141"
  protocol: udp

# /etc/rsyslog.d/50-lbro.conf
# *.* @127.0.0.1:5141

# Also tail kernel/auth logs directly:
log_files:
  - path:   /var/log/auth.log
    format: syslog
    follow: true
  - path:   /var/log/kern.log
    format: syslog
    follow: true

# systemctl restart rsyslog && systemctl enable --now lbro-agent`,
    },
  }

  return MAP[id] ?? { install: '', code: '# Integration snippet not found' }
}

// ── curl examples ──────────────────────────────────────────────────────────
const CURL_EVENTS = [
  { label:'SQL Injection',    type:'sql_injection',   sev:'critical', msg:"SQLi probe on /api/users",               ip:'185.220.101.42' },
  { label:'Brute Force',      type:'brute_force',     sev:'high',     msg:'200 failed logins in 60s',              ip:'94.102.49.190'  },
  { label:'Port Scan',        type:'port_scan',       sev:'medium',   msg:'SYN scan ports 1-65535',                ip:'203.0.113.55'   },
  { label:'XSS',              type:'xss',             sev:'high',     msg:'Reflected XSS in search param',         ip:'198.51.100.23'  },
  { label:'Auth Failure',     type:'auth_failure',    sev:'medium',   msg:'Login failed: bad password (attempt 8)',ip:'104.21.14.101'  },
  { label:'Malware',          type:'system_log',      sev:'critical', msg:'Malware sig: Trojan.GenericKD.48752',   ip:'10.0.0.15'      },
  { label:'Suspicious Login', type:'auth_failure',    sev:'high',     msg:'Login from new country: NG (usual: US)',ip:'197.210.84.195' },
]

// ── CopyButton ─────────────────────────────────────────────────────────────
function CopyBtn({ text }: { text: string }) {
  const [ok, setOk] = useState(false)
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1800) }) }}
      className="flex items-center gap-1 transition-colors text-xs"
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
        <span className="text-xs text-zinc-600">{lang ?? 'bash'}</span>
        <CopyBtn text={code} />
      </div>
      <pre className="p-4 text-xs leading-relaxed overflow-x-auto" style={{ background: '#0a0a0a', color: '#d4d4d4', fontFamily: 'monospace', margin: 0 }}>
        {code}
      </pre>
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────
const CATEGORIES = ['All', 'SDK', 'Agent']

export default function IntegrationsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [selected, setSelected] = useState('python')
  const [category, setCategory] = useState('All')
  const [search,   setSearch]   = useState('')
  const [curlIdx,  setCurlIdx]  = useState(0)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn:  () => projectsApi.get(projectId!),
    enabled:  !!projectId,
  })

  const apiKey = project?.api_key ?? ''
  const sel    = CATALOG.find(c => c.id === selected)!
  const snip   = buildSnippet(selected, apiKey)
  const curl   = CURL_EVENTS[curlIdx]
  const curlCmd = `curl -X POST ${typeof window !== 'undefined' ? window.location.origin : ''}/api/v1/events \\
  -H "Authorization: Bearer ${apiKey || 'proj_your_key'}" \\
  -H "Content-Type: application/json" \\
  -d '{"event_type":"${curl.type}","severity":"${curl.sev}","message":"${curl.msg}","source_ip":"${curl.ip}"}'`

  const filtered = CATALOG.filter(c => {
    const matchCat = category === 'All' || c.category === category
    const matchSearch = !search || c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.tags.some(t => t.toLowerCase().includes(search.toLowerCase()))
    return matchCat && matchSearch
  })

  return (
    <div className="min-h-screen" style={{ background: BG }}>
      <div className="max-w-6xl mx-auto px-6 py-10">

        {/* Header */}
        <div className="mb-8">
          <Link to={`/projects/${projectId}`}
            className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 mb-4 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to project
          </Link>
          <h1 className="font-display text-3xl text-white">Integrations</h1>
          <p className="text-sm text-zinc-500 mt-1">Connect your application to LBRO in under 5 minutes</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left: integration picker */}
          <div>
            {/* Search + filter */}
            <div className="mb-4 space-y-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-600" />
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search integrations..."
                  className="w-full pl-8 pr-3 py-2 rounded-lg text-xs text-white outline-none"
                  style={{ background: CARD, border: '1px solid ' + BORDER, fontSize: 12 }}
                />
              </div>
              <div className="flex gap-2">
                {CATEGORIES.map(c => (
                  <button key={c} onClick={() => setCategory(c)}
                    className="px-3 py-1 rounded text-xs transition-all"
                    style={{
                      background: category === c ? ORANGE + '22' : '#1a1a1a',
                      color:      category === c ? ORANGE : '#666',
                      border:     '1px solid ' + (category === c ? ORANGE + '44' : '#222'),
                    }}
                  >{c}</button>
                ))}
              </div>
            </div>

            {/* List */}
            <div className="space-y-1">
              {filtered.map(int => (
                <button
                  key={int.id}
                  onClick={() => setSelected(int.id)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all"
                  style={{
                    background:  selected === int.id ? int.color + '15' : 'transparent',
                    border:      '1px solid ' + (selected === int.id ? int.color + '40' : 'transparent'),
                  }}
                >
                  <span className="text-lg w-6 text-center shrink-0">{int.icon}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white truncate">{int.name}</p>
                    <p className="text-xs" style={{ color: int.color + 'aa' }}>{int.category}</p>
                  </div>
                  {selected === int.id && <ChevronRight className="w-3.5 h-3.5" style={{ color: int.color }} />}
                </button>
              ))}
            </div>
          </div>

          {/* Right: code panel */}
          <div className="lg:col-span-2 space-y-5">
            {/* Title */}
            <div className="flex items-center gap-3 pb-4" style={{ borderBottom: '1px solid ' + BORDER }}>
              <span className="text-2xl">{sel.icon}</span>
              <div>
                <h2 className="font-display text-xl text-white">{sel.name}</h2>
                <p className="text-xs text-zinc-500">
                  {sel.category === 'SDK' ? 'Add to your application code' : 'Run alongside your infrastructure'}
                </p>
              </div>
              <span className="ml-auto text-xs px-2 py-0.5 rounded" style={{ background: sel.color + '22', color: sel.color }}>
                {sel.category}
              </span>
            </div>

            {snip.install && (
              <div>
                <p className="text-xs text-zinc-500 mb-2 font-medium uppercase tracking-wide">Install</p>
                <CodeBlock code={snip.install} lang="bash" />
              </div>
            )}

            <div>
              <p className="text-xs text-zinc-500 mb-2 font-medium uppercase tracking-wide">Code</p>
              <CodeBlock code={snip.code} lang={
                ['nodejs','express'].includes(selected) ? 'javascript' :
                ['java','spring'].includes(selected) ? 'java' :
                selected === 'go' ? 'go' :
                ['aspnet'].includes(selected) ? 'csharp' :
                ['php','laravel'].includes(selected) ? 'php' : 'python'
              } />
            </div>

            {/* curl section */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-zinc-500 font-medium uppercase tracking-wide">cURL Examples</p>
                <Terminal className="w-3.5 h-3.5 text-zinc-600" />
              </div>
              <div className="flex flex-wrap gap-1.5 mb-3">
                {CURL_EVENTS.map((ev, i) => (
                  <button key={i} onClick={() => setCurlIdx(i)}
                    className="text-xs px-2 py-1 rounded transition-all"
                    style={{
                      background: curlIdx === i ? ORANGE + '22' : '#161616',
                      color:      curlIdx === i ? ORANGE : '#555',
                      border:     '1px solid ' + (curlIdx === i ? ORANGE + '40' : '#1e1e1e'),
                    }}
                  >{ev.label}</button>
                ))}
              </div>
              <CodeBlock code={curlCmd} lang="bash" />
            </div>

            {/* Docs link */}
            <div className="flex items-center gap-2 pt-2">
              <Link to="/docs" className="text-xs text-zinc-500 hover:text-zinc-300 flex items-center gap-1 transition-colors">
                <ExternalLink className="w-3 h-3" /> Full API documentation
              </Link>
              <span className="text-zinc-700">·</span>
              <Link to={`/projects/${projectId}/events`} className="text-xs flex items-center gap-1 transition-colors" style={{ color: ORANGE }}>
                <Terminal className="w-3 h-3" /> Live event stream
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
