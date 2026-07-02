/**
 * LBRO Login Page -- editorial off-white/orange/black theme
 * Authentication via POST /api/v1/auth/login (JWT Bearer)
 */
import { useState, type FormEvent, useEffect } from 'react'
import { useNavigate, Link, useLocation } from 'react-router-dom'
import { Eye, EyeOff, ShieldCheck, AlertCircle, Loader2, Lock } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/api/client'
import { logger, auditAction } from '@/lib/logger'
import { LOGIN_MAX_ATTEMPTS, ROLES } from '@/constants'
import type { AuthUser } from '@/types'
import type { UserRole } from '@/constants'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const BG     = '#f0ebe2'

export default function LoginPage() {
  const [email, setEmail]         = useState('')
  const [password, setPassword]   = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError]         = useState('')
  const [loading, setLoading]     = useState(false)

  const { login, isAuthenticated, incrementLoginAttempts, resetLoginAttempts, isLocked, loginAttempts, lockedUntil } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (isAuthenticated) {
      const from = (location.state as { from?: string })?.from ?? '/dashboard'
      navigate(from, { replace: true })
    }
  }, [isAuthenticated, navigate, location.state])

  const [lockoutRemaining, setLockoutRemaining] = useState(0)
  useEffect(() => {
    if (!lockedUntil) return
    const tick = () => setLockoutRemaining(Math.max(0, Math.ceil((lockedUntil - Date.now()) / 1000)))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [lockedUntil])

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError('')

    if (isLocked()) {
      setError(`Too many failed attempts. Try again in ${Math.ceil(lockoutRemaining / 60)} minute${lockoutRemaining > 60 ? 's' : ''}.`)
      return
    }
    if (!email.trim())    { setError('Email is required.'); return }
    if (!password.trim()) { setError('Password is required.'); return }

    setLoading(true)
    try {
      // 1. Exchange credentials for JWT
      const tokenResponse = await authApi.login(email.trim(), password)
      const { access_token } = tokenResponse

      // 2. Fetch the authenticated user's profile.
      //    Pass the token explicitly -- it is not yet in the store's memory mirror
      //    so the Axios interceptor cannot inject it automatically yet.
      const userRecord = await authApi.me(access_token)

      // 3. Map backend User -> AuthUser (store shape)
      const authUser: AuthUser = {
        id:          userRecord.id,
        name:        userRecord.full_name,
        email:       userRecord.email,
        role:        (userRecord.role as UserRole) ?? ROLES.VIEWER,
        permissions: [],    // derived from role at runtime by rbac.ts helpers
        last_login:  userRecord.last_login,
      }

      // 4. Commit to store -- this also writes to sessionStorage
      resetLoginAttempts()
      login(access_token, tokenResponse.refresh_token ?? null, authUser)
      auditAction('auth:login', 'session', 'current', { source: 'login-page' })
      logger.info('User authenticated successfully', { userId: authUser.id, role: authUser.role })

      const from = (location.state as { from?: string })?.from ?? '/dashboard'
      navigate(from, { replace: true })

    } catch (err: unknown) {
      incrementLoginAttempts()
      const remaining = LOGIN_MAX_ATTEMPTS - loginAttempts - 1

      // Distinguish 401 (bad credentials) from network/server errors
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 401 || status === 422) {
        setError(remaining > 0
          ? `Invalid credentials. ${remaining} attempt${remaining !== 1 ? 's' : ''} remaining.`
          : 'Account locked due to too many failed attempts.')
      } else {
        setError('Authentication service unavailable. Please try again.')
      }
      logger.warn('Login failed', { status, email })
    } finally {
      setLoading(false)
    }
  }

  const locked = isLocked()
  const canSubmit = !loading && !locked && !!email.trim() && !!password.trim()

  return (
    <div style={{ minHeight: '100vh', background: BG, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      {/* Perspective grid decoration */}
      <svg
        viewBox="0 0 800 400"
        style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', opacity: 0.04, pointerEvents: 'none' }}
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <pattern id="lgrid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M40 0L0 0 0 40" fill="none" stroke="#111" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="800" height="400" fill="url(#lgrid)" />
        <line x1="400" y1="0" x2="0"   y2="400" stroke="#111" strokeWidth="0.5" opacity="0.5" />
        <line x1="400" y1="0" x2="800" y2="400" stroke="#111" strokeWidth="0.5" opacity="0.5" />
        <line x1="400" y1="0" x2="200" y2="400" stroke="#111" strokeWidth="0.3" opacity="0.3" />
        <line x1="400" y1="0" x2="600" y2="400" stroke="#111" strokeWidth="0.3" opacity="0.3" />
      </svg>

      <main style={{ width: '100%', maxWidth: 420, position: 'relative' }} aria-label="Login">
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 64, color: BLACK, letterSpacing: '0.05em', lineHeight: 1 }}>
            LB<span style={{ color: ORANGE }}>R</span>O
          </div>
          <div style={{ fontSize: 11, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.15em', marginTop: 4 }}>
            / Law-aware Breach Response Orchestrator /
          </div>
        </div>

        {/* Card */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 28 }}>
          <h2 style={{ fontSize: 13, fontWeight: 500, color: BLACK, marginBottom: 4 }}>Authenticate</h2>
          <p style={{ fontSize: 11, color: GRAY, marginBottom: 24 }}>Sign in with your credentials to access the SOC dashboard</p>

          {/* Lockout banner */}
          {locked && (
            <div role="alert" aria-live="assertive" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', border: `1px solid rgba(229,78,27,0.35)`, background: 'rgba(229,78,27,0.08)', borderRadius: 4, marginBottom: 16 }}>
              <Lock style={{ width: 14, height: 14, color: ORANGE, flexShrink: 0 }} aria-hidden="true" />
              <div style={{ fontSize: 11, color: ORANGE }}>
                <div style={{ fontWeight: 500 }}>Account temporarily locked</div>
                <div>Try again in {Math.ceil(lockoutRemaining / 60)} minute{lockoutRemaining > 60 ? 's' : ''}</div>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Email field */}
            <div>
              <label htmlFor="email" style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="analyst@your-org.com"
                autoComplete="email"
                autoCapitalize="none"
                spellCheck={false}
                disabled={loading || locked}
                aria-required="true"
                aria-invalid={!!error}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  fontSize: 12,
                  background: BG,
                  border: `1px solid ${BORDER}`,
                  borderRadius: 4,
                  color: BLACK,
                  outline: 'none',
                  opacity: loading || locked ? 0.5 : 1,
                  boxSizing: 'border-box',
                }}
                onFocus={e => { e.target.style.borderColor = ORANGE }}
                onBlur={e => { e.target.style.borderColor = BORDER }}
              />
            </div>

            {/* Password field */}
            <div>
              <label htmlFor="password" style={{ display: 'block', fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  autoComplete="current-password"
                  disabled={loading || locked}
                  aria-required="true"
                  aria-invalid={!!error}
                  aria-describedby={error ? 'login-error' : undefined}
                  style={{
                    width: '100%',
                    padding: '10px 40px 10px 12px',
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 12,
                    background: BG,
                    border: `1px solid ${error ? ORANGE : BORDER}`,
                    borderRadius: 4,
                    color: BLACK,
                    outline: 'none',
                    opacity: loading || locked ? 0.5 : 1,
                    boxSizing: 'border-box',
                  }}
                  onFocus={e => { if (!error) e.target.style.borderColor = ORANGE }}
                  onBlur={e => { if (!error) e.target.style.borderColor = BORDER }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: GRAY, display: 'flex', alignItems: 'center' }}
                >
                  {showPassword
                    ? <EyeOff style={{ width: 15, height: 15 }} aria-hidden="true" />
                    : <Eye    style={{ width: 15, height: 15 }} aria-hidden="true" />}
                </button>
              </div>

              <div id="login-error" role="alert" aria-live="polite" style={{ minHeight: 18, marginTop: 6 }}>
                {error && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: ORANGE }}>
                    <AlertCircle style={{ width: 13, height: 13, flexShrink: 0 }} aria-hidden="true" />
                    {error}
                  </div>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              style={{
                width: '100%',
                padding: '11px 0',
                background: canSubmit ? ORANGE : '#c8c2b8',
                color: '#fff',
                border: 'none',
                borderRadius: 4,
                fontSize: 11,
                fontWeight: 500,
                textTransform: 'uppercase',
                letterSpacing: '0.12em',
                cursor: canSubmit ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                transition: 'background 0.15s',
              }}
            >
              {loading ? (
                <><Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} aria-hidden="true" /> Authenticating…</>
              ) : (
                <><ShieldCheck style={{ width: 14, height: 14 }} aria-hidden="true" /> Authenticate</>
              )}
            </button>
          </form>

          <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${BORDER}`, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Link to="/forgot-password" style={{ fontSize: 11, color: GRAY, textDecoration: 'none' }}>
              Forgot password? Contact your administrator
            </Link>
            <div style={{ fontSize: 11, color: GRAY }}>
              No account?{' '}
              <Link to="/register" style={{ color: ORANGE, textDecoration: 'none', fontWeight: 500 }}>
                Create one
              </Link>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
