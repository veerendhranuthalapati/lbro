import { useNavigate } from 'react-router-dom'
import { ShieldOff } from 'lucide-react'

export default function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <div style={{ minHeight: '100vh', background: '#f0ebe2', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <ShieldOff style={{ width: 40, height: 40, color: '#c8c2b8', margin: '0 auto 16px' }} aria-hidden="true" />
        <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 96, color: '#c8c2b8', lineHeight: 1, marginBottom: 8 }}>404</div>
        <p style={{ fontSize: 14, color: '#6b6560', marginBottom: 4 }}>Page not found</p>
        <p style={{ fontSize: 12, color: '#c8c2b8', marginBottom: 24 }}>The page you're looking for doesn't exist or was moved.</p>
        <button
          onClick={() => navigate('/dashboard')}
          style={{ padding: '10px 24px', background: '#e54e1b', color: '#fff', border: 'none', borderRadius: 2, fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.1em', cursor: 'pointer' }}
        >
          Return to Dashboard
        </button>
      </div>
    </div>
  )
}
