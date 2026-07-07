import { useMlStats } from '@/hooks/useApi'
import { Brain, TrendingUp, AlertCircle, CheckCircle, BarChart2, Cpu, Wifi } from 'lucide-react'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

interface ModelInfo {
  model_id: string; version: string; trained_at: string
  accuracy: number; f1_score: number; is_active: boolean
  feature_count: number; class_count: number
}

interface MLStats {
  active_model: ModelInfo | null
  registry: ModelInfo[]
  predictions_today: number
  avg_confidence: number
  low_confidence_count: number
  attack_distribution: Record<string, number>
  top_features: Array<{ name: string; importance: number }>
}

function confColor(score: number) {
  if (score >= 0.85) return '#3a7a50'
  if (score >= 0.65) return '#d97706'
  return ORANGE
}

export default function MLInsightsPage() {
  const { data: rawStats, isLoading, isError } = useMlStats()
  const stats = rawStats as unknown as MLStats | undefined

  const maxAttackCount = stats ? Math.max(...Object.values(stats.attack_distribution)) : 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Brain style={{ width: 20, height: 20, color: ORANGE }} aria-hidden="true" />
        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
          Threat Detection
        </h1>
      </div>

      {isLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} style={{ height: 96, background: PARCH, borderRadius: 4 }} />
          ))}
        </div>
      ) : isError ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '64px 0', gap: 12 }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'rgba(229,78,27,0.08)', border: '1px solid rgba(229,78,27,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Wifi style={{ width: 20, height: 20, color: ORANGE, opacity: 0.6 }} aria-hidden="true" />
          </div>
          <p style={{ fontSize: 13, color: BLACK, fontWeight: 500 }}>Detection engine offline</p>
          <p style={{ fontSize: 11, color: GRAY, textAlign: 'center', maxWidth: 320 }}>
            The ML service is not responding. Check that the backend is running and the model is loaded.
          </p>
        </div>
      ) : stats ? (
        <>
          {/* KPIs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
            {[
              { icon: <Cpu style={{ width: 14, height: 14, color: ORANGE }} />, label: 'Predictions today', value: stats.predictions_today.toLocaleString(), color: ORANGE },
              { icon: <TrendingUp style={{ width: 14, height: 14, color: '#3a7a50' }} />, label: 'Avg confidence', value: `${(stats.avg_confidence * 100).toFixed(1)}%`, color: confColor(stats.avg_confidence) },
              { icon: <AlertCircle style={{ width: 14, height: 14, color: '#d97706' }} />, label: 'Needs review', value: stats.low_confidence_count.toString(), color: stats.low_confidence_count > 0 ? '#d97706' : '#3a7a50' },
              { icon: <CheckCircle style={{ width: 14, height: 14, color: '#3b82f6' }} />, label: 'Model accuracy', value: stats.active_model ? `${(stats.active_model.accuracy * 100).toFixed(1)}%` : 'N/A', color: BLACK },
            ].map(k => (
              <div key={k.label} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '14px 16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: GRAY, marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  {k.icon} {k.label}
                </div>
                <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 36, color: k.color, lineHeight: 1 }}>{k.value}</div>
              </div>
            ))}
          </div>

          {/* Active model */}
          {stats.active_model && (
            <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderTop: `3px solid ${ORANGE}`, borderRadius: 4, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
                <div>
                  <div style={{ fontSize: 11, fontWeight: 500, color: ORANGE, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 2 }}>Active model</div>
                  <div style={{ fontSize: 11, color: GRAY }}>v{stats.active_model.version} · Trained {new Date(stats.active_model.trained_at).toLocaleDateString()}</div>
                </div>
                <span style={{ fontSize: 10, padding: '2px 8px', border: '1px solid rgba(58,122,80,0.3)', background: 'rgba(58,122,80,0.08)', color: '#3a7a50', borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Active</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                {[
                  { label: 'Accuracy', value: `${(stats.active_model.accuracy * 100).toFixed(2)}%` },
                  { label: 'F1 score', value: stats.active_model.f1_score.toFixed(4) },
                  { label: 'Features / Classes', value: `${stats.active_model.feature_count} / ${stats.active_model.class_count}` },
                ].map(f => (
                  <div key={f.label}>
                    <div style={{ fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>{f.label}</div>
                    <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 24, color: BLACK }}>{f.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Attack dist + top features */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: BLACK, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                <BarChart2 style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
                Attack distribution
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(stats.attack_distribution)
                  .sort(([, a], [, b]) => b - a)
                  .map(([attack, count]) => (
                    <div key={attack}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: GRAY, marginBottom: 3 }}>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>{attack}</span>
                        <span>{count}</span>
                      </div>
                      <div style={{ height: 4, background: PARCH, borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ height: '100%', background: ORANGE, width: `${(count / maxAttackCount) * 100}%`, borderRadius: 2, opacity: 0.8, transition: 'width 0.6s ease' }} />
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 500, color: BLACK, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Brain style={{ width: 13, height: 13, color: '#a78bfa' }} aria-hidden="true" />
                Top predictive features
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {stats.top_features.slice(0, 10).map((f) => (
                  <div key={f.name}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: GRAY, marginBottom: 3 }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>{f.name}</span>
                      <span>{(f.importance * 100).toFixed(1)}%</span>
                    </div>
                    <div style={{ height: 4, background: PARCH, borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', background: '#a78bfa', width: `${f.importance * 100}%`, borderRadius: 2, transition: 'width 0.6s ease' }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Model registry */}
          {stats.registry.length > 1 && (
            <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', borderBottom: `1px solid ${BORDER}`, fontSize: 11, fontWeight: 500, color: BLACK }}>
                Model registry
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: PARCH }}>
                    {['Version', 'Trained', 'Accuracy', 'F1', 'Status'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500, borderBottom: `1px solid ${BORDER}` }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {stats.registry.map(m => (
                    <tr key={m.model_id} style={{ borderBottom: `1px solid ${BORDER}` }}
                      onMouseEnter={e => (e.currentTarget.style.background = PARCH)}
                      onMouseLeave={e => (e.currentTarget.style.background = '')}
                    >
                      <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BLACK }}>v{m.version}</td>
                      <td style={{ padding: '10px 14px', fontSize: 11, color: GRAY }}>{new Date(m.trained_at).toLocaleDateString()}</td>
                      <td style={{ padding: '10px 14px', fontSize: 11, color: BLACK }}>{(m.accuracy * 100).toFixed(2)}%</td>
                      <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BLACK }}>{m.f1_score.toFixed(4)}</td>
                      <td style={{ padding: '10px 14px' }}>
                        {m.is_active
                          ? <span style={{ fontSize: 10, padding: '2px 8px', background: 'rgba(58,122,80,0.08)', border: '1px solid rgba(58,122,80,0.3)', color: '#3a7a50', borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Active</span>
                          : <span style={{ fontSize: 10, color: GRAY }}>Archived</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '64px 0', gap: 12 }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', background: PARCH, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Brain style={{ width: 20, height: 20, color: GRAY, opacity: 0.5 }} aria-hidden="true" />
          </div>
          <p style={{ fontSize: 13, color: BLACK, fontWeight: 500 }}>No detection data yet</p>
          <p style={{ fontSize: 11, color: GRAY, textAlign: 'center', maxWidth: 320 }}>
            The detection engine is running, but no predictions have been recorded. Data will appear here once the model begins classifying traffic.
          </p>
        </div>
      )}
    </div>
  )
}
