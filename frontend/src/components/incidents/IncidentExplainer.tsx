/**
 * IncidentExplainer — plain-English attack explanation panel.
 *
 * Shown inside IncidentDetailPage when the user clicks "Explain this incident".
 * Calls GET /api/v1/incidents/{id}/explain and renders all fields.
 */
import { useState } from 'react'
import {
  Sparkles, ChevronDown, ChevronUp, ExternalLink,
  AlertTriangle, Shield, Zap, Wrench, BookOpen, Target,
} from 'lucide-react'
import { useIncidentExplanation } from '@/hooks/useApi'

const BLACK  = '#111111'
const ORANGE = '#e54e1b'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'
const BORDER = '#c8c2b8'

const LIKELIHOOD_COLOR: Record<string, string> = {
  Low:      '#22c55e',
  Medium:   '#f59e0b',
  High:     '#f97316',
  Critical: '#ef4444',
}

function Section({
  icon, title, children,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
        {icon}
        <span style={{
          fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '0.1em', color: GRAY,
        }}>
          {title}
        </span>
      </div>
      {children}
    </div>
  )
}

function Pill({ text, color }: { text: string; color?: string }) {
  return (
    <span style={{
      display: 'inline-block',
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: 10,
      color: color ?? GRAY,
      background: color ? `${color}15` : PARCH,
      border: `1px solid ${color ? `${color}40` : BORDER}`,
      borderRadius: 2,
      padding: '2px 8px',
      marginRight: 6,
      marginBottom: 4,
    }}>
      {text}
    </span>
  )
}

interface Props {
  incidentId: string
}

export function IncidentExplainer({ incidentId }: Props) {
  const [open, setOpen] = useState(false)
  const { data, isLoading, isError } = useIncidentExplanation(
    open ? incidentId : ''   // only fetch when panel is opened
  )

  const likelihoodColor = data ? (LIKELIHOOD_COLOR[data.likelihood] ?? ORANGE) : ORANGE

  return (
    <div style={{
      border: `1px solid rgba(229,78,27,0.3)`,
      borderLeft: `3px solid ${ORANGE}`,
      borderRadius: 4,
      overflow: 'hidden',
    }}>
      {/* Toggle header */}
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '12px 16px',
          background: 'rgba(229,78,27,0.04)',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
        aria-expanded={open}
      >
        <Sparkles style={{ width: 15, height: 15, color: ORANGE, flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: BLACK, flex: 1 }}>
          Explain this incident
        </span>
        <span style={{ fontSize: 10, color: GRAY, marginRight: 6 }}>
          Plain-English attack analysis
        </span>
        {open
          ? <ChevronUp style={{ width: 14, height: 14, color: GRAY }} />
          : <ChevronDown style={{ width: 14, height: 14, color: GRAY }} />
        }
      </button>

      {/* Expanded panel */}
      {open && (
        <div style={{ padding: '16px 18px', background: CREAM, borderTop: `1px solid ${BORDER}` }}>

          {/* Loading */}
          {isLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[80, 60, 90, 50].map((w, i) => (
                <div key={i} style={{ height: 12, background: PARCH, borderRadius: 2, width: `${w}%` }} />
              ))}
            </div>
          )}

          {/* Error */}
          {isError && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: GRAY, fontSize: 12 }}>
              <AlertTriangle style={{ width: 14, height: 14, color: ORANGE }} />
              Could not load explanation. Check backend connectivity.
            </div>
          )}

          {/* Content */}
          {data && (
            <div>
              {/* Plain-English lead */}
              <div style={{
                fontSize: 13, color: BLACK, lineHeight: 1.7,
                marginBottom: 16, fontStyle: 'normal',
              }}>
                {data.plain_english}
              </div>

              {/* Context (IP, port, duration) */}
              {data.context && (
                <div style={{
                  fontSize: 11, color: GRAY, lineHeight: 1.6,
                  background: PARCH, border: `1px solid ${BORDER}`,
                  borderRadius: 3, padding: '8px 12px',
                  marginBottom: 16, fontFamily: 'JetBrains Mono, monospace',
                }}>
                  {data.context}
                </div>
              )}

              {/* Two-column impact */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <Section icon={<Zap style={{ width: 12, height: 12, color: '#f59e0b' }} />} title="Business Impact">
                  <p style={{ fontSize: 11, color: BLACK, lineHeight: 1.6, margin: 0 }}>
                    {data.business_impact}
                  </p>
                </Section>
                <Section icon={<Shield style={{ width: 12, height: 12, color: ORANGE }} />} title="Technical Impact">
                  <p style={{ fontSize: 11, color: BLACK, lineHeight: 1.6, margin: 0 }}>
                    {data.technical_impact}
                  </p>
                </Section>
              </div>

              {/* Likelihood */}
              <Section icon={<AlertTriangle style={{ width: 12, height: 12, color: likelihoodColor }} />} title="Escalation Likelihood">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    fontFamily: 'JetBrains Mono, monospace',
                    fontSize: 11, fontWeight: 700,
                    color: likelihoodColor,
                    background: `${likelihoodColor}15`,
                    border: `1px solid ${likelihoodColor}40`,
                    borderRadius: 2, padding: '3px 10px',
                  }}>
                    {data.likelihood}
                  </span>
                  <span style={{ fontSize: 11, color: GRAY }}>
                    likelihood this escalates if left unresolved
                  </span>
                </div>
              </Section>

              {/* Taxonomy */}
              <Section icon={<BookOpen style={{ width: 12, height: 12, color: GRAY }} />} title="Security Classification">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                  {data.owasp && (
                    <Pill text={data.owasp} color="#3b82f6" />
                  )}
                  {data.mitre_attack.map(m => (
                    <Pill key={m} text={m} color="#8b5cf6" />
                  ))}
                  {!data.owasp && data.mitre_attack.length === 0 && (
                    <span style={{ fontSize: 11, color: GRAY }}>No classification available for this attack type.</span>
                  )}
                </div>
              </Section>

              {/* Recommended fixes */}
              <Section icon={<Wrench style={{ width: 12, height: 12, color: '#22c55e' }} />} title="Recommended Fixes">
                <ol style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {data.recommended_fixes.map((fix, i) => (
                    <li key={i} style={{ fontSize: 11, color: BLACK, lineHeight: 1.6 }}>
                      {fix}
                    </li>
                  ))}
                </ol>
              </Section>

              {/* Learn more */}
              {data.learn_more_url && (
                <div style={{ marginTop: 4 }}>
                  <a
                    href={data.learn_more_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      fontSize: 11, color: ORANGE, textDecoration: 'none',
                      fontFamily: 'JetBrains Mono, monospace',
                    }}
                  >
                    <Target style={{ width: 11, height: 11 }} />
                    Learn more about this attack
                    <ExternalLink style={{ width: 10, height: 10 }} />
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
