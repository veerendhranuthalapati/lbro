import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ShieldCheck, AlertCircle, Loader2, Eye, EyeOff } from 'lucide-react'
import { authApi } from '@/api/client'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const BG     = '#f0ebe2'

type Field = { value: string; error: string }
const field = (v = ''): Field => ({ value: v, error: '' })

function Input({
  id, label, type = 'text', f, onChange, placeholder, autoComplete, mono,
}: {
  id: string; label: string; type?: string; f: Field
  onChange: (v: string) => void; placeholder?: string; autoComplete?: string; mono?: boolean
}) {
  const [focused, setFocused] = useState(false)
  return (
    <div>
      <label htmlFor={id} style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
        {label}
      </label>
      <input
        id={id} type={type} value={f.value} placeholder={placeholder}
        autoComplete={autoComplete} spellCheck={false}
        onChange={e => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        aria-invalid={!!f.error}
        style={{
          width: '100%', padding: '10px 12px', fontSize: 12, boxSizing: 'border-box',
          fontFamily: mono ? 'JetBrains Mono, monospace' : 'inherit',
          background: BG, border: `1px solid ${f.error ? ORANGE : focused ? ORANGE : BORDER}`,
          borderRadius: 4, color: BLACK, outline: 'none',
        }}
      />
      {f.error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: ORANGE, marginTop: 4 }}>
          <AlertCircle style={{ width: 12, height: 12 }} /> {f.error}
        </div>
      )}
    </div>
  )
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const [email,    setEmail]    = useState(field())
  const [username, setUsername] = useState(field())
  const [fullName, setFullName] = useState(field())
  const [password, setPassword] = useState(field())
  const [confirm,  setConfirm]  = useState(field())
  const [showPw,   setShowPw]   = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [apiError, setApiError] = useState('')
  const [success,  setSuccess]  = useState(false)

  function validate() {
    let ok = true
    const set = (setter: (f: Field) => void, msg: string) => { setter({ value: '', error: msg }); ok = false }

    if (!email.value.includes('@'))        { set(f => setEmail({ ...email, error: 'Valid email required' }), ''); ok = false }
    if (username.value.length < 3)         { setUsername(f => ({ ...f, error: 'Min 3 characters' })); ok = false }
    if (!fullName.value.trim())            { setFullName(f => ({ ...f, error: 'Required' })); ok = false }
    if (password.value.length < 8)        { setPassword(f => ({ ...f, error: 'Min 8 characters' })); ok = false }
    if (password.value !== confirm.value) { setConfirm(f => ({ ...f, error: 'Passwords do not match' })); ok = false }
    return ok
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setApiError('')
    if (!validate()) return

    setLoading(true)
    try {
      await authApi.register({
        email: email.value.trim(),
        username: username.value.trim(),
        full_name: fullName.value.trim(),
        password: password.value,
      })
      setSuccess(true)
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      if (status === 403) setApiError('Self-registration is disabled. Contact an administrator.')
      else if (status === 409) setApiError(detail ?? 'Email or username already taken.')
      else setApiError('Registration failed. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: BG, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <svg viewBox="0 0 800 400" style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', opacity: 0.04, pointerEvents: 'none' }} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <defs><pattern id="rg" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0L0 0 0 40" fill="none" stroke="#111" strokeWidth="0.5" /></pattern></defs>
        <rect width="800" height="400" fill="url(#rg)" />
        <line x1="400" y1="0" x2="0"   y2="400" stroke="#111" strokeWidth="0.5" opacity="0.5" />
        <line x1="400" y1="0" x2="800" y2="400" stroke="#111" strokeWidth="0.5" opacity="0.5" />
      </svg>

      <main style={{ width: '100%', maxWidth: 440, position: 'relative' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 64, color: BLACK, letterSpacing: '0.05em', lineHeight: 1 }}>
            LB<span style={{ color: ORANGE }}>R</span>O
          </div>
          <div style={{ fontSize: 11, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.15em', marginTop: 4 }}>
            / Law-aware Breach Response Orchestrator /
          </div>
        </div>

        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 28 }}>
          {success ? (
            <div style={{ textAlign: 'center', padding: '16px 0' }}>
              <ShieldCheck style={{ width: 40, height: 40, color: '#3a7a50', margin: '0 auto 16px' }} />
              <div style={{ fontSize: 14, fontWeight: 500, color: BLACK, marginBottom: 8 }}>Account created</div>
              <div style={{ fontSize: 12, color: GRAY, marginBottom: 24 }}>You can now sign in with your credentials.</div>
              <button onClick={() => navigate('/login')} style={{ padding: '10px 24px', background: ORANGE, color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.1em', cursor: 'pointer' }}>
                Go to Login
              </button>
            </div>
          ) : (
            <>
              <h2 style={{ fontSize: 13, fontWeight: 500, color: BLACK, marginBottom: 4 }}>Create account</h2>
              <p style={{ fontSize: 11, color: GRAY, marginBottom: 24 }}>Register for access to the LBRO SOC dashboard</p>

              {apiError && (
                <div role="alert" style={{ display: 'flex', gap: 8, padding: '10px 12px', border: `1px solid rgba(229,78,27,0.35)`, background: 'rgba(229,78,27,0.08)', borderRadius: 4, marginBottom: 16, fontSize: 11, color: ORANGE }}>
                  <AlertCircle style={{ width: 14, height: 14, flexShrink: 0, marginTop: 1 }} /> {apiError}
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <Input id="fullName" label="Full name" f={fullName} onChange={v => setFullName({ value: v, error: '' })} placeholder="Jane Smith" autoComplete="name" />
                <Input id="email" label="Email" type="email" f={email} onChange={v => setEmail({ value: v, error: '' })} placeholder="analyst@your-org.com" autoComplete="email" />
                <Input id="username" label="Username" f={username} onChange={v => setUsername({ value: v, error: '' })} placeholder="jsmith" autoComplete="username" mono />

                {/* Password */}
                <div>
                  <label htmlFor="password" style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      id="password" type={showPw ? 'text' : 'password'} value={password.value}
                      onChange={e => setPassword({ value: e.target.value, error: '' })}
                      placeholder="Min 8 characters" autoComplete="new-password"
                      style={{ width: '100%', padding: '10px 40px 10px 12px', fontSize: 12, fontFamily: 'JetBrains Mono, monospace', boxSizing: 'border-box', background: BG, border: `1px solid ${password.error ? ORANGE : BORDER}`, borderRadius: 4, color: BLACK, outline: 'none' }}
                    />
                    <button type="button" onClick={() => setShowPw(v => !v)} aria-label={showPw ? 'Hide' : 'Show'} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: GRAY, display: 'flex' }}>
                      {showPw ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
                    </button>
                  </div>
                  {password.error && <div style={{ fontSize: 11, color: ORANGE, marginTop: 4, display: 'flex', gap: 4 }}><AlertCircle style={{ width: 12, height: 12 }} /> {password.error}</div>}
                </div>

                <div>
                  <label htmlFor="confirm" style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Confirm password</label>
                  <input
                    id="confirm" type="password" value={confirm.value}
                    onChange={e => setConfirm({ value: e.target.value, error: '' })}
                    placeholder="Repeat password" autoComplete="new-password"
                    style={{ width: '100%', padding: '10px 12px', fontSize: 12, fontFamily: 'JetBrains Mono, monospace', boxSizing: 'border-box', background: BG, border: `1px solid ${confirm.error ? ORANGE : BORDER}`, borderRadius: 4, color: BLACK, outline: 'none' }}
                  />
                  {confirm.error && <div style={{ fontSize: 11, color: ORANGE, marginTop: 4, display: 'flex', gap: 4 }}><AlertCircle style={{ width: 12, height: 12 }} /> {confirm.error}</div>}
                </div>

                <button
                  type="submit" disabled={loading}
                  style={{ width: '100%', padding: '11px 0', background: loading ? '#c8c2b8' : ORANGE, color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.12em', cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
                >
                  {loading
                    ? <><Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} /> Creating account…</>
                    : <><ShieldCheck style={{ width: 14, height: 14 }} /> Create account</>}
                </button>
              </form>

              <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${BORDER}`, textAlign: 'center', fontSize: 11, color: GRAY }}>
                Already have an account?{' '}
                <Link to="/login" style={{ color: ORANGE, textDecoration: 'none', fontWeight: 500 }}>Sign in</Link>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
