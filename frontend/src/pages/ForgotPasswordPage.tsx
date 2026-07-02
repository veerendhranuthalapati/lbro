import { Link } from 'react-router-dom'
import { ShieldCheck, Mail } from 'lucide-react'

export default function ForgotPasswordPage() {
  return (
    <div style={{ minHeight: '100vh', background: '#f0ebe2', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      {/* Perspective grid */}
      <svg style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', opacity: 0.04, pointerEvents: 'none' }} aria-hidden="true">
        <defs>
          <pattern id="pgrid-fp" x="0" y="0" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M60 0L0 0 0 60" fill="none" stroke="#111" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#pgrid-fp)" />
      </svg>

      <div style={{ width: '100%', maxWidth: 400, textAlign: 'center', position: 'relative' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 52, height: 52, border: '1px solid rgba(229,78,27,0.3)', background: 'rgba(229,78,27,0.06)', borderRadius: 4, marginBottom: 16 }}>
          <ShieldCheck style={{ width: 24, height: 24, color: '#e54e1b' }} />
        </div>

        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 36, color: '#111111', letterSpacing: '0.04em', lineHeight: 1, marginBottom: 8 }}>
          Reset Access
        </h1>
        <p style={{ fontSize: 11, color: '#6b6560', marginBottom: 20, lineHeight: 1.6 }}>
          API keys are managed through AWS Secrets Manager.<br />
          Contact your administrator to rotate or recover your key.
        </p>

        <div style={{ background: '#f9f5ef', border: '1px solid #c8c2b8', borderRadius: 4, padding: 20, marginBottom: 16, textAlign: 'left' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#111111', marginBottom: 12 }}>
            <Mail style={{ width: 14, height: 14, color: '#e54e1b' }} />
            <span>Contact: <a href="mailto:admin@lbro.io" style={{ color: '#e54e1b', textDecoration: 'none' }}>admin@lbro.io</a></span>
          </div>
          <p style={{ fontSize: 11, color: '#6b6560' }}>
            Or visit AWS Console - Secrets Manager -{' '}
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#111111', background: '#e8e2d9', padding: '1px 5px', borderRadius: 2 }}>
              lbro/prod/api-key
            </span>
          </p>
        </div>

        <Link
          to="/login"
          style={{ fontSize: 11, color: '#6b6560', textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.08em' }}
          onMouseEnter={e => (e.currentTarget.style.color = '#e54e1b')}
          onMouseLeave={e => (e.currentTarget.style.color = '#6b6560')}
        >
          Back to login
        </Link>
      </div>
    </div>
  )
}
