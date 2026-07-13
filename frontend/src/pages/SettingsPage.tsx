import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Sparkles, Loader2, Check, AlertCircle, User } from 'lucide-react'
import { authApi, demoApi } from '@/api/client'
import { useAuthStore } from '@/store/authStore'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const BG     = '#f0ebe2'

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 24, marginBottom: 16 }}>
      <div style={{ marginBottom: 20, paddingBottom: 16, borderBottom: `1px solid ${BORDER}` }}>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: BLACK, margin: 0 }}>{title}</h2>
        {description && <p style={{ fontSize: 11, color: GRAY, margin: '4px 0 0' }}>{description}</p>}
      </div>
      {children}
    </section>
  )
}

function Toggle({ enabled, onChange }: { enabled: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      onClick={() => onChange(!enabled)}
      style={{
        width: 40, height: 22, borderRadius: 11, border: 'none', cursor: 'pointer',
        background: enabled ? ORANGE : BORDER,
        position: 'relative', transition: 'background 0.2s', flexShrink: 0,
      }}
    >
      <span style={{
        position: 'absolute', top: 3, left: enabled ? 20 : 3,
        width: 16, height: 16, borderRadius: '50%', background: '#fff',
        transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
      }} />
    </button>
  )
}

function Label({ htmlFor, children }: { htmlFor?: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
      {children}
    </label>
  )
}

function Input({ id, type = 'text', value, onChange, placeholder, autoComplete }: {
  id?: string; type?: string; value: string; onChange: (v: string) => void
  placeholder?: string; autoComplete?: string
}) {
  return (
    <input
      id={id} type={type} value={value} placeholder={placeholder}
      autoComplete={autoComplete}
      onChange={e => onChange(e.target.value)}
      style={{ width: '100%', padding: '9px 12px', fontSize: 12, boxSizing: 'border-box', background: BG, border: `1px solid ${BORDER}`, borderRadius: 4, color: BLACK, outline: 'none' }}
    />
  )
}

function ProfileSection() {
  const { user, setUser } = useAuthStore()
  const [fullName,   setFullName]   = useState(user?.name ?? '')
  const [email,      setEmail]      = useState(user?.email ?? '')
  const [currentPw,  setCurrentPw]  = useState('')
  const [newPw,      setNewPw]      = useState('')
  const [saved,      setSaved]      = useState(false)
  const [error,      setError]      = useState('')

  const mutation = useMutation({
    mutationFn: () => authApi.updateProfile({
      full_name: fullName.trim() || undefined,
      email: email.trim() || undefined,
      current_password: currentPw || undefined,
      new_password: newPw || undefined,
    }),
    onSuccess: updatedUser => {
      setSaved(true)
      setCurrentPw('')
      setNewPw('')
      setError('')
      setTimeout(() => setSaved(false), 2500)
      if (user) {
        setUser({
          ...user,
          name:  updatedUser.full_name ?? user.name,
          email: updatedUser.email     ?? user.email,
        })
      }
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? 'Could not save changes.')
    },
  })

  const initials = (user?.name ?? 'U').split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)

  return (
    <Section title="Profile" description="Update your name, email and password.">
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
        <div style={{ width: 52, height: 52, borderRadius: '50%', background: ORANGE, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 700, color: '#fff', flexShrink: 0 }}>
          {initials}
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: BLACK }}>{user?.name}</div>
          <div style={{ fontSize: 11, color: GRAY }}>{user?.email}</div>
          <div style={{ fontSize: 10, color: GRAY, marginTop: 2, textTransform: 'capitalize' }}>{user?.role}</div>
        </div>
      </div>

      {error && (
        <div style={{ display: 'flex', gap: 8, padding: '9px 12px', background: 'rgba(229,78,27,0.08)', border: `1px solid rgba(229,78,27,0.3)`, borderRadius: 4, fontSize: 11, color: ORANGE, marginBottom: 16 }}>
          <AlertCircle style={{ width: 13, height: 13, flexShrink: 0, marginTop: 1 }} /> {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
        <div>
          <Label htmlFor="profile-name">Full name</Label>
          <Input id="profile-name" value={fullName} onChange={setFullName} placeholder="Jane Smith" autoComplete="name" />
        </div>
        <div>
          <Label htmlFor="profile-email">Email</Label>
          <Input id="profile-email" type="email" value={email} onChange={setEmail} placeholder="you@company.com" autoComplete="email" />
        </div>
      </div>

      <div style={{ background: BG, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 14, marginBottom: 16 }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>Change password</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div>
            <Label htmlFor="current-pw">Current password</Label>
            <Input id="current-pw" type="password" value={currentPw} onChange={setCurrentPw} autoComplete="current-password" />
          </div>
          <div>
            <Label htmlFor="new-pw">New password</Label>
            <Input id="new-pw" type="password" value={newPw} onChange={setNewPw} autoComplete="new-password" />
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 18px', background: saved ? '#16a34a' : ORANGE, color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, fontWeight: 600, cursor: mutation.isPending ? 'not-allowed' : 'pointer', transition: 'background 0.2s' }}
        >
          {mutation.isPending
            ? <><Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} /> Saving…</>
            : saved
            ? <><Check style={{ width: 13, height: 13 }} /> Saved</>
            : <><Save style={{ width: 13, height: 13 }} /> Save changes</>
          }
        </button>
      </div>
    </Section>
  )
}

function DemoModeSection() {
  const qc = useQueryClient()
  const [enabled, setEnabled] = useState(false)
  const [generated, setGenerated] = useState(false)

  const mutation = useMutation({
    mutationFn: () => demoApi.generate(),
    onSuccess: () => {
      setGenerated(true)
      qc.invalidateQueries({ queryKey: ['incidents'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['compliance'] })
      setTimeout(() => setGenerated(false), 4000)
    },
  })

  return (
    <Section title="Demo Mode" description="Populate the platform with sample data to explore its features.">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: BLACK, marginBottom: 4 }}>Enable demo data</div>
          <div style={{ fontSize: 11, color: GRAY, lineHeight: 1.5 }}>
            Generates sample incidents, evidence, and compliance records so you can explore all features immediately.
          </div>
        </div>
        <Toggle enabled={enabled} onChange={setEnabled} />
      </div>

      {enabled && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${BORDER}` }}>
          {generated ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#16a34a' }}>
              <Check style={{ width: 14, height: 14 }} />
              Demo data generated — check the Dashboard and Incidents pages.
            </div>
          ) : (
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 16px', background: BLACK, color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, fontWeight: 600, cursor: mutation.isPending ? 'not-allowed' : 'pointer' }}
            >
              {mutation.isPending
                ? <><Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} /> Generating…</>
                : <><Sparkles style={{ width: 13, height: 13 }} /> Generate sample data</>
              }
            </button>
          )}
          {mutation.isError && (
            <div style={{ fontSize: 11, color: ORANGE, marginTop: 8, display: 'flex', gap: 6 }}>
              <AlertCircle style={{ width: 13, height: 13 }} /> Failed to generate demo data. Is the backend running?
            </div>
          )}
        </div>
      )}
    </Section>
  )
}

export default function SettingsPage() {
  return (
    <div style={{ maxWidth: 780, margin: '0 auto', padding: '32px 24px' }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <User style={{ width: 16, height: 16, color: ORANGE }} />
          <h1 style={{ fontSize: 18, fontWeight: 700, color: BLACK, margin: 0 }}>Settings</h1>
        </div>
        <p style={{ fontSize: 11, color: GRAY, margin: 0 }}>Manage your account and platform preferences.</p>
      </div>

      <ProfileSection />
      <DemoModeSection />
    </div>
  )
}
