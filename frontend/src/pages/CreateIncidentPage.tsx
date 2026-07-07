/**
 * Create Incident Page -- POST /api/v1/incidents
 * Navigates to the new incident detail on success.
 */
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ShieldAlert, Loader2 } from 'lucide-react'
import { useCreateIncident } from '@/hooks/useApi'
import type { IncidentSeverity, IncidentStatus } from '@/types'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const BG     = '#f0ebe2'

const inputStyle = {
  width: '100%',
  padding: '9px 12px',
  fontSize: 12,
  background: BG,
  border: `1px solid ${BORDER}`,
  borderRadius: 4,
  color: BLACK,
  outline: 'none',
  boxSizing: 'border-box' as const,
}

const labelStyle = {
  display: 'block' as const,
  fontSize: 10,
  fontWeight: 500,
  color: GRAY,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.1em',
  marginBottom: 6,
}

export default function CreateIncidentPage() {
  const navigate = useNavigate()
  const createMutation = useCreateIncident()

  const [title,          setTitle]          = useState('')
  const [description,    setDescription]    = useState('')
  const [severity,       setSeverity]       = useState<IncidentSeverity>('medium')
  const [sourceIp,       setSourceIp]       = useState('')
  const [personalData,   setPersonalData]   = useState(false)
  const [healthData,     setHealthData]     = useState(false)
  const [error,          setError]          = useState('')

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (!title.trim()) { setError('Title is required.'); return }

    try {
      const created = await createMutation.mutateAsync({
        title:                  title.trim(),
        description:            description.trim() || undefined,
        severity,
        source_ip:              sourceIp.trim() || undefined,
        personal_data_involved: personalData,
        health_data_involved:   healthData,
      })
      navigate(`/incidents/${created.id}`, { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? 'Failed to create incident. Please try again.')
    }
  }

  const severities: IncidentSeverity[] = ['low', 'medium', 'high', 'critical']

  return (
    <div style={{ maxWidth: 640, display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div>
        <button
          onClick={() => navigate('/incidents')}
          style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: GRAY, background: 'none', border: 'none', cursor: 'pointer', padding: 0, marginBottom: 16 }}
        >
          <ArrowLeft style={{ width: 13, height: 13 }} /> Back to incidents
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ShieldAlert style={{ width: 20, height: 20, color: ORANGE }} aria-hidden="true" />
          <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
            New Incident
          </h1>
        </div>
        <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
          Report a security issue. LBRO will classify it automatically and track any compliance deadlines.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Title */}
        <div>
          <label style={labelStyle}>Title *</label>
          <input
            style={inputStyle}
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="e.g. Ransomware detected on finance-srv-01"
            onFocus={e => { e.target.style.borderColor = ORANGE }}
            onBlur={e => { e.target.style.borderColor = BORDER }}
          />
        </div>

        {/* Severity */}
        <div>
          <label style={labelStyle}>Severity</label>
          <div style={{ display: 'flex', gap: 6 }}>
            {severities.map(s => (
              <button
                key={s}
                type="button"
                onClick={() => setSeverity(s)}
                style={{
                  flex: 1,
                  padding: '8px 0',
                  fontSize: 10,
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  border: `1px solid ${severity === s ? ORANGE : BORDER}`,
                  background: severity === s ? 'rgba(229,78,27,0.08)' : 'transparent',
                  color: severity === s ? ORANGE : GRAY,
                  borderRadius: 2,
                  cursor: 'pointer',
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Description */}
        <div>
          <label style={labelStyle}>Description</label>
          <textarea
            style={{ ...inputStyle, minHeight: 80, resize: 'vertical', fontFamily: 'inherit' }}
            value={description}
            onChange={e => setDescription(e.target.value)}
            placeholder="Initial observations, attack vector, affected scope…"
            onFocus={e => { e.target.style.borderColor = ORANGE }}
            onBlur={e => { e.target.style.borderColor = BORDER }}
          />
        </div>

        {/* Source IP + Affected Systems */}
        <div>
          <label style={labelStyle}>Source IP</label>
          <input
            style={inputStyle}
            value={sourceIp}
            onChange={e => setSourceIp(e.target.value)}
            placeholder="192.168.1.100"
            onFocus={e => { e.target.style.borderColor = ORANGE }}
            onBlur={e => { e.target.style.borderColor = BORDER }}
          />
        </div>

        {/* Data flags */}
        <div style={{ display: 'flex', gap: 16 }}>
          {[
            { label: 'Personal data involved (GDPR / DPDPA)', value: personalData, set: setPersonalData },
            { label: 'Health data involved (HIPAA)',           value: healthData,   set: setHealthData   },
          ].map(({ label, value, set }) => (
            <label key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: BLACK, cursor: 'pointer', flex: 1 }}>
              <div
                onClick={() => set(v => !v)}
                style={{
                  width: 16, height: 16, borderRadius: 2, flexShrink: 0,
                  border: `1.5px solid ${value ? ORANGE : BORDER}`,
                  background: value ? ORANGE : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                {value && (
                  <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
                    <path d="M1 3.5L3.5 6L8 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </div>
              {label}
            </label>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div style={{ fontSize: 11, color: ORANGE, padding: '8px 12px', background: 'rgba(229,78,27,0.06)', border: '1px solid rgba(229,78,27,0.3)', borderRadius: 4 }}>
            {error}
          </div>
        )}

        {/* Submit */}
        <div style={{ display: 'flex', gap: 8, paddingTop: 4 }}>
          <button
            type="button"
            onClick={() => navigate('/incidents')}
            style={{ padding: '10px 20px', fontSize: 11, border: `1px solid ${BORDER}`, background: 'transparent', color: GRAY, borderRadius: 4, cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.1em' }}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending || !title.trim()}
            style={{
              flex: 1, padding: '10px 0', fontSize: 11, fontWeight: 500,
              background: createMutation.isPending || !title.trim() ? BORDER : ORANGE,
              color: '#fff', border: 'none', borderRadius: 4, cursor: createMutation.isPending || !title.trim() ? 'not-allowed' : 'pointer',
              textTransform: 'uppercase', letterSpacing: '0.1em',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}
          >
            {createMutation.isPending
              ? <><Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} /> Creating…</>
              : 'Create Incident'}
          </button>
        </div>
      </form>
    </div>
  )
}