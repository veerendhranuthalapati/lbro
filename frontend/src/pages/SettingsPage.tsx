import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Key, Bell, Users, Shield, Eye, EyeOff, Copy, CheckCircle, Lock, ChevronRight, Info } from 'lucide-react'
import { toast } from '@/components/ui/Toast'
import { useAuthStore, getAccessToken } from '@/store/authStore'
import { useUsers } from '@/hooks/useApi'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        {icon}
        <h3 style={{ fontSize: 12, fontWeight: 500, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{title}</h3>
      </div>
      {children}
    </div>
  )
}


function TeamSection() {
  const { data: usersData, isLoading } = useUsers()
  const users = usersData?.items ?? []

  return (
    <Section icon={<Users style={{ width: 14, height: 14, color: ORANGE }} />} title="Team">
      {isLoading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[1,2,3].map(i => <div key={i} style={{ height: 40, background: PARCH, borderRadius: 4 }} />)}
        </div>
      ) : users.length === 0 ? (
        <p style={{ fontSize: 11, color: GRAY }}>No users found</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {users.map((m, idx, arr) => (
            <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: idx < arr.length - 1 ? '1px solid ' + BORDER : 'none' }}>
              <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'rgba(229,78,27,0.1)', border: '1px solid rgba(229,78,27,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: ORANGE, flexShrink: 0 }}>
                {(m.full_name || m.email)[0].toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12, color: BLACK, fontWeight: 500 }}>{m.full_name ?? m.email}</div>
                <div style={{ fontSize: 10, color: GRAY, marginTop: 1 }}>{m.email}</div>
              </div>
              <span style={{ fontSize: 10, padding: '2px 8px', border: '1px solid ' + BORDER, borderRadius: 2, color: GRAY, fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                {m.role}
              </span>
            </div>
          ))}
        </div>
      )}
    </Section>
  )
}

const DEFAULT_PREFS = [
  { label: 'Critical incident alerts', desc: 'Immediate notification for CRITICAL severity', on: true },
  { label: 'High severity alerts', desc: 'Notification for HIGH severity incidents', on: true },
  { label: 'Compliance deadline warnings', desc: 'Alert 24h and 6h before regulatory deadline', on: true },
  { label: 'New evidence uploaded', desc: 'Alert when files are attached to an incident', on: false },
  { label: 'Background service alerts', desc: 'Alert when a background job stops working', on: true },
]

