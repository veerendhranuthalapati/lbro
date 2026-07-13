/**
 * WelcomePage — 5-step onboarding wizard shown after first registration.
 *
 * Step 1: Welcome to LBRO 👋
 * Step 2: Create Project
 * Step 3: Generate API Key
 * Step 4: Connect Your Application
 * Step 5: You're Ready 🎉
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ShieldCheck, ArrowRight, Copy, Check, Download, RefreshCw,
  Loader2, Globe, Box, Layers,
} from 'lucide-react'
import { projectsApi } from '@/api/client'
import { useProjectStore } from '@/store/projectStore'
import { useAuthStore } from '@/store/authStore'
import type { ProjectEnvironment } from '@/types'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BG     = '#0a0a0a'
const CARD   = '#111111'
const BORDER = '#222222'
const GRAY   = '#888888'
const GREEN  = '#22c55e'

const TOTAL_STEPS = 5

function StepIndicator({ current }: { current: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {Array.from({ length: TOTAL_STEPS }, (_, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: i < current ? 24 : 8,
            height: 8,
            borderRadius: 4,
            background: i < current ? ORANGE : i === current ? '#555' : '#333',
            transition: 'all 0.3s',
          }} />
        </div>
      ))}
    </div>
  )
}

// ── Step 1: Welcome ──────────────────────────────────────────────────────────
function StepWelcome({ onNext, user }: { onNext: () => void; user: string }) {
  return (
    <div style={{ textAlign: 'center', maxWidth: 480, margin: '0 auto' }}>
      <div style={{ fontSize: 56, marginBottom: 16 }}>👋</div>
      <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: '#fff', letterSpacing: '0.05em', lineHeight: 1, marginBottom: 16 }}>
        Welcome to LBRO
      </h1>
      <p style={{ fontSize: 16, color: GRAY, lineHeight: 1.7, marginBottom: 12 }}>
        Hi {user.split(' ')[0]}! LBRO monitors your applications, detects cyber attacks,
        stores forensic evidence, and explains incidents in plain English.
      </p>
      <p style={{ fontSize: 13, color: '#666', lineHeight: 1.7, marginBottom: 40 }}>
        Let's get you set up in under 2 minutes. We'll create a project, generate your API key,
        and show you how to connect your application.
      </p>
      <button onClick={onNext} style={{ display: 'inline-flex', alignItems: 'center', gap: 10, padding: '14px 32px', background: ORANGE, color: '#fff', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
        Get Started <ArrowRight style={{ width: 16, height: 16 }} />
      </button>
    </div>
  )
}

// ── Step 2: Create Project ───────────────────────────────────────────────────
const ENV_OPTIONS: { value: ProjectEnvironment; label: string; color: string }[] = [
  { value: 'production',  label: 'Production',  color: '#ef4444' },
  { value: 'staging',     label: 'Staging',     color: '#f59e0b' },
  { value: 'development', label: 'Development', color: '#22c55e' },
]

function StepCreateProject({ onNext }: { onNext: (project: { id: string; name: string; api_key: string }) => void }) {
  const qc = useQueryClient()
  const { setCurrentProject } = useProjectStore()
  const [name, setName] = useState('My First Project')
  const [env, setEnv] = useState<ProjectEnvironment>('production')
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: () => projectsApi.create({ name: name.trim(), environment: env }),
    onSuccess: (project) => {
      setCurrentProject(project)
      qc.invalidateQueries({ queryKey: ['projects'] })
      onNext({ id: project.id, name: project.name, api_key: project.api_key })
    },
    onError: () => setError('Could not create project. Please try again.'),
  })

  return (
    <div style={{ maxWidth: 480, margin: '0 auto' }}>
      <div style={{ marginBottom: 32 }}>
        <div style={{ width: 48, height: 48, borderRadius: 12, background: 'rgba(229,78,27,0.12)', border: '1px solid rgba(229,78,27,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
          <Layers style={{ width: 22, height: 22, color: ORANGE }} />
        </div>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: '#fff', marginBottom: 8 }}>Create your project</h2>
        <p style={{ fontSize: 13, color: GRAY }}>A project groups your incidents, evidence, and API keys. You can add more projects later.</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <label style={{ display: 'block', fontSize: 11, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>Project name</label>
          <input
            value={name}
            onChange={e => { setName(e.target.value); setError('') }}
            placeholder="My First Project"
            autoFocus
            style={{ width: '100%', padding: '12px 14px', background: '#1a1a1a', border: `1px solid ${error ? ORANGE : '#333'}`, borderRadius: 6, color: '#fff', fontSize: 14, outline: 'none', boxSizing: 'border-box' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: 11, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>Environment</label>
          <div style={{ display: 'flex', gap: 8 }}>
            {ENV_OPTIONS.map(o => (
              <button
                key={o.value}
                onClick={() => setEnv(o.value)}
                style={{
                  flex: 1, padding: '10px 0', borderRadius: 6, border: `1px solid ${env === o.value ? o.color : '#333'}`,
                  background: env === o.value ? o.color + '18' : '#1a1a1a',
                  color: env === o.value ? o.color : GRAY,
                  fontSize: 12, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>

        {error && <p style={{ fontSize: 12, color: ORANGE }}>{error}</p>}

        <button
          onClick={() => { if (name.trim()) mutation.mutate() }}
          disabled={mutation.isPending || !name.trim()}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '14px 0', background: mutation.isPending || !name.trim() ? '#333' : ORANGE, color: '#fff', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: mutation.isPending || !name.trim() ? 'not-allowed' : 'pointer', marginTop: 8 }}
        >
          {mutation.isPending ? <><Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} /> Creating…</> : <>Create Project <ArrowRight style={{ width: 16, height: 16 }} /></>}
        </button>
      </div>
    </div>
  )
}

// ── Step 3: API Key ──────────────────────────────────────────────────────────
function StepApiKey({ projectId, apiKey, projectName, onNext }: {
  projectId: string; apiKey: string; projectName: string; onNext: (apiKey: string) => void
}) {
  const { setCurrentProject } = useProjectStore()
  const [key, setKey] = useState(apiKey)
  const [copied, setCopied] = useState(false)

  const regenMutation = useMutation({
    mutationFn: () => projectsApi.regenerateKey(projectId),
    onSuccess: (updated) => {
      setKey(updated.api_key)
      setCurrentProject(updated)
    },
  })

  const copy = () => {
    navigator.clipboard.writeText(key)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const download = () => {
    const blob = new Blob([`LBRO Project API Key\nProject: ${projectName}\nKey: ${key}\n\nSend as header: X-Project-Key: ${key}`], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'lbro-api-key.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ maxWidth: 520, margin: '0 auto' }}>
      <div style={{ marginBottom: 32 }}>
        <div style={{ width: 48, height: 48, borderRadius: 12, background: 'rgba(229,78,27,0.12)', border: '1px solid rgba(229,78,27,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
          <ShieldCheck style={{ width: 22, height: 22, color: ORANGE }} />
        </div>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: '#fff', marginBottom: 8 }}>Your project API key</h2>
        <p style={{ fontSize: 13, color: GRAY }}>Send this key in the <code style={{ background: '#222', padding: '2px 6px', borderRadius: 3, fontSize: 11 }}>X-Project-Key</code> header when submitting incidents to LBRO.</p>
      </div>

      <div style={{ background: '#0f0f0f', border: `1px solid ${BORDER}`, borderRadius: 8, padding: 20, marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
          <code style={{ flex: 1, fontFamily: 'JetBrains Mono, monospace', fontSize: 12, color: '#a3e635', wordBreak: 'break-all', lineHeight: 1.6 }}>
            {key}
          </code>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={copy} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: copied ? 'rgba(34,197,94,0.12)' : '#1a1a1a', border: `1px solid ${copied ? '#22c55e' : '#333'}`, borderRadius: 5, color: copied ? GREEN : GRAY, fontSize: 12, cursor: 'pointer', transition: 'all 0.15s' }}>
            {copied ? <Check style={{ width: 13, height: 13 }} /> : <Copy style={{ width: 13, height: 13 }} />}
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button onClick={download} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: '#1a1a1a', border: '1px solid #333', borderRadius: 5, color: GRAY, fontSize: 12, cursor: 'pointer' }}>
            <Download style={{ width: 13, height: 13 }} /> Download
          </button>
          <button onClick={() => regenMutation.mutate()} disabled={regenMutation.isPending} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', background: '#1a1a1a', border: '1px solid #333', borderRadius: 5, color: GRAY, fontSize: 12, cursor: 'pointer', marginLeft: 'auto', opacity: regenMutation.isPending ? 0.5 : 1 }}>
            {regenMutation.isPending ? <Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} /> : <RefreshCw style={{ width: 13, height: 13 }} />} Regenerate
          </button>
        </div>
      </div>

      <p style={{ fontSize: 12, color: '#555', marginBottom: 28, lineHeight: 1.6 }}>
        Keep this key secret. It grants write access to your project's incidents. You can view it again at any time in Project Settings.
      </p>

      <button onClick={() => onNext(key)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%', padding: '14px 0', background: ORANGE, color: '#fff', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
        Next: Connect your app <ArrowRight style={{ width: 16, height: 16 }} />
      </button>
    </div>
  )
}

// ── Step 4: Connect App ──────────────────────────────────────────────────────
function StepConnectApp({ apiKey, onNext }: { apiKey: string; onNext: () => void }) {
  const [copied, setCopied] = useState(false)
  const snippet = `curl -X POST https://your-lbro-host/api/v1/ingest \\
  -H "Content-Type: application/json" \\
  -H "X-Project-Key: ${apiKey}" \\
  -d '{
    "source_ip": "1.2.3.4",
    "destination_ip": "10.0.0.5",
    "destination_port": 443,
    "protocol": "TCP",
    "event_type": "SUSPICIOUS_REQUEST",
    "raw_log": "GET /admin HTTP/1.1 - 401 Unauthorized"
  }'`

  const copy = () => {
    navigator.clipboard.writeText(snippet)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{ maxWidth: 580, margin: '0 auto' }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ width: 48, height: 48, borderRadius: 12, background: 'rgba(229,78,27,0.12)', border: '1px solid rgba(229,78,27,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
          <Globe style={{ width: 22, height: 22, color: ORANGE }} />
        </div>
        <h2 style={{ fontSize: 28, fontWeight: 700, color: '#fff', marginBottom: 8 }}>Connect your application</h2>
        <p style={{ fontSize: 13, color: GRAY }}>Send log events from your application to LBRO using a simple HTTP POST. LBRO will classify each event and create incidents automatically.</p>
      </div>

      {/* Code example */}
      <div style={{ position: 'relative', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 16px', background: '#161616', border: `1px solid ${BORDER}`, borderBottom: 'none', borderRadius: '6px 6px 0 0' }}>
          <span style={{ fontSize: 11, color: GRAY }}>curl</span>
          <button onClick={copy} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', background: copied ? 'rgba(34,197,94,0.1)' : '#222', border: `1px solid ${copied ? '#22c55e' : '#333'}`, borderRadius: 4, color: copied ? GREEN : GRAY, fontSize: 11, cursor: 'pointer' }}>
            {copied ? <Check style={{ width: 11, height: 11 }} /> : <Copy style={{ width: 11, height: 11 }} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <pre style={{ margin: 0, padding: '16px', background: '#0d0d0d', border: `1px solid ${BORDER}`, borderRadius: '0 0 6px 6px', fontSize: 11, color: '#a3e635', fontFamily: 'JetBrains Mono, monospace', overflowX: 'auto', lineHeight: 1.7 }}>
          {snippet}
        </pre>
      </div>

      {/* Coming soon integrations */}
      <div style={{ background: '#111', border: `1px solid ${BORDER}`, borderRadius: 8, padding: 20, marginBottom: 28 }}>
        <p style={{ fontSize: 11, color: '#555', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 16 }}>Integrations coming soon</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
          {[
            { icon: <Box style={{ width: 14, height: 14 }} />, label: 'One-line installer' },
            { icon: <Box style={{ width: 14, height: 14 }} />, label: 'Docker Agent' },
            { icon: <Globe style={{ width: 14, height: 14 }} />, label: 'Nginx integration' },
          ].map(i => (
            <div key={i.label} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', background: '#0d0d0d', border: '1px solid #1e1e1e', borderRadius: 6 }}>
              <span style={{ color: '#444' }}>{i.icon}</span>
              <span style={{ fontSize: 11, color: '#444' }}>{i.label}</span>
            </div>
          ))}
        </div>
      </div>

      <button onClick={onNext} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%', padding: '14px 0', background: ORANGE, color: '#fff', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
        Looks good, continue <ArrowRight style={{ width: 16, height: 16 }} />
      </button>
    </div>
  )
}

// ── Step 5: Ready ────────────────────────────────────────────────────────────
function StepReady({ onDone }: { onDone: () => void }) {
  return (
    <div style={{ textAlign: 'center', maxWidth: 480, margin: '0 auto' }}>
      <div style={{ fontSize: 64, marginBottom: 16 }}>🎉</div>
      <h2 style={{ fontSize: 36, fontWeight: 700, color: '#fff', marginBottom: 12 }}>You're all set!</h2>
      <p style={{ fontSize: 14, color: GRAY, lineHeight: 1.7, marginBottom: 12 }}>
        Your project is ready. As soon as your application sends its first log event, you'll see incidents appear on the dashboard.
      </p>
      <p style={{ fontSize: 13, color: '#555', lineHeight: 1.7, marginBottom: 40 }}>
        Need some data to explore the UI right now? Click "Go to Dashboard" and use the <strong style={{ color: '#888' }}>Generate Demo Data</strong> button.
      </p>
      <button onClick={onDone} style={{ display: 'inline-flex', alignItems: 'center', gap: 10, padding: '14px 36px', background: ORANGE, color: '#fff', border: 'none', borderRadius: 6, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}>
        Go to Dashboard <ArrowRight style={{ width: 16, height: 16 }} />
      </button>
    </div>
  )
}

// ── Main wizard ──────────────────────────────────────────────────────────────
export default function WelcomePage() {
  const navigate = useNavigate()
  const user = useAuthStore(s => s.user)
  const [step, setStep] = useState(0)
  const [project, setProject] = useState<{ id: string; name: string; api_key: string } | null>(null)
  const [apiKey, setApiKey] = useState('')

  const handleProjectCreated = (p: { id: string; name: string; api_key: string }) => {
    setProject(p)
    setApiKey(p.api_key)
    setStep(2)
  }

  const handleApiKeyNext = (key: string) => {
    setApiKey(key)
    setStep(3)
  }

  return (
    <div style={{ minHeight: '100vh', background: BG, display: 'flex', flexDirection: 'column' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 32px', borderBottom: `1px solid ${BORDER}` }}>
        <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 28, color: '#fff', letterSpacing: '0.05em' }}>
          LB<span style={{ color: ORANGE }}>R</span>O
        </div>
        <StepIndicator current={step} />
        <button
          onClick={() => navigate('/dashboard', { replace: true })}
          style={{ fontSize: 12, color: '#555', background: 'none', border: 'none', cursor: 'pointer', padding: '6px 12px', borderRadius: 4 }}
        >
          Skip setup
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 24px' }}>
        <div style={{ width: '100%', maxWidth: 640 }}>
          {step === 0 && (
            <StepWelcome onNext={() => setStep(1)} user={user?.name ?? user?.email ?? 'there'} />
          )}
          {step === 1 && (
            <StepCreateProject onNext={handleProjectCreated} />
          )}
          {step === 2 && project && (
            <StepApiKey
              projectId={project.id}
              apiKey={project.api_key}
              projectName={project.name}
              onNext={handleApiKeyNext}
            />
          )}
          {step === 3 && (
            <StepConnectApp apiKey={apiKey} onNext={() => setStep(4)} />
          )}
          {step === 4 && (
            <StepReady onDone={() => navigate('/dashboard', { replace: true })} />
          )}
        </div>
      </div>
    </div>
  )
}
