/**
 * ThreatIntelPage — ML threat intelligence dashboard
 *
 * All chart data sourced from GET /api/v1/ml/metrics and GET /api/v1/ml/flows.
 * CICIDS_MITRE_MAPPING and ATTACK_IOC_PATTERNS are published MITRE ATT&CK taxonomy
 * reference data (not mock) and do not change at runtime.
 */
import { memo, useMemo, useState } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { Brain, Target, AlertTriangle, TrendingUp, ExternalLink, Activity } from 'lucide-react'
import { StatCard } from '@/components/ui/StatCard'
import { useMlFlows, useMlMetrics } from '@/hooks/useApi'
import { CICIDS_MITRE_MAPPING, ATTACK_IOC_PATTERNS } from '@/data/mitre'
import type { AttackType } from '@/types'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

// ---- Sub-components --------------------------------------------------------

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '8px 12px', fontSize: 11 }}>
      {payload.map((p: any) => (
        <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color ?? ORANGE }} />
          <span style={{ color: GRAY }}>{p.name}:</span>
          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: BLACK }}>
            {typeof p.value === 'number' ? p.value.toLocaleString() : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

function SkeletonBar() {
  return (
    <div style={{ height: 12, background: PARCH, borderRadius: 2, width: '70%', animation: 'pulse 1.5s ease-in-out infinite' }} />
  )
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px 0', gap: 8 }}>
      <Activity style={{ width: 20, height: 20, color: PARCH }} aria-hidden="true" />
      <p style={{ fontSize: 11, color: GRAY, textAlign: 'center' }}>{message}</p>
    </div>
  )
}

const IOCPanel = memo(function IOCPanel({ attackType }: { attackType: AttackType }) {
  const iocs  = ATTACK_IOC_PATTERNS[attackType]
  const mitre = CICIDS_MITRE_MAPPING[attackType]
  if (!iocs) return null
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Target style={{ width: 14, height: 14, color: ORANGE }} aria-hidden="true" />
        <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Attack Indicators</span>
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE, background: 'rgba(229,78,27,0.08)', border: `1px solid rgba(229,78,27,0.25)`, borderRadius: 2, padding: '1px 6px' }}>
          {attackType}
        </span>
      </div>
      <ul style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {iocs.map(ioc => (
          <li key={ioc} style={{ display: 'flex', alignItems: 'flex-start', gap: 6, fontSize: 11 }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: ORANGE, flexShrink: 0, marginTop: 5 }} />
            <span style={{ color: BLACK }}>{ioc}</span>
          </li>
        ))}
      </ul>
      {mitre && (
        <a
          href={mitre.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: ORANGE, textDecoration: 'none' }}
        >
          <ExternalLink style={{ width: 11, height: 11 }} aria-hidden="true" />
          {mitre.technique_id} — {mitre.name}
        </a>
      )}
    </div>
  )
})

// ---- Page ------------------------------------------------------------------

