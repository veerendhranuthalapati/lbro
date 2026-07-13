/**
 * ProjectSetupWizardPage — post-creation onboarding wizard.
 *
 * Step 1: Project created — show name/env/ID/API key
 * Step 2: Choose integration — 17 tiles
 * Step 3: Send first event — language snippet + curl examples
 *
 * Redirected here automatically after project creation.
 */
import { useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Check, Copy, Download, RefreshCw, ChevronRight, ArrowRight,
  Terminal, Code2, Zap, Globe, Loader2, Key, Eye, EyeOff,
} from 'lucide-react'
import { projectsApi } from '@/api/client'
import type { ProjectEnvironment } from '@/types'

// ── constants ──────────────────────────────────────────────────────────────
const ORANGE = '#e54e1b'
const BG     = '#080808'
const CARD   = '#0f0f0f'
const BORDER = '#1e1e1e'
const MUTED  = '#3a3a3a'

const ENV_COLOR: Record<ProjectEnvironment, string> = {
  production:  '#ef4444',
  staging:     '#f59e0b',
  development: '#22c55e',
}

// ── Integrations ───────────────────────────────────────────────────────────
interface Integration {
  id:    string
  name:  string
  icon:  string
  color: string
  tag:   string
}

const INTEGRATIONS: Integration[] = [
  { id: 'python',     name: 'Python',            icon: '🐍', color: '#3b82f6', tag: 'SDK'    },
  { id: 'nodejs',     name: 'Node.js',           icon: '⬢',  color: '#22c55e', tag: 'SDK'    },
  { id: 'java',       name: 'Java',              icon: '☕', color: '#f59e0b', tag: 'SDK'    },
  { id: 'go',         name: 'Go',                icon: '🐹', color: '#06b6d4', tag: 'SDK'    },
  { id: 'docker',     name: 'Docker',            icon: '🐳', color: '#3b82f6', tag: 'Agent'  },
  { id: 'nginx',      name: 'Nginx',             icon: '⚡', color: '#22c55e', tag: 'Agent'  },
  { id: 'apache',     name: 'Apache',            icon: '🪶', color: '#ef4444', tag: 'Agent'  },
  { id: 'express',    name: 'Express',           icon: '🚂', color: '#6b7280', tag: 'SDK'    },
  { id: 'fastapi',    name: 'FastAPI',           icon: '⚡', color: '#22c55e', tag: 'SDK'    },
  { id: 'flask',      name: 'Flask',             icon: '🧪', color: '#a855f7', tag: 'SDK'    },
  { id: 'spring',     name: 'Spring Boot',       icon: '🍃', color: '#22c55e', tag: 'SDK'    },
  { id: 'django',     name: 'Django',            icon: '🎸', color: '#22c55e', tag: 'SDK'    },
  { id: 'aspnet',     name: 'ASP.NET',           icon: '🟣', color: '#a855f7', tag: 'SDK'    },
  { id: 'php',        name: 'PHP',               icon: '🐘', color: '#6366f1', tag: 'SDK'    },
  { id: 'laravel',    name: 'Laravel',           icon: '🎨', color: '#ef4444', tag: 'SDK'    },
  { id: 'windows',    name: 'Windows Events',    icon: '🪟', color: '#3b82f6', tag: 'Agent'  },
  { id: 'syslog',     name: 'Linux Syslog',      icon: '🐧', color: '#f59e0b', tag: 'Agent'  },
]

