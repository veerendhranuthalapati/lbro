/**
 * LBRO Registration Page – hardened with:
 *  • Email confirmation field
 *  • Regex email format validation
 *  • Symbol requirement in password (added to StrengthBar + validation)
 *  • Live password requirements checklist
 *  • Client-side rate limiting: 5 attempts → 2-min cooldown
 *  • Math CAPTCHA before submit
 */
import { useState, useEffect, useRef, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ShieldCheck, AlertCircle, Loader2, Eye, EyeOff, CheckCircle2, XCircle, Lock } from 'lucide-react'
import { authApi } from '@/api/client'
import { useAuthStore } from '@/store/authStore'
import { ROLE_PERMISSIONS } from '@/types/rbac'
import type { AuthUser, UserRole as Role } from '@/types'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const BG     = '#f0ebe2'
const GREEN  = '#16a34a'

// Rate limiting: 5 attempts per 2 minutes
const MAX_ATTEMPTS = 5
const COOLDOWN_MS  = 2 * 60 * 1000 // 2 minutes

// Email regex (RFC 5322 simplified)
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

function makeCapcha() {
  const a = Math.floor(Math.random() * 9) + 1
  const b = Math.floor(Math.random() * 9) + 1
  return { a, b, answer: String(a + b) }
}

type Field = { value: string; error: string }
const field = (v = ''): Field => ({ value: v, error: '' })

function Input({
  id, label, type = 'text', f, onChange, placeholder, autoComplete, disabled,
}: {
  id: string; label: string; type?: string; f: Field
  onChange: (v: string) => void; placeholder?: string; autoComplete?: string
  disabled?: boolean
}) {
  const [focused, setFocused] = useState(false)
  return (
    <div>
      <label htmlFor={id} style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
        {label}
      </label>
      <input
        id={id} type={type} value={f.value} placeholder={placeholder}
        autoComplete={autoComplete} spellCheck={false} disabled={disabled}
        onChange={e => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        aria-invalid={!!f.error}
        style={{
          width: '100%', padding: '10px 12px', fontSize: 12, boxSizing: 'border-box' as const,
          background: BG, border: `1px solid ${f.error ? ORANGE : focused ? ORANGE : BORDER}`,
          borderRadius: 4, color: BLACK, outline: 'none',
          opacity: disabled ? 0.6 : 1,
          transition: 'border-color 0.12s',
        }}
      />
      {f.error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: ORANGE, marginTop: 4 }}>
          <AlertCircle style={{ width: 12, height: 12, flexShrink: 0 }} /> {f.error}
        </div>
      )}
    </div>
  )
}

type PwChecks = { len8: boolean; upper: boolean; digit: boolean; symbol: boolean; len12: boolean }

function pwChecks(pw: string): PwChecks {
  return {
    len8:   pw.length >= 8,
    upper:  /[A-Z]/.test(pw),
    digit:  /[0-9]/.test(pw),
    symbol: /[^A-Za-z0-9]/.test(pw),
    len12:  pw.length >= 12,
  }
}

function StrengthBar({ pw }: { pw: string }) {
  if (!pw) return null
  const c = pwChecks(pw)
  const score = [c.len8, c.upper, c.digit, c.symbol, c.len12].filter(Boolean).length
  const colors = ['#e54e1b', '#f59e0b', '#f59e0b', '#3b82f6', '#16a34a']
  const labels = ['Too short', 'Weak', 'Fair', 'Good', 'Strong', 'Excellent']
  const color  = colors[Math.max(0, score - 1)] ?? '#ddd'

  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: 'flex', gap: 3, marginBottom: 4 }}>
        {[1,2,3,4,5].map(i => (
          <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: i <= score ? color : '#ddd', transition: 'background 0.2s' }} />
        ))}
      </div>
      <span style={{ fontSize: 10, color: score <= 2 ? ORANGE : score <= 3 ? '#f59e0b' : GREEN }}>
        {labels[score]}
      </span>
    </div>
  )
}