export default function ThreatIntelPage() {
  const [selectedAttack, setSelectedAttack] = useState<AttackType>('DoS Hulk')

  const { data: flows,     isLoading: flowsLoading,   isError: flowsError   } = useMlFlows()
  const { data: mlMetrics, isLoading: metricsLoading, isError: metricsError } = useMlMetrics()

  // KPI: overall model accuracy derived from FP analysis (live data when available)
  const overallAccuracy = useMemo(() => {
    const fp = mlMetrics?.false_positive_analysis
    if (!fp || fp.length === 0) return null
    const total   = fp.reduce((s, d) => s + d.tp + d.fp + d.fn, 0)
    const correct = fp.reduce((s, d) => s + d.tp, 0)
    return (correct / total * 100).toFixed(1)
  }, [mlMetrics])

  // KPI: average confidence across live flows
  const avgConfidence = useMemo(() => {
    if (!flows || flows.length === 0) return null
    return (flows.reduce((s, f) => s + f.confidence_score, 0) / flows.length * 100).toFixed(1)
  }, [flows])

  // Derived chart data from API
  const featureData  = mlMetrics?.feature_importance      ?? []
  const radarData    = mlMetrics?.per_class_confidence     ?? []
  const fpData       = mlMetrics?.false_positive_analysis  ?? []
  const tacticData   = mlMetrics?.tactic_distribution      ?? []

  // Reference counts from published MITRE mapping (stable taxonomy, not runtime data)
  const mitreTechCount  = Object.keys(CICIDS_MITRE_MAPPING).length
  const attackTypeCount = Object.keys(ATTACK_IOC_PATTERNS).length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
          Threat Intelligence
        </h2>
        <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
          ML-powered attack detection · MITRE ATT&amp;CK framework · false positive tracking
        </p>
      </div>

      {/* KPI stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        <StatCard
          label="Model Accuracy"
          value={metricsLoading ? '…' : metricsError ? '--' : overallAccuracy != null ? `${overallAccuracy}%` : '--'}
          sub={metricsError ? 'unavailable' : overallAccuracy != null ? 'live incident data' : 'no incidents yet'}
          icon={Brain} accent="orange"
        />
        <StatCard
          label="Avg Confidence"
          value={flowsLoading ? '…' : flowsError ? '--' : avgConfidence != null ? `${avgConfidence}%` : '--'}
          sub={flowsError ? 'unavailable' : avgConfidence != null ? 'live flows' : 'no flows yet'}
          icon={TrendingUp} accent="green"
        />
        <StatCard
          label="Attack Types"
          value={String(attackTypeCount)}
          sub="CICIDS2017 categories"
          icon={Target} accent="purple"
        />
        <StatCard
          label="MITRE Techniques"
          value={String(mitreTechCount)}
          sub="mapped to ATT&CK"
          icon={Target} accent="orange"
        />
      </div>

      {/* Radar + feature importance */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>

        {/* Per-class confidence radar */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Brain style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
            <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Per-Class Model Confidence</span>
            <span style={{ fontSize: 9, color: GRAY, marginLeft: 'auto' }}>from /api/v1/ml/metrics</span>
          </div>
          {metricsLoading ? (
            <div style={{ height: 240, background: PARCH, borderRadius: 4, animation: 'pulse 1.5s ease-in-out infinite' }} />
          ) : metricsError ? (
            <EmptyChart message="Metrics endpoint unavailable." />
          ) : radarData.length === 0 ? (
            <EmptyChart message="No per-class confidence data yet." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke={BORDER} />
                <PolarAngleAxis dataKey="subject" tick={{ fill: GRAY, fontSize: 10 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: GRAY, fontSize: 9 }} />
                <Radar name="Confidence %" dataKey="A" stroke={ORANGE} fill={ORANGE} fillOpacity={0.12} strokeWidth={2} />
                <Tooltip content={<ChartTooltip />} />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Feature importance */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <TrendingUp style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
            <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Feature Importance</span>
            <span style={{ fontSize: 10, color: GRAY, marginLeft: 'auto' }}>from /api/v1/ml/metrics</span>
          </div>
          {metricsLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[0,1,2,3,4,5,6,7].map(i => <SkeletonBar key={i} />)}
            </div>
          ) : metricsError ? (
            <EmptyChart message="Metrics endpoint unavailable." />
          ) : featureData.length === 0 ? (
            <EmptyChart message="No feature importance data yet." />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[...featureData].sort((a, b) => b.importance - a.importance).map(f => (
                <div key={f.feature} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
                  <span style={{ color: GRAY, width: 110, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {f.feature}
                  </span>
                  <div style={{ flex: 1, height: 4, background: PARCH, borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${f.importance * 100}%`, background: ORANGE, borderRadius: 2, opacity: 0.8 }} />
                  </div>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', color: ORANGE, width: 32, textAlign: 'right', fontSize: 10 }}>
                    {(f.importance * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* MITRE tactic distribution */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <Target style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
          <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>MITRE ATT&amp;CK Tactic Distribution</span>
          <span style={{ fontSize: 10, color: GRAY, marginLeft: 'auto' }}>live incident data</span>
        </div>
        {metricsLoading ? (
          <div style={{ height: 200, background: PARCH, borderRadius: 4, animation: 'pulse 1.5s ease-in-out infinite' }} />
        ) : metricsError ? (
          <EmptyChart message="Metrics endpoint unavailable." />
        ) : tacticData.length === 0 ? (
          <EmptyChart message="No incidents classified yet. Tactic distribution will appear once threats are detected." />
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(160, tacticData.length * 32)}>
            <BarChart data={tacticData} margin={{ top: 4, right: 4, bottom: 4, left: -10 }} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={BORDER} horizontal={false} />
              <XAxis type="number" tick={{ fill: GRAY, fontSize: 10 }} />
              <YAxis type="category" dataKey="tactic" tick={{ fill: GRAY, fontSize: 10 }} width={130} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {tacticData.map((entry, idx) => (
                  <Cell key={idx} fill={entry.color} opacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* False Positive Analysis table */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: `1px solid ${BORDER}`, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle style={{ width: 13, height: 13, color: '#d97706' }} aria-hidden="true" />
          <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>False Positive Analysis</span>
          <span style={{ fontSize: 10, color: GRAY, marginLeft: 'auto' }}>True Pos / False Pos / False Neg · live data</span>
        </div>
        {metricsLoading ? (
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[0,1,2,3].map(i => <SkeletonBar key={i} />)}
          </div>
        ) : metricsError ? (
          <div style={{ padding: '24px 16px', textAlign: 'center', fontSize: 11, color: GRAY }}>
            Metrics endpoint unavailable.
          </div>
        ) : fpData.length === 0 ? (
          <div style={{ padding: '24px 16px', textAlign: 'center', fontSize: 11, color: GRAY }}>
            No classified incidents yet. FP analysis will populate as threats are detected and classified.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: PARCH }}>
                {['Attack Type', 'True Pos', 'False Pos', 'False Neg', 'Precision', 'Recall'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500, borderBottom: `1px solid ${BORDER}` }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fpData.map((row, i) => {
                const precision = row.tp / (row.tp + row.fp)
                const recall    = row.tp / (row.tp + row.fn)
                return (
                  <tr
                    key={row.attack}
                    style={{ borderBottom: i < fpData.length - 1 ? `1px solid ${BORDER}` : 'none' }}
                    onMouseEnter={e => (e.currentTarget.style.background = PARCH)}
                    onMouseLeave={e => (e.currentTarget.style.background = '')}
                  >
                    <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BLACK }}>{row.attack}</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#3a7a50' }}>{row.tp.toLocaleString()}</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE  }}>{row.fp.toLocaleString()}</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#d97706' }}>{row.fn.toLocaleString()}</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE  }}>{(precision * 100).toFixed(1)}%</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#7c3aed' }}>{(recall * 100).toFixed(1)}%</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Live flows + IOC panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Brain style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
            <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Live Traffic Analysis</span>
          </div>

          {flowsLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[0, 1, 2, 3].map(i => (
                <div key={i} style={{ height: 56, background: PARCH, borderRadius: 4, animation: 'pulse 1.5s ease-in-out infinite' }} />
              ))}
            </div>
          )}

          {flowsError && (
            <EmptyChart message="Flow classification endpoint unavailable. Start the ML classifier to see live detections." />
          )}

          {!flowsLoading && !flowsError && (!flows || flows.length === 0) && (
            <EmptyChart message="No flow classifications yet. Flows will appear as network traffic is analysed." />
          )}

          {!flowsLoading && !flowsError && flows && flows.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {flows.map(flow => (
                <button
                  key={flow.flow_id}
                  onClick={() => setSelectedAttack(flow.attack_type as AttackType)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px',
                    border: selectedAttack === flow.attack_type ? `1px solid rgba(229,78,27,0.4)` : `1px solid ${BORDER}`,
                    borderRadius: 4, background: selectedAttack === flow.attack_type ? 'rgba(229,78,27,0.06)' : 'transparent',
                    cursor: 'pointer', textAlign: 'left', width: '100%', transition: 'all 0.12s',
                  }}
                  onMouseEnter={e => { if (selectedAttack !== flow.attack_type) (e.currentTarget as HTMLElement).style.background = PARCH }}
                  onMouseLeave={e => { if (selectedAttack !== flow.attack_type) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                >
                  <span style={{ width: 7, height: 7, borderRadius: '50%', flexShrink: 0, background: flow.attack_type === 'BENIGN' ? '#3a7a50' : ORANGE }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: ORANGE }}>{flow.attack_type}</span>
                      <span style={{ fontSize: 10, color: GRAY }}>{flow.src_ip}:{flow.src_port}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 8, fontSize: 9, fontFamily: 'JetBrains Mono, monospace', color: GRAY, marginTop: 2 }}>
                      <span>{flow.total_fwd_packets.toLocaleString()} fwd</span>
                      <span>{flow.total_bwd_packets.toLocaleString()} bwd</span>
                      <span>{flow.flow_bytes_per_sec.toLocaleString()} B/s</span>
                    </div>
                  </div>
                  <div style={{ flexShrink: 0, textAlign: 'right' }}>
                    <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 700, color: ORANGE }}>
                      {(flow.confidence_score * 100).toFixed(0)}%
                    </div>
                    <div style={{ fontSize: 9, color: GRAY }}>confidence</div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <IOCPanel attackType={selectedAttack} />

          {CICIDS_MITRE_MAPPING[selectedAttack] && (() => {
            const m = CICIDS_MITRE_MAPPING[selectedAttack]!
            return (
              <div style={{ background: 'rgba(124,58,237,0.04)', border: '1px solid rgba(124,58,237,0.2)', borderRadius: 4, padding: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: '#7c3aed', background: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.2)', borderRadius: 2, padding: '1px 7px' }}>
                    {m.technique_id}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>{m.name}</span>
                </div>
                <div style={{ fontSize: 11, color: GRAY, marginBottom: 4 }}>Tactic: {m.tactic}</div>
                <p style={{ fontSize: 11, color: GRAY, marginBottom: 10 }}>{m.description}</p>
                <div>
                  <div style={{ fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Mitigations</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {m.mitigations.map(mit => (
                      <span key={mit} style={{ fontSize: 10, padding: '2px 8px', border: `1px solid ${BORDER}`, borderRadius: 2, background: PARCH, color: GRAY }}>
                        {mit}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      </div>
    </div>
  )
}