// ── Code snippets ──────────────────────────────────────────────────────────
function getSnippet(integrationId: string, apiKey: string): { install: string; code: string } {
  const k = apiKey || 'proj_your_api_key_here'
  const BASE = 'https://your-lbro-instance.com'

  const snippets: Record<string, { install: string; code: string }> = {
    python: {
      install: 'pip install requests',
      code: `import requests

client = requests.Session()
client.headers.update({
    "Authorization": "Bearer ${k}",
    "Content-Type":  "application/json",
})

def send_event(event_type, severity, message, source_ip=None):
    resp = client.post("${BASE}/api/v1/events", json={
        "event_type": event_type,
        "severity":   severity,
        "message":    message,
        "source_ip":  source_ip,
    })
    resp.raise_for_status()
    return resp.json()

# Example: report a failed login
send_event("auth_failure", "medium", "Login failed for user admin", "203.0.113.1")`,
    },
    nodejs: {
      install: 'npm install node-fetch',
      code: `const fetch = require("node-fetch");

const LBRO_KEY  = "${k}";
const LBRO_BASE = "${BASE}";

async function sendEvent(eventType, severity, message, sourceIp) {
  const res = await fetch(\`\${LBRO_BASE}/api/v1/events\`, {
    method:  "POST",
    headers: {
      "Authorization": \`Bearer \${LBRO_KEY}\`,
      "Content-Type":  "application/json",
    },
    body: JSON.stringify({ event_type: eventType, severity, message, source_ip: sourceIp }),
  });
  if (!res.ok) throw new Error(\`LBRO error: \${res.status}\`);
  return res.json();
}

// Example: report SQL injection
sendEvent("sql_injection", "critical", "SQLi probe on /api/users", "185.220.101.42");`,
    },
    java: {
      install: '// No extra dependencies needed — uses java.net.http (Java 11+)',
      code: `import java.net.URI;
import java.net.http.*;
import java.net.http.HttpRequest.BodyPublishers;

public class LBROClient {
    private static final String API_KEY  = "${k}";
    private static final String BASE_URL = "${BASE}";
    private final HttpClient http = HttpClient.newHttpClient();

    public void sendEvent(String type, String severity, String message) throws Exception {
        String body = String.format(
            "{\\"event_type\\":\\"%s\\",\\"severity\\":\\"%s\\",\\"message\\":\\"%s\\"}",
            type, severity, message);
        HttpRequest req = HttpRequest.newBuilder()
            .uri(URI.create(BASE_URL + "/api/v1/events"))
            .header("Authorization", "Bearer " + API_KEY)
            .header("Content-Type", "application/json")
            .POST(BodyPublishers.ofString(body))
            .build();
        http.send(req, HttpResponse.BodyHandlers.ofString());
    }
}`,
    },
    go: {
      install: '// Uses standard library only — no extra modules needed',
      code: `package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

const (
    APIKey  = "${k}"
    BaseURL = "${BASE}"
)

type Event struct {
    EventType string \`json:"event_type"\`
    Severity  string \`json:"severity"\`
    Message   string \`json:"message"\`
    SourceIP  string \`json:"source_ip,omitempty"\`
}

func SendEvent(e Event) error {
    body, _ := json.Marshal(e)
    req, _ := http.NewRequest("POST", BaseURL+"/api/v1/events", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+APIKey)
    req.Header.Set("Content-Type", "application/json")
    resp, err := http.DefaultClient.Do(req)
    if err != nil { return err }
    defer resp.Body.Close()
    if resp.StatusCode != 202 {
        return fmt.Errorf("LBRO returned %d", resp.StatusCode)
    }
    return nil
}`,
    },
    docker: {
      install: '# Pull the LBRO agent image',
      code: `# docker-compose.yml — add alongside your app
services:
  lbro-agent:
    image: lbro/agent:latest
    environment:
      LBRO_API_KEY:  "${k}"
      LBRO_BASE_URL: "${BASE}"
    volumes:
      - /var/log/nginx:/logs/nginx:ro
      - /var/log/apache2:/logs/apache:ro
      - /var/log/syslog:/logs/syslog:ro
    restart: unless-stopped`,
    },
    nginx: {
      install: '# Download and configure lbro-agent',
      code: `# /etc/lbro-agent/config.yaml
api_key:  "${k}"
base_url: "${BASE}"

log_files:
  - path:   /var/log/nginx/access.log
    format: nginx
  - path:   /var/log/nginx/error.log
    format: nginx

# Start the agent
# lbro-agent --config /etc/lbro-agent/config.yaml`,
    },
    fastapi: {
      install: 'pip install requests',
      code: `from fastapi import FastAPI, Request
import requests, time

app = FastAPI()
LBRO = requests.Session()
LBRO.headers["Authorization"] = "Bearer ${k}"

@app.middleware("http")
async def lbro_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    if response.status_code >= 400:
        LBRO.post("${BASE}/api/v1/events", json={
            "event_type": "suspicious_request",
            "severity":   "high" if response.status_code >= 500 else "medium",
            "message":    f"{request.method} {request.url.path} -> {response.status_code}",
            "source_ip":  request.client.host,
            "payload":    {"status_code": response.status_code, "duration_ms": int(duration * 1000)},
        })
    return response`,
    },
    express: {
      install: 'npm install node-fetch',
      code: `const fetch = require("node-fetch");

const LBRO_KEY  = "${k}";
const LBRO_BASE = "${BASE}";

// Express middleware
app.use(async (req, res, next) => {
  res.on("finish", () => {
    if (res.statusCode >= 400) {
      fetch(\`\${LBRO_BASE}/api/v1/events\`, {
        method: "POST",
        headers: {
          "Authorization": \`Bearer \${LBRO_KEY}\`,
          "Content-Type":  "application/json",
        },
        body: JSON.stringify({
          event_type: "suspicious_request",
          severity:   res.statusCode >= 500 ? "high" : "medium",
          message:    \`\${req.method} \${req.path} -> \${res.statusCode}\`,
          source_ip:  req.ip,
        }),
      }).catch(() => {});
    }
  });
  next();
});`,
    },
    flask: {
      install: 'pip install requests',
      code: `from flask import Flask, request, g
import requests, time

app = Flask(__name__)
LBRO = requests.Session()
LBRO.headers["Authorization"] = "Bearer ${k}"

@app.after_request
def log_to_lbro(response):
    if response.status_code >= 400:
        LBRO.post("${BASE}/api/v1/events", json={
            "event_type": "suspicious_request",
            "severity":   "high" if response.status_code >= 500 else "medium",
            "message":    f"{request.method} {request.path} -> {response.status_code}",
            "source_ip":  request.remote_addr,
        })
    return response`,
    },
    django: {
      install: 'pip install requests',
      code: `# middleware.py
import requests

class LBROMiddleware:
    LBRO = requests.Session()
    LBRO.headers["Authorization"] = "Bearer ${k}"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code >= 400:
            self.LBRO.post("${BASE}/api/v1/events", json={
                "event_type": "suspicious_request",
                "severity":   "high" if response.status_code >= 500 else "medium",
                "message":    f"{request.method} {request.path} -> {response.status_code}",
                "source_ip":  request.META.get("REMOTE_ADDR"),
            })
        return response

# settings.py
MIDDLEWARE = ["myapp.middleware.LBROMiddleware", ...]`,
    },
    spring: {
      install: '// spring-boot-starter-web included',
      code: `@Component
public class LBROFilter implements Filter {
    private static final String API_KEY  = "${k}";
    private static final String BASE_URL = "${BASE}/api/v1/events";
    private final RestTemplate rest = new RestTemplate();

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {
        chain.doFilter(req, res);
        int status = ((HttpServletResponse) res).getStatus();
        if (status >= 400) {
            HttpHeaders headers = new HttpHeaders();
            headers.set("Authorization", "Bearer " + API_KEY);
            headers.setContentType(MediaType.APPLICATION_JSON);
            Map<String,Object> body = Map.of(
                "event_type", "suspicious_request",
                "severity",   status >= 500 ? "high" : "medium",
                "message",    "HTTP " + status
            );
            rest.postForEntity(BASE_URL, new HttpEntity<>(body, headers), String.class);
        }
    }
}`,
    },
    aspnet: {
      install: '// Uses System.Net.Http (built-in)',
      code: `// Middleware/LBROMiddleware.cs
public class LBROMiddleware {
    const string ApiKey  = "${k}";
    const string BaseUrl = "${BASE}/api/v1/events";
    readonly RequestDelegate _next;
    static readonly HttpClient _http = new();

    public LBROMiddleware(RequestDelegate next) { _next = next; }

    public async Task InvokeAsync(HttpContext context) {
        await _next(context);
        if (context.Response.StatusCode >= 400) {
            _http.DefaultRequestHeaders.Authorization =
                new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", ApiKey);
            await _http.PostAsJsonAsync(BaseUrl, new {
                event_type = "suspicious_request",
                severity   = context.Response.StatusCode >= 500 ? "high" : "medium",
                message    = $"HTTP {context.Response.StatusCode} on {context.Request.Path}",
                source_ip  = context.Connection.RemoteIpAddress?.ToString(),
            });
        }
    }
}
// Program.cs: app.UseMiddleware<LBROMiddleware>();`,
    },
    php: {
      install: '# Uses built-in cURL — no extra packages needed',
      code: `<?php
function lbro_send_event($type, $severity, $message, $source_ip = null) {
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
            "source_ip"  => $source_ip,
        ]),
    ]);
    $response = curl_exec($ch);
    curl_close($ch);
    return json_decode($response, true);
}

// Example: report auth failure
lbro_send_event("auth_failure", "medium", "Login failed", $_SERVER["REMOTE_ADDR"]);`,
    },
    laravel: {
      install: '# Built-in HTTP client (Laravel 7+)',
      code: `<?php
// app/Http/Middleware/LBROMiddleware.php
namespace App\\Http\\Middleware;

use Closure;
use Illuminate\\Support\\Facades\\Http;

class LBROMiddleware {
    const API_KEY  = "${k}";
    const BASE_URL = "${BASE}";

    public function handle($request, Closure $next) {
        $response = $next($request);
        if ($response->status() >= 400) {
            Http::withToken(self::API_KEY)->post(self::BASE_URL . "/api/v1/events", [
                "event_type" => "suspicious_request",
                "severity"   => $response->status() >= 500 ? "high" : "medium",
                "message"    => "HTTP {$response->status()} on {$request->path()}",
                "source_ip"  => $request->ip(),
            ]);
        }
        return $response;
    }
}
// Register in app/Http/Kernel.php: \\App\\Http\\Middleware\\LBROMiddleware::class`,
    },
    apache: {
      install: '# Download and configure lbro-agent',
      code: `# /etc/lbro-agent/config.yaml
api_key:  "${k}"
base_url: "${BASE}"

log_files:
  - path:   /var/log/apache2/access.log
    format: apache
  - path:   /var/log/apache2/error.log
    format: apache

# Start the agent
# lbro-agent --config /etc/lbro-agent/config.yaml`,
    },
    windows: {
      install: '# Download lbro-agent-windows.exe from releases',
      code: `# PowerShell: install as Windows Service
$config = @{
    api_key  = "${k}"
    base_url = "${BASE}"
    sources  = @(
        @{ type = "windows_event_log"; channels = @("Security","System","Application") }
    )
}
$config | ConvertTo-Json | Set-Content C:\\ProgramData\\lbro-agent\\config.json
New-Service -Name "LBROAgent" -BinaryPathName "C:\\lbro-agent.exe --service" -StartupType Automatic
Start-Service LBROAgent`,
    },
    syslog: {
      install: '# Redirect rsyslog to lbro-agent',
      code: `# /etc/rsyslog.d/lbro.conf
# Forward all logs to lbro-agent running locally
*.* @127.0.0.1:5141

# /etc/lbro-agent/config.yaml
api_key:  "${k}"
base_url: "${BASE}"

syslog_listener:
  address: "0.0.0.0:5141"
  protocol: udp

# systemctl enable --now lbro-agent`,
    },
  }

  return snippets[integrationId] ?? { install: '', code: '# Select an integration above' }
}