function PwChecklist({ pw }: { pw: string }) {
  if (!pw) return null
  const c = pwChecks(pw)
  const items: [boolean, string][] = [
    [c.len8,   'At least 8 characters'],
    [c.upper,  'One uppercase letter'],
    [c.digit,  'One number (0–9)'],
    [c.symbol, 'One symbol (!@#$…)'],
    [c.len12,  '12+ characters (recommended)'],
  ]
  return (
    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 3 }}>
      {items.map(([met, label]) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: met ? GREEN : GRAY }}>
          {met
            ? <CheckCircle2 style={{ width: 11, height: 11, flexShrink: 0 }} />
            : <XCircle      style={{ width: 11, height: 11, flexShrink: 0, color: '#c8c2b8' }} />}
          {label}
        </div>
      ))}
    </div>
  )
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const { login, isAuthenticated } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated) navigate('/dashboard', { replace: true })
  }, [isAuthenticated, navigate])

  // Fields
  const [fullName,      setFullName]      = useState(field())
  const [email,         setEmail]         = useState(field())
  const [emailConfirm,  setEmailConfirm]  = useState(field())
  const [password,      setPassword]      = useState(field())
  const [confirm,       setConfirm]       = useState(field())
  const [showPw,        setShowPw]        = useState(false)

  // Rate limiting
  const [attempts,   setAttempts]   = useState(0)
  const [lockedUntil, setLockedUntil] = useState<number | null>(null)
  const [remaining,   setRemaining]  = useState(0)

  useEffect(() => {
    if (!lockedUntil) return
    const tick = () => {
      const left = Math.max(0, Math.ceil((lockedUntil - Date.now()) / 1000))
      setRemaining(left)
      if (left === 0) { setLockedUntil(null); setAttempts(0) }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [lockedUntil])

  // CAPTCHA
  const captchaRef = useRef(makeCapcha())
  const [captchaInput, setCaptchaInput] = useState('')
  const [captchaError, setCaptchaError] = useState('')

  const [loading,  setLoading]  = useState(false)
  const [apiError, setApiError] = useState('')

  const isLocked = !!lockedUntil && Date.now() < lockedUntil

  function validate(): boolean {
    let ok = true
    const clear = <T extends Field>(setter: React.Dispatch<React.SetStateAction<T>>) =>
      (msg: string) => { setter(f => ({ ...f, error: msg })); ok = false }

    if (!fullName.value.trim())
      clear(setFullName)('Your name is required')

    if (!EMAIL_RE.test(email.value.trim()))
      clear(setEmail)('Enter a valid email address')
    else if (email.value.trim().toLowerCase() !== emailConfirm.value.trim().toLowerCase())
      clear(setEmailConfirm)('Email addresses do not match')

    const c = pwChecks(password.value)
    if (!c.len8)
      clear(setPassword)('Password must be at least 8 characters')
    else if (!c.upper)
      clear(setPassword)('Add an uppercase letter')
    else if (!c.digit)
      clear(setPassword)('Add a number (0–9)')
    else if (!c.symbol)
      clear(setPassword)('Add a symbol (!@#$…)')

    if (password.value && password.value !== confirm.value)
      clear(setConfirm)('Passwords do not match')

    if (captchaInput.trim() !== captchaRef.current.answer) {
      setCaptchaError('Incorrect answer — please try again')
      captchaRef.current = makeCapcha()
      setCaptchaInput('')
      ok = false
    }

    return ok
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setApiError('')
    setCaptchaError('')

    if (isLocked) return
    if (!validate()) {
      // Count failed attempt toward rate limit
      const next = attempts + 1
      setAttempts(next)
      if (next >= MAX_ATTEMPTS) setLockedUntil(Date.now() + COOLDOWN_MS)
      return
    }

    setLoading(true)
    try {
      const tokenResponse = await authApi.register({
        email: email.value.trim().toLowerCase(),
        full_name: fullName.value.trim(),
        password: password.value,
      })
      const { access_token } = tokenResponse

      let jwtPayload: Record<string, unknown> = {}
      try {
        const b64 = access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
        jwtPayload = JSON.parse(atob(b64))
      } catch { /* fallback */ }

      const userRecord = await authApi.me(access_token)
      const role = ((jwtPayload.role as Role) ?? userRecord.role ?? 'admin') as Role
      const jwtPerms = Array.isArray(jwtPayload.permissions) ? jwtPayload.permissions : null
      const authUser: AuthUser = {
        id:          userRecord.id,
        name:        userRecord.full_name,
        email:       userRecord.email,
        role,
        permissions: jwtPerms ?? (ROLE_PERMISSIONS[role as keyof typeof ROLE_PERMISSIONS] ?? []),
        last_login:  userRecord.last_login,
      }
      login(access_token, tokenResponse.refresh_token ?? null, authUser)
      navigate('/welcome', { replace: true })
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const nextAttempts = attempts + 1
      setAttempts(nextAttempts)
      if (nextAttempts >= MAX_ATTEMPTS) setLockedUntil(Date.now() + COOLDOWN_MS)
      if (status === 409)      setApiError(detail ?? 'Email already registered.')
      else if (status === 403) setApiError('Registration is currently disabled.')
      else                     setApiError('Could not create account. Is the backend running?')
      // Refresh captcha on API error too
      captchaRef.current = makeCapcha()
      setCaptchaInput('')
    } finally {
      setLoading(false)
    }
  }

  const attemptsLeft = Math.max(0, MAX_ATTEMPTS - attempts)

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
          <h2 style={{ fontSize: 14, fontWeight: 600, color: BLACK, marginBottom: 4 }}>Create your account</h2>
          <p style={{ fontSize: 11, color: GRAY, marginBottom: 24 }}>
            Free to use &middot; No credit card &middot; Start monitoring in 2 minutes
          </p>

          {/* Rate limit lockout banner */}
          {isLocked && (
            <div role="alert" aria-live="assertive" style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', border: `1px solid rgba(229,78,27,0.35)`, background: 'rgba(229,78,27,0.08)', borderRadius: 4, marginBottom: 16 }}>
              <Lock style={{ width: 14, height: 14, color: ORANGE, flexShrink: 0, marginTop: 1 }} />
              <div style={{ fontSize: 11, color: ORANGE }}>
                <div style={{ fontWeight: 600 }}>Too many failed attempts</div>
                <div>Please wait {remaining}s before trying again.</div>
              </div>
            </div>
          )}

          {/* API error */}
          {apiError && !isLocked && (
            <div role="alert" style={{ display: 'flex', gap: 8, padding: '10px 12px', border: `1px solid rgba(229,78,27,0.35)`, background: 'rgba(229,78,27,0.08)', borderRadius: 4, marginBottom: 16, fontSize: 11, color: ORANGE }}>
              <AlertCircle style={{ width: 14, height: 14, flexShrink: 0, marginTop: 1 }} />
              <span>{apiError}{attemptsLeft > 0 && attemptsLeft < MAX_ATTEMPTS ? ` (${attemptsLeft} attempt${attemptsLeft !== 1 ? 's' : ''} left before lockout)` : ''}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Full name */}
            <Input id="fullName" label="Full name" f={fullName}
              onChange={v => setFullName({ value: v, error: '' })}
              placeholder="Jane Smith" autoComplete="name" disabled={isLocked} />

            {/* Email */}
            <Input id="email" label="Email" type="email" f={email}
              onChange={v => setEmail({ value: v, error: '' })}
              placeholder="you@company.com" autoComplete="email" disabled={isLocked} />

            {/* Confirm email */}
            <Input id="emailConfirm" label="Confirm email" type="email" f={emailConfirm}
              onChange={v => setEmailConfirm({ value: v, error: '' })}
              placeholder="Repeat your email" autoComplete="email" disabled={isLocked} />

            {/* Password with show/hide */}
            <div>
              <label htmlFor="password" style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="password"
                  type={showPw ? 'text' : 'password'}
                  value={password.value}
                  onChange={e => setPassword({ value: e.target.value, error: '' })}
                  placeholder="Min 8 chars, uppercase, number, symbol"
                  autoComplete="new-password"
                  disabled={isLocked}
                  style={{
                    width: '100%', padding: '10px 40px 10px 12px', fontSize: 12,
                    fontFamily: 'JetBrains Mono, monospace', boxSizing: 'border-box' as const,
                    background: BG, border: `1px solid ${password.error ? ORANGE : BORDER}`,
                    borderRadius: 4, color: BLACK, outline: 'none',
                    opacity: isLocked ? 0.6 : 1,
                  }}
                />
                <button type="button" onClick={() => setShowPw(v => !v)}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: GRAY, display: 'flex' }}>
                  {showPw ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
                </button>
              </div>
              {password.error
                ? <div style={{ fontSize: 11, color: ORANGE, marginTop: 4, display: 'flex', gap: 4 }}><AlertCircle style={{ width: 12, height: 12, flexShrink: 0 }} /> {password.error}</div>
                : <StrengthBar pw={password.value} />}
              <PwChecklist pw={password.value} />
            </div>

            {/* Confirm password */}
            <div>
              <label htmlFor="confirm" style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Confirm password
              </label>
              <input
                id="confirm" type="password" value={confirm.value}
                onChange={e => setConfirm({ value: e.target.value, error: '' })}
                placeholder="Repeat your password"
                autoComplete="new-password"
                disabled={isLocked}
                style={{
                  width: '100%', padding: '10px 12px', fontSize: 12,
                  fontFamily: 'JetBrains Mono, monospace', boxSizing: 'border-box' as const,
                  background: BG, border: `1px solid ${confirm.error ? ORANGE : BORDER}`,
                  borderRadius: 4, color: BLACK, outline: 'none', opacity: isLocked ? 0.6 : 1,
                }}
              />
              {confirm.error && (
                <div style={{ fontSize: 11, color: ORANGE, marginTop: 4, display: 'flex', gap: 4 }}>
                  <AlertCircle style={{ width: 12, height: 12, flexShrink: 0 }} /> {confirm.error}
                </div>
              )}
              {/* Show match indicator when confirm is non-empty and no error */}
              {!confirm.error && confirm.value && password.value && (
                <div style={{ fontSize: 11, marginTop: 4, display: 'flex', gap: 4, color: confirm.value === password.value ? GREEN : GRAY }}>
                  {confirm.value === password.value
                    ? <><CheckCircle2 style={{ width: 11, height: 11, flexShrink: 0 }} /> Passwords match</>
                    : <><XCircle style={{ width: 11, height: 11, flexShrink: 0, color: '#c8c2b8' }} /> Not matching yet</>}
                </div>
              )}
            </div>

            {/* Math CAPTCHA */}
            <div style={{ background: BG, border: `1px solid ${captchaError ? ORANGE : BORDER}`, borderRadius: 4, padding: '12px 14px' }}>
              <div style={{ fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Quick check — what is {captchaRef.current.a} + {captchaRef.current.b}?
              </div>
              <input
                type="text" inputMode="numeric" pattern="[0-9]*"
                value={captchaInput}
                onChange={e => { setCaptchaInput(e.target.value); setCaptchaError('') }}
                placeholder="Type the answer"
                disabled={isLocked}
                aria-label={`What is ${captchaRef.current.a} plus ${captchaRef.current.b}?`}
                style={{
                  width: '100%', padding: '8px 10px', fontSize: 12, boxSizing: 'border-box' as const,
                  background: CREAM, border: `1px solid ${captchaError ? ORANGE : BORDER}`,
                  borderRadius: 4, color: BLACK, outline: 'none',
                  opacity: isLocked ? 0.6 : 1,
                }}
              />
              {captchaError && (
                <div style={{ fontSize: 11, color: ORANGE, marginTop: 4, display: 'flex', gap: 4 }}>
                  <AlertCircle style={{ width: 12, height: 12, flexShrink: 0 }} /> {captchaError}
                </div>
              )}
            </div>

            {/* Attempt warning (not yet locked) */}
            {!isLocked && attempts > 0 && attempts < MAX_ATTEMPTS && (
              <div style={{ fontSize: 11, color: '#f59e0b', display: 'flex', gap: 5, alignItems: 'center' }}>
                <AlertCircle style={{ width: 12, height: 12, flexShrink: 0 }} />
                {attemptsLeft} attempt{attemptsLeft !== 1 ? 's' : ''} remaining before temporary lockout
              </div>
            )}

            <button
              type="submit"
              disabled={loading || isLocked}
              style={{
                width: '100%', marginTop: 4, padding: '12px 0',
                background: loading || isLocked ? '#c8c2b8' : ORANGE,
                color: '#fff', border: 'none', borderRadius: 4,
                fontSize: 12, fontWeight: 600,
                cursor: loading || isLocked ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                transition: 'background 0.15s',
              }}
            >
              {loading
                ? <><Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} /> Creating your account...</>
                : isLocked
                  ? <><Lock style={{ width: 14, height: 14 }} /> Locked — wait {remaining}s</>
                  : <><ShieldCheck style={{ width: 14, height: 14 }} /> Get started &mdash; it&apos;s free</>}
            </button>
          </form>

          <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${BORDER}`, textAlign: 'center', fontSize: 11, color: GRAY }}>
            Already have an account?{' '}
            <Link to="/login" style={{ color: ORANGE, textDecoration: 'none', fontWeight: 500 }}>Sign in</Link>
          </div>
        </div>

        <p style={{ textAlign: 'center', fontSize: 10, color: GRAY, marginTop: 16, lineHeight: 1.6 }}>
          By creating an account you accept the{' '}
          <Link to="/privacy" style={{ color: GRAY, textDecoration: 'underline' }}>privacy policy</Link>.
        </p>
      </main>
    </div>
  )
}