export default function SettingsPage() {
  const navigate = useNavigate()
  // Subscribe to auth state changes so we re-render on login/logout
  const isAuthenticated = useAuthStore(s => s.isAuthenticated)
  const currentUser = useAuthStore(s => s.user)
  // getAccessToken() reads module-level memory (not Zustand state) -- safe after the persist-getter fix
  const accessToken = isAuthenticated ? getAccessToken() : null
  const [showKey, setShowKey] = useState(false)
  const [copied, setCopied] = useState(false)
  const [prefs, setPrefs] = useState(DEFAULT_PREFS)

  const togglePref = (idx: number) =>
    setPrefs(prev => prev.map((p, i) => i === idx ? { ...p, on: !p.on } : p))

  const copyKey = () => {
    if (accessToken) {
      navigator.clipboard.writeText(accessToken)
      setCopied(true)
      toast.success('Session token copied to clipboard')
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 700 }}>
      <div>
        <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>Settings</h2>
        <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>Account, notifications, team, and activity log preferences</p>
      </div>

      {/* Session Token */}
      <Section icon={<Key style={{ width: 14, height: 14, color: ORANGE }} />} title="Session Token">
        <div>
          <label style={{ display: 'block', fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>Current JWT (Bearer)</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ flex: 1, background: PARCH, border: '1px solid ' + BORDER, borderRadius: 4, padding: '8px 12px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: BLACK, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {showKey
                ? (accessToken ?? '--')
                : (accessToken ? '•'.repeat(24) + accessToken.slice(-8) : '--')}
            </div>
            <button onClick={() => setShowKey(v => !v)} style={{ padding: 8, border: '1px solid ' + BORDER, borderRadius: 4, background: 'transparent', cursor: 'pointer', color: GRAY, display: 'flex' }}>
              {showKey ? <EyeOff style={{ width: 14, height: 14 }} /> : <Eye style={{ width: 14, height: 14 }} />}
            </button>
            <button onClick={copyKey} style={{ padding: 8, border: '1px solid ' + BORDER, borderRadius: 4, background: 'transparent', cursor: 'pointer', color: copied ? '#3a7a50' : GRAY, display: 'flex' }}>
              {copied ? <CheckCircle style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
            </button>
          </div>
          <p style={{ fontSize: 11, color: GRAY, marginTop: 8 }}>Short-lived JWT -- do not share. Session expires automatically and clears on tab close.</p>
        </div>
      </Section>

      {/* Notifications */}
      <Section icon={<Bell style={{ width: 14, height: 14, color: ORANGE }} />} title="Notification Preferences">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {prefs.map((pref, idx, arr) => (
            <div key={pref.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: idx < arr.length - 1 ? '1px solid ' + BORDER : 'none' }}>
              <div>
                <div style={{ fontSize: 12, color: BLACK, fontWeight: 500 }}>{pref.label}</div>
                <div style={{ fontSize: 10, color: GRAY, marginTop: 2 }}>{pref.desc}</div>
              </div>
              <button
                onClick={() => togglePref(idx)}
                aria-checked={pref.on}
                role="switch"
                aria-label={pref.label}
                style={{ width: 36, height: 20, borderRadius: 10, background: pref.on ? 'rgba(229,78,27,0.15)' : PARCH, border: '1px solid ' + (pref.on ? 'rgba(229,78,27,0.4)' : BORDER), display: 'flex', alignItems: 'center', cursor: 'pointer', position: 'relative', flexShrink: 0, padding: 0 }}
              >
                <span style={{ width: 14, height: 14, borderRadius: '50%', background: pref.on ? ORANGE : GRAY, position: 'absolute', left: pref.on ? 18 : 2, transition: 'left 0.15s' }} />
              </button>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 10, color: GRAY, marginTop: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
          <Info style={{ width: 11, height: 11, flexShrink: 0 }} />
          Preferences are saved for this session. Persistent notification settings require a backend profile endpoint.
        </p>
      </Section>

      {/* IAM */}
      <Section icon={<Shield style={{ width: 14, height: 14, color: ORANGE }} />} title="Infrastructure Configuration">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {[
            ['ECS Task Role', import.meta.env.VITE_AWS_TASK_ROLE ?? 'Not configured'],
            ['S3 Evidence Bucket', import.meta.env.VITE_S3_BUCKET ?? 'Not configured'],
            ['SQS Queues', import.meta.env.VITE_SQS_QUEUES ?? 'Not configured'],
            ['Secrets Manager', import.meta.env.VITE_SECRETS_PATH ?? 'Not configured'],
            ['Region', import.meta.env.VITE_AWS_REGION ?? 'Not configured'],
          ].map(([k, v]) => (
            <div key={k} style={{ display: 'flex', gap: 12, fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }}>
              <span style={{ color: GRAY, width: 150, flexShrink: 0 }}>{k}</span>
              <span style={{ color: v === 'Not configured' ? GRAY : BLACK, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontStyle: v === 'Not configured' ? 'italic' : 'normal' }}>{v}</span>
            </div>
          ))}
        </div>
        <p style={{ fontSize: 10, color: GRAY, marginTop: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
          <Info style={{ width: 11, height: 11, flexShrink: 0 }} />
          Set VITE_AWS_TASK_ROLE, VITE_S3_BUCKET, VITE_SQS_QUEUES, VITE_SECRETS_PATH, VITE_AWS_REGION in your .env file.
        </p>
        </Section>

      
      {/* Team -- live from /api/v1/users */}
      <TeamSection />

      {/* Privacy & Data */}
      <div
        onClick={() => navigate('/privacy')}
        style={{
          background: CREAM,
          border: `1px solid ${BORDER}`,
          borderRadius: 4,
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          cursor: 'pointer',
          transition: 'border-color 0.15s',
        }}
        onMouseEnter={e => (e.currentTarget.style.borderColor = ORANGE)}
        onMouseLeave={e => (e.currentTarget.style.borderColor = BORDER)}
        role="link"
        aria-label="Privacy and Data Handling"
      >
        <Lock style={{ width: 14, height: 14, color: ORANGE, flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>Privacy & Data Handling</div>
          <div style={{ fontSize: 11, color: GRAY, marginTop: 2 }}>
            How your data is stored, redacted, and deleted -- and for how long.
          </div>
        </div>
        <ChevronRight style={{ width: 14, height: 14, color: GRAY }} />
      </div>
    </div>
  )
}