// ── curl examples ──────────────────────────────────────────────────────────
const CURL_EXAMPLES = [
  {
    label:   'SQL Injection',
    type:    'sql_injection',
    sev:     'critical',
    message: "SQLi probe on /api/users?id=1' OR '1'='1",
    ip:      '185.220.101.42',
  },
  {
    label:   'Brute Force',
    type:    'brute_force',
    sev:     'high',
    message: '429 failed login attempts in 60 seconds',
    ip:      '94.102.49.190',
  },
  {
    label:   'Port Scan',
    type:    'port_scan',
    sev:     'medium',
    message: 'SYN scan across ports 1-65535 from external IP',
    ip:      '203.0.113.55',
  },
  {
    label:   'XSS',
    type:    'xss',
    sev:     'high',
    message: 'Reflected XSS in search parameter',
    ip:      '198.51.100.23',
  },
  {
    label:   'Auth Failure',
    type:    'auth_failure',
    sev:     'medium',
    message: 'Login failed: wrong password (attempt 12)',
    ip:      '104.21.14.101',
  },
  {
    label:   'Malware',
    type:    'system_log',
    sev:     'critical',
    message: 'Malware signature detected: Trojan.GenericKD.48752',
    ip:      '10.0.0.15',
  },
  {
    label:   'Suspicious Login',
    type:    'auth_failure',
    sev:     'high',
    message: 'Login from new country: Nigeria (usual: US)',
    ip:      '197.210.84.195',
  },
]

// ── CopyButton ─────────────────────────────────────────────────────────────
function CopyButton({ text, small }: { text: string; small?: boolean }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1 transition-colors"
      style={{ color: copied ? '#22c55e' : '#666', fontSize: small ? 11 : 12 }}
    >
      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

// ── CodeBlock ──────────────────────────────────────────────────────────────
function CodeBlock({ code, language }: { code: string; language?: string }) {
  return (
    <div className="relative rounded-lg overflow-hidden" style={{ background: '#0a0a0a', border: '1px solid #1e1e1e' }}>
      <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: '#1e1e1e', background: '#0f0f0f' }}>
        <span className="text-xs text-zinc-500">{language ?? 'bash'}</span>
        <CopyButton text={code} small />
      </div>
      <pre className="p-4 text-xs leading-relaxed overflow-x-auto" style={{ color: '#d4d4d4', fontFamily: 'monospace', margin: 0 }}>
        <code>{code}</code>
      </pre>
    </div>
  )
}

// ── Step indicator ─────────────────────────────────────────────────────────
function StepDot({ n, active, done }: { n: number; active: boolean; done: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-all"
        style={{
          background: done ? '#22c55e' : active ? ORANGE : '#1e1e1e',
          color:      done || active ? '#fff' : '#555',
          border:     '2px solid ' + (done ? '#22c55e' : active ? ORANGE : '#2a2a2a'),
        }}
      >
        {done ? <Check className="w-3.5 h-3.5" /> : n}
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────
export default function ProjectSetupWizardPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const [step, setStep]               = useState(1)
  const [selected, setSelected]       = useState<string>('python')
  const [keyCopied, setKeyCopied]     = useState(false)
  const [keyVisible, setKeyVisible]   = useState(false)
  const [curlIdx, setCurlIdx]         = useState(0)
  const [regenLoading, setRegenLoading] = useState(false)

  const { data: project, refetch } = useQuery({
    queryKey: ['project', projectId],
    queryFn:  () => projectsApi.get(projectId!),
    enabled:  !!projectId,
  })

  const copyKey = useCallback(() => {
    if (!project?.api_key) return
    navigator.clipboard.writeText(project.api_key).then(() => {
      setKeyCopied(true)
      setTimeout(() => setKeyCopied(false), 2000)
    })
  }, [project?.api_key])

  const downloadKey = useCallback(() => {
    if (!project) return
    const content = [
      'LBRO API Key',
      '===========',
      '',
      'Project:     ' + project.name,
      'Project ID:  ' + project.id,
      'Environment: ' + project.environment,
      'API Key:     ' + project.api_key,
      '',
      'Keep this file secure. Do not commit to version control.',
      '',
      'Usage:',
      '  Authorization: Bearer ' + project.api_key,
    ].join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'lbro-' + project.name.toLowerCase().replace(/\s+/g, '-') + '-api-key.txt'
    a.click()
  }, [project])

  const regenerateKey = useCallback(async () => {
    if (!projectId) return
    setRegenLoading(true)
    try {
      await projectsApi.regenerateKey(projectId)
      await refetch()
    } finally {
      setRegenLoading(false)
    }
  }, [projectId, refetch])

  if (!project) {
    return (
      <div className="flex items-center justify-center min-h-screen" style={{ background: BG }}>
        <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
      </div>
    )
  }

  const envColor = ENV_COLOR[project.environment as ProjectEnvironment] ?? '#666'
  const apiKey   = project.api_key ?? ''
  const maskedKey = apiKey ? apiKey.slice(0, 10) + '••••••••••••••••••••' : ''
  const snippet  = getSnippet(selected, apiKey)
  const curl     = CURL_EXAMPLES[curlIdx]
  const curlCmd  = `curl -X POST ${window.location.origin}/api/v1/events \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "event_type": "${curl.type}",
    "severity":   "${curl.sev}",
    "message":    "${curl.message}",
    "source_ip":  "${curl.ip}"
  }'`

  const STEPS = ['Project created', 'Choose integration', 'Send first event']

  return (
    <div className="min-h-screen" style={{ background: BG }}>
      <div className="max-w-3xl mx-auto px-6 py-10">

        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs px-2 py-0.5 rounded capitalize" style={{ color: envColor, background: envColor + '18' }}>
              {project.environment}
            </span>
          </div>
          <h1 className="font-display text-3xl text-white">{project.name}</h1>
          <p className="text-sm text-zinc-500 mt-1">Project setup — connect your first application</p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-0 mb-10">
          {STEPS.map((label, i) => (
            <div key={i} className="flex items-center">
              <button
                onClick={() => i + 1 < step && setStep(i + 1)}
                className="flex items-center gap-2 group"
                style={{ cursor: i + 1 < step ? 'pointer' : 'default' }}
              >
                <StepDot n={i + 1} active={step === i + 1} done={step > i + 1} />
                <span className="text-xs hidden sm:block" style={{ color: step === i + 1 ? '#fff' : '#555' }}>
                  {label}
                </span>
              </button>
              {i < STEPS.length - 1 && (
                <div className="mx-3 h-px w-12 sm:w-20" style={{ background: step > i + 1 ? '#22c55e40' : '#1e1e1e' }} />
              )}
            </div>
          ))}
        </div>

        {/* ── Step 1: Project details + API key ── */}
        {step === 1 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <div className="rounded-xl border p-6" style={{ background: CARD, borderColor: '#1e1e1e' }}>
              <div className="flex items-center gap-2 mb-6">
                <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: '#22c55e22' }}>
                  <Check className="w-4 h-4 text-green-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">Project created successfully</p>
                  <p className="text-xs text-zinc-500">Your API key is ready to use</p>
                </div>
              </div>

              {/* Project meta */}
              <div className="grid grid-cols-2 gap-3 mb-6">
                {[
                  { label: 'Project Name',  value: project.name },
                  { label: 'Environment',   value: project.environment },
                  { label: 'Project ID',    value: project.id, mono: true },
                  { label: 'Status',        value: project.status },
                ].map(({ label, value, mono }) => (
                  <div key={label} className="rounded-lg p-3" style={{ background: '#0a0a0a', border: '1px solid #1e1e1e' }}>
                    <p className="text-xs text-zinc-500 mb-1">{label}</p>
                    <p className={`text-sm text-white truncate ${mono ? 'font-mono text-xs' : ''}`}>{value}</p>
                  </div>
                ))}
              </div>

              {/* API key */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Key className="w-3.5 h-3.5 text-zinc-400" />
                    <span className="text-xs text-zinc-400 font-medium">API Key</span>
                  </div>
                  <button
                    onClick={() => setKeyVisible(v => !v)}
                    className="text-xs text-zinc-500 hover:text-zinc-300 flex items-center gap-1 transition-colors"
                  >
                    {keyVisible ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    {keyVisible ? 'Hide' : 'Reveal'}
                  </button>
                </div>
                <div className="rounded-lg p-3 flex items-center justify-between gap-3" style={{ background: '#0a0a0a', border: '1px solid #1e1e1e' }}>
                  <code className="text-sm text-green-400 font-mono truncate">
                    {keyVisible ? apiKey : maskedKey}
                  </code>
                </div>

                <div className="flex gap-2 mt-3">
                  <button
                    onClick={copyKey}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded text-xs font-medium transition-all"
                    style={{ background: keyCopied ? '#22c55e22' : '#1e1e1e', color: keyCopied ? '#22c55e' : '#ccc', border: '1px solid ' + (keyCopied ? '#22c55e44' : '#2a2a2a') }}
                  >
                    {keyCopied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {keyCopied ? 'Copied!' : 'Copy API Key'}
                  </button>
                  <button
                    onClick={downloadKey}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded text-xs font-medium transition-all"
                    style={{ background: '#1e1e1e', color: '#ccc', border: '1px solid #2a2a2a' }}
                  >
                    <Download className="w-3 h-3" /> Download
                  </button>
                  <button
                    onClick={regenerateKey}
                    disabled={regenLoading}
                    className="flex items-center gap-1.5 px-3 py-2 rounded text-xs transition-all"
                    style={{ background: '#1e1e1e', color: '#666', border: '1px solid #2a2a2a' }}
                    title="Regenerate API key"
                  >
                    <RefreshCw className={`w-3 h-3 ${regenLoading ? 'animate-spin' : ''}`} />
                  </button>
                </div>
                <p className="text-xs text-zinc-600 mt-2">Keep this key secret. It grants access to this project's event ingestion endpoint.</p>
              </div>
            </div>

            <button
              onClick={() => setStep(2)}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-lg font-medium text-sm transition-all hover:opacity-90"
              style={{ background: ORANGE, color: '#fff' }}
            >
              Choose integration <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* ── Step 2: Choose integration ── */}
        {step === 2 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            <p className="text-sm text-zinc-400">Select the technology you want to connect to LBRO.</p>
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
              {INTEGRATIONS.map(int => (
                <button
                  key={int.id}
                  onClick={() => setSelected(int.id)}
                  className="rounded-xl border p-3 text-left transition-all"
                  style={{
                    background:   selected === int.id ? int.color + '15' : CARD,
                    borderColor:  selected === int.id ? int.color : BORDER,
                  }}
                >
                  <div className="text-xl mb-1.5">{int.icon}</div>
                  <p className="text-xs font-medium text-white truncate">{int.name}</p>
                  <p className="text-xs mt-0.5" style={{ color: selected === int.id ? int.color : '#555' }}>{int.tag}</p>
                </button>
              ))}
            </div>

            <div className="flex gap-3">
              <button onClick={() => setStep(1)} className="flex-1 py-3 rounded-lg text-sm transition-all" style={{ background: '#1e1e1e', color: '#888' }}>
                Back
              </button>
              <button
                onClick={() => setStep(3)}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg font-medium text-sm transition-all hover:opacity-90"
                style={{ background: ORANGE, color: '#fff' }}
              >
                View code snippet <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ── Step 3: Code snippets + curl ── */}
        {step === 3 && (
          <div className="space-y-6 animate-in fade-in duration-200">
            {/* Selected integration header */}
            <div className="flex items-center gap-3">
              <span className="text-2xl">{INTEGRATIONS.find(i => i.id === selected)?.icon}</span>
              <div>
                <p className="font-medium text-white">{INTEGRATIONS.find(i => i.id === selected)?.name} integration</p>
                <p className="text-xs text-zinc-500">Your API key is pre-filled below</p>
              </div>
              <button
                onClick={() => setStep(2)}
                className="ml-auto text-xs px-3 py-1.5 rounded transition-all"
                style={{ background: '#1e1e1e', color: '#888' }}
              >
                Change
              </button>
            </div>

            {snippet.install && (
              <div>
                <p className="text-xs text-zinc-500 mb-2 font-medium">INSTALL</p>
                <CodeBlock code={snippet.install} language="bash" />
              </div>
            )}
            <div>
              <p className="text-xs text-zinc-500 mb-2 font-medium">CODE</p>
              <CodeBlock code={snippet.code} language={selected === 'nodejs' || selected === 'express' ? 'javascript' : selected === 'java' || selected === 'spring' || selected === 'aspnet' ? 'java' : selected === 'go' ? 'go' : 'python'} />
            </div>

            {/* cURL examples */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-zinc-500 font-medium">CURL EXAMPLES</p>
                <div className="flex gap-1">
                  {CURL_EXAMPLES.map((ex, i) => (
                    <button
                      key={i}
                      onClick={() => setCurlIdx(i)}
                      className="text-xs px-2 py-0.5 rounded transition-all"
                      style={{
                        background:  curlIdx === i ? ORANGE + '22' : '#1a1a1a',
                        color:       curlIdx === i ? ORANGE : '#555',
                        border:      '1px solid ' + (curlIdx === i ? ORANGE + '44' : '#222'),
                      }}
                    >
                      {ex.label}
                    </button>
                  ))}
                </div>
              </div>
              <CodeBlock code={curlCmd} language="bash" />
            </div>

            {/* CTA */}
            <div className="rounded-xl border p-5" style={{ background: '#0a160a', borderColor: '#1e3a1e' }}>
              <div className="flex items-start gap-3">
                <Zap className="w-4 h-4 text-green-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-white mb-1">Ready to see incidents appear live?</p>
                  <p className="text-xs text-zinc-400 mb-3">Send the curl command above, then watch the live event stream.</p>
                  <div className="flex gap-2">
                    <Link
                      to={`/projects/${projectId}/events`}
                      className="flex items-center gap-1.5 px-4 py-2 rounded text-xs font-medium transition-all hover:opacity-90"
                      style={{ background: '#22c55e', color: '#fff' }}
                    >
                      <Terminal className="w-3 h-3" /> Live event stream
                    </Link>
                    <Link
                      to="/dashboard"
                      className="flex items-center gap-1.5 px-4 py-2 rounded text-xs font-medium transition-all"
                      style={{ background: '#1e1e1e', color: '#ccc', border: '1px solid #2a2a2a' }}
                    >
                      View dashboard <ChevronRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
