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
import { useIncidentExplanation, useIncidentAttackExplanation } from '@/hooks/useApi'

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
  const [audience, setAudience] = useState<'executive' | 'analyst'>('analyst')
  const [tab, setTab] = useState<'what' | 'why' | 'now' | 'protect' | 'learn'>('what')
  const enabled = open && !!incidentId
  const { data, isLoading, isError } = useIncidentExplanation(enabled ? incidentId : '')
  const { data: guideData, isLoading: guideLoading } = useIncidentAttackExplanation(
    enabled ? incidentId : '',
    audience,
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
          Understand this attack
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

          {/* Decision-support disclaimer + uncertainty from composed guide */}
          {(guideData?.disclaimer || guideData?.uncertainty_banner) && (
            <div
              role="status"
              style={{
                fontSize: 11,
                lineHeight: 1.55,
                color: BLACK,
                background: '#fff7ed',
                border: `1px solid ${ORANGE}55`,
                borderRadius: 3,
                padding: '10px 12px',
                marginBottom: 14,
              }}
            >
              {guideData?.uncertainty_banner && (
                <p style={{ margin: '0 0 6px', fontWeight: 600, color: ORANGE }}>
                  {guideData.uncertainty_banner.title}
                </p>
              )}
              <p style={{ margin: 0 }}>{String(guideData?.disclaimer ?? '')}</p>
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }} role="tablist" aria-label="Explanation audience">
            {(['analyst', 'executive'] as const).map(mode => (
              <button
                key={mode}
                type="button"
                role="tab"
                aria-selected={audience === mode}
                onClick={() => setAudience(mode)}
                style={{
                  fontSize: 10,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  padding: '4px 10px',
                  borderRadius: 2,
                  border: `1px solid ${audience === mode ? ORANGE : BORDER}`,
                  background: audience === mode ? `${ORANGE}12` : '#fff',
                  color: audience === mode ? ORANGE : GRAY,
                  cursor: 'pointer',
                }}
              >
                {mode}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }} role="tablist" aria-label="Explanation sections">
            {([
              ['what', 'What happened'],
              ['why', 'Why we flagged it'],
              ['now', 'What to do now'],
              ['protect', 'How to protect'],
              ['learn', 'Learn more'],
            ] as const).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                style={{
                  fontSize: 10,
                  padding: '4px 8px',
                  borderRadius: 2,
                  border: `1px solid ${tab === id ? ORANGE : BORDER}`,
                  background: tab === id ? `${ORANGE}12` : '#fff',
                  color: tab === id ? ORANGE : GRAY,
                  cursor: 'pointer',
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Loading */}
          {(isLoading || guideLoading) && (
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
            <div role="tabpanel">
              {tab === 'what' && (
                <>
                  <div style={{ fontSize: 13, color: BLACK, lineHeight: 1.7, marginBottom: 16 }}>
                    {audience === 'executive'
                      ? (guideData?.guide?.summary_plain ?? data.plain_english)
                      : data.plain_english}
                  </div>
                  {data.context && (
                    <div style={{
                      fontSize: 11, color: GRAY, lineHeight: 1.6,
                      background: PARCH, border: `1px solid ${BORDER}`,
                      borderRadius: 3, padding: '8px 12px', marginBottom: 16,
                      fontFamily: 'JetBrains Mono, monospace',
                    }}>
                      {data.context}
                    </div>
                  )}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <Section icon={<Zap style={{ width: 12, height: 12, color: '#f59e0b' }} />} title="Business Impact">
                      <p style={{ fontSize: 11, color: BLACK, lineHeight: 1.6, margin: 0 }}>{data.business_impact}</p>
                    </Section>
                    <Section icon={<Shield style={{ width: 12, height: 12, color: ORANGE }} />} title="Technical Impact">
                      <p style={{ fontSize: 11, color: BLACK, lineHeight: 1.6, margin: 0 }}>{data.technical_impact}</p>
                    </Section>
                  </div>
                </>
              )}
              {tab === 'why' && (
                <Section icon={<BookOpen style={{ width: 12, height: 12, color: GRAY }} />} title="Why we flagged it">
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 11, color: BLACK, lineHeight: 1.6 }}>
                    {(guideData?.why_flagged ?? []).map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                    {data.mitre_attack.map(m => (
                      <Pill key={m} text={m} color="#8b5cf6" />
                    ))}
                  </div>
                </Section>
              )}
              {tab === 'now' && (
                <Section icon={<Wrench style={{ width: 12, height: 12, color: ORANGE }} />} title="What to do now">
                  <ol style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {(guideData?.guide?.immediate_actions ?? data.recommended_fixes).map((step, i) => (
                      <li key={i} style={{ fontSize: 11, color: BLACK, lineHeight: 1.6 }}>{step}</li>
                    ))}
                  </ol>
                </Section>
              )}
              {tab === 'protect' && guideData?.guide?.prevention && (
                <div style={{ fontSize: 11, color: BLACK, lineHeight: 1.6 }}>
                  {(['people', 'process', 'technology'] as const).map(k => (
                    <div key={k} style={{ marginBottom: 10 }}>
                      <strong style={{ textTransform: 'capitalize' }}>{k}: </strong>
                      {(guideData.guide!.prevention![k] ?? []).join(' ')}
                    </div>
                  ))}
                </div>
              )}
              {tab === 'learn' && (
                <>
                  {data.learn_more_url && (
                    <a href={data.learn_more_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 11, color: ORANGE }}>
                      MITRE / external reference <ExternalLink style={{ width: 10, height: 10, display: 'inline' }} />
                    </a>
                  )}
                  {(guideData?.guide?.references ?? []).map((url, i) => (
                    <p key={i} style={{ fontSize: 11, margin: '6px 0' }}>
                      <a href={String(url)} target="_blank" rel="noopener noreferrer" style={{ color: ORANGE }}>{String(url)}</a>
                    </p>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
