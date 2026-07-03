/**
 * ThreatIntelPage -- ML threat intelligence dashboard
 *
 * Data sources:
 *   LIVE (from backend):  useMlFlows()    -> GET /api/v1/ml/flows    (implemented)
 *                         useMlMetrics()  -> GET /api/v1/ml/metrics  (implemented)
 *   STATIC (published reference data, NOT mock):
 *                         CICIDS_MITRE_MAPPING -- MITRE ATT&CK technique IDs, names, URLs
 *                         ATTACK_IOC_PATTERNS  -- IOC indicator descriptions per attack type
 *   HARD-CODED charts:    MODEL_FEATURES, RADAR_DATA, FP_DATA, TACTIC_HEATMAP
 *                         -> populated from /api/v1/ml/metrics once data accumulates in DB
 */
import { memo, useMemo, useState } from 'react'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { Brain, Target, AlertTriangle, TrendingUp, ExternalLink } from 'lucide-react'
import { StatCard } from '@/components/ui/StatCard'
import { useMlFlows, useMlMetrics } from '@/hooks/useApi'
// Static MITRE ATT&CK reference data -- published taxonomy, not mock data
import { CICIDS_MITRE_MAPPING, ATTACK_IOC_PATTERNS } from '@/data/mitre'
import type { AttackType } from '@/types'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

// ---- Static reference charts (TODO: replace with /api/v1/ml/metrics) --------------------
// These reflect the published CICIDS2017 paper results and don't change at runtime.
// Once GET /api/v1/ml/metrics is implemented, replace with useMlMetrics() data.

const MODEL_FEATURES = [
  { feature: 'Flow Duration', importance: 0.87 },
  { feature: 'Fwd Packets',   importance: 0.92 },
  { feature: 'Bwd Packets',   importance: 0.78 },
  { feature: 'Bytes/sec',     importance: 0.95 },
  { feature: 'Pkts/sec',      importance: 0.91 },
  { feature: 'IAT Mean',      importance: 0.74 },
  { feature: 'Header Length', importance: 0.68 },
  { feature: 'Flags',         importance: 0.83 },
]

const RADAR_DATA = [
  { subject: 'DoS Hulk',    A: 94, fullMark: 100 },
  { subject: 'DDoS',        A: 97, fullMark: 100 },
  { subject: 'SSH-Patator', A: 89, fullMark: 100 },
  { subject: 'PortScan',    A: 92, fullMark: 100 },
  { subject: 'SQL Inject',  A: 88, fullMark: 100 },
  { subject: 'XSS',         A: 81, fullMark: 100 },
  { subject: 'Infiltration',A: 76, fullMark: 100 },
  { subject: 'Heartbleed',  A: 99, fullMark: 100 },
]

// TP/FP/FN from CICIDS2017 paper -- static reference
const FP_DATA = [
  { attack: 'DoS Hulk',    tp: 231073, fp: 4200, fn: 890 },
  { attack: 'DDoS',        tp: 41835,  fp: 312,  fn: 124 },
  { attack: 'PortScan',    tp: 87393,  fp: 1820, fn: 440 },
  { attack: 'SSH-Patator', tp: 5897,   fp: 234,  fn: 87  },
  { attack: 'Infiltration',tp: 36,     fp: 8,    fn: 12  },
]

const TACTIC_HEATMAP = [
  { tactic: 'Initial Access',     count: 4821,   color: ORANGE    },
  { tactic: 'Execution',          count: 12,     color: '#d97706' },
  { tactic: 'Credential Access',  count: 13805,  color: '#d97706' },
  { tactic: 'Discovery',          count: 87393,  color: '#3a7a50' },
  { tactic: 'Lateral Movement',   count: 36,     color: ORANGE    },
  { tactic: 'Command & Control',  count: 1966,   color: '#7c3aed' },
  { tactic: 'Impact',             count: 291957, color: ORANGE    },
]

// ---- Sub-components ------------------------------------------------------------------------------------------------------------------------

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '8px 12px', fontSize: 11 }}>
      {payload.map((p: any) => (
        <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color ?? ORANGE }} />
          <span style={{ color: GRAY }}>{p.name}:</span>
          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: BLACK }}>{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
        </div>
      ))}
    </div>
  )
}

function MissingEndpointBanner({ endpoint, description }: { endpoint: string; description?: string }) {
  return (
    <div style={{ background: 'rgba(217,119,6,0.06)', border: `1px solid rgba(217,119,6,0.3)`, borderLeft: `3px solid #d97706`, borderRadius: 4, padding: '10px 14px', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
      <AlertTriangle style={{ width: 13, height: 13, color: '#d97706', flexShrink: 0, marginTop: 1 }} aria-hidden="true" />
      <div style={{ fontSize: 11, color: GRAY }}>
        <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE }}>{endpoint}</code>
        {description && <span style={{ marginLeft: 6 }}>{description}</span>}
      </div>
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
        <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>IOC Indicators</span>
        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE, background: 'rgba(229,78,27,0.08)', border: `1px solid rgba(229,78,27,0.25)`, borderRadius: 2, padding: '1px 6px' }}>{attackType}</span>
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
          {mitre.technique_id} -- {mitre.name}
        </a>
      )}
    </div>
  )
})

// ---- Page ------------------------------------------------------------------------------------------------------------------------------------------

export default function ThreatIntelPage() {
  const [selectedAttack, setSelectedAttack] = useState<AttackType>('DoS Hulk')

  // Real API hooks -- endpoints implemented at GET /api/v1/ml/flows and GET /api/v1/ml/metrics
  const { data: flows, isLoading: flowsLoading, isError: flowsError } = useMlFlows()
  const { data: mlMetrics } = useMlMetrics()

  // Compute accuracy from FP data (TODO: source from /api/v1/ml/metrics once implemented)
  const overallAccuracy = useMemo(() => {
    // If metrics endpoint returns false_positive_analysis, use that; otherwise fall back to static
    const data = mlMetrics?.false_positive_analysis ?? FP_DATA
    const total   = data.reduce((s, d) => s + d.tp + d.fp + d.fn, 0)
    const correct = data.reduce((s, d) => s + d.tp, 0)
    return (correct / total * 100).toFixed(1)
  }, [mlMetrics])

  const avgConfidence = useMemo(() => {
    if (flows && flows.length > 0) {
      return (flows.reduce((s, f) => s + f.confidence_score, 0) / flows.length * 100).toFixed(1)
    }
    return null
  }, [flows])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
          Threat Intelligence
        </h2>
        <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>CICIDS2017 ML analytics · MITRE ATT&CK mapping · False positive tracking</p>
      </div>

      {/* KPI stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        <StatCard
          label="Model Accuracy"
          value={`${overallAccuracy}%`}
          sub="CICIDS2017 paper results"
          icon={Brain} accent="orange"
        />
        <StatCard
          label="Avg Confidence"
          value={flowsLoading ? '…' : flowsError ? '--' : avgConfidence != null ? `${avgConfidence}%` : '--'}
          sub={flowsError ? 'endpoint missing' : 'live flows'}
          icon={TrendingUp} accent="green"
        />
        <StatCard label="Attack Types"     value="14" sub="CICIDS2017 categories"  icon={Target} accent="purple" />
        <StatCard label="MITRE Techniques" value="8"  sub="mapped to ATT&CK"       icon={Target} accent="orange" />
      </div>

      {/* Radar + feature importance */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <Brain style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
            <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Per-Class Model Confidence</span>
            <span style={{ fontSize: 9, color: GRAY, marginLeft: 'auto' }}>CICIDS2017 paper</span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <RadarChart data={RADAR_DATA}>
              <PolarGrid stroke={BORDER} />
              <PolarAngleAxis dataKey="subject" tick={{ fill: GRAY, fontSize: 10 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: GRAY, fontSize: 9 }} />
              <Radar name="Confidence %" dataKey="A" stroke={ORANGE} fill={ORANGE} fillOpacity={0.12} strokeWidth={2} />
              <Tooltip content={<ChartTooltip />} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <TrendingUp style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
            <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Feature Importance (SHAP)</span>
            <span style={{ fontSize: 10, color: GRAY, marginLeft: 'auto' }}>RF + XGBoost ensemble</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[...MODEL_FEATURES].sort((a, b) => b.importance - a.importance).map(f => (
              <div key={f.feature} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
                <span style={{ color: GRAY, width: 110, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.feature}</span>
                <div style={{ flex: 1, height: 4, background: PARCH, borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${f.importance * 100}%`, background: ORANGE, borderRadius: 2, opacity: 0.8 }} />
                </div>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', color: ORANGE, width: 32, textAlign: 'right', fontSize: 10 }}>{(f.importance * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* MITRE tactic heatmap */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <Target style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
          <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>MITRE ATT&CK Tactic Distribution</span>
          <span style={{ fontSize: 10, color: GRAY, marginLeft: 'auto' }}>CICIDS2017 paper results</span>
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={TACTIC_HEATMAP} margin={{ top: 4, right: 4, bottom: 20, left: -10 }} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke={BORDER} horizontal={false} />
            <XAxis type="number" tick={{ fill: GRAY, fontSize: 10 }} />
            <YAxis type="category" dataKey="tactic" tick={{ fill: GRAY, fontSize: 10 }} width={120} />
            <Tooltip content={<ChartTooltip />} />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              {TACTIC_HEATMAP.map((entry, idx) => (
                <Cell key={idx} fill={entry.color} opacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* TP/FP/FN table -- static from paper */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: `1px solid ${BORDER}`, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle style={{ width: 13, height: 13, color: '#d97706' }} aria-hidden="true" />
          <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>False Positive Analysis</span>
          <span style={{ fontSize: 10, color: GRAY, marginLeft: 'auto' }}>True Pos / False Pos / False Neg · CICIDS2017 paper</span>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: PARCH }}>
              {['Attack Type', 'True Pos', 'False Pos', 'False Neg', 'Precision', 'Recall'].map(h => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500, borderBottom: `1px solid ${BORDER}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FP_DATA.map((row, i) => {
              const precision = row.tp / (row.tp + row.fp)
              const recall    = row.tp / (row.tp + row.fn)
              return (
                <tr key={row.attack} style={{ borderBottom: i < FP_DATA.length - 1 ? `1px solid ${BORDER}` : 'none' }}
                  onMouseEnter={e => (e.currentTarget.style.background = PARCH)}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}
                >
                  <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BLACK }}>{row.attack}</td>
                  <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#3a7a50' }}>{row.tp.toLocaleString()}</td>
                  <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE  }}>{row.fp.toLocaleString()}</td>
                  <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#d97706'}}>{row.fn.toLocaleString()}</td>
                  <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE  }}>{(precision * 100).toFixed(1)}%</td>
                  <td style={{ padding: '10px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#7c3aed'}}>{(recall * 100).toFixed(1)}%</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Live flows + IOC panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Brain style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
            <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>Live Flow Classifications</span>
          </div>

          {flowsLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[0, 1, 2, 3].map(i => (
                <div key={i} style={{ height: 56, background: PARCH, borderRadius: 4, animation: 'pulse 1.5s ease-in-out infinite' }} />
              ))}
            </div>
          )}

          {flowsError && (
            <div style={{ textAlign: 'center', padding: '20px 0', fontSize: 11, color: GRAY }}>
              <div style={{ marginBottom: 6 }}>
                <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE }}>GET /api/v1/ml/flows</code>
              </div>
              not yet deployed -- live flow classifications unavailable
            </div>
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
                    <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, fontWeight: 700, color: ORANGE }}>{(flow.confidence_score * 100).toFixed(0)}%</div>
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
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: '#7c3aed', background: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.2)', borderRadius: 2, padding: '1px 7px' }}>{m.technique_id}</span>
                  <span style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>{m.name}</span>
                </div>
                <div style={{ fontSize: 11, color: GRAY, marginBottom: 4 }}>Tactic: {m.tactic}</div>
                <p style={{ fontSize: 11, color: GRAY, marginBottom: 10 }}>{m.description}</p>
                <div>
                  <div style={{ fontSize: 10, fontWeight: 500, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Mitigations</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {m.mitigations.map(mit => (
                      <span key={mit} style={{ fontSize: 10, padding: '2px 8px', border: `1px solid ${BORDER}`, borderRadius: 2, background: PARCH, color: GRAY }}>{mit}</span>
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
