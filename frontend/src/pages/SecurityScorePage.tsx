/**
 * Security Score Page
 *
 * Developer-first security posture view. Turns raw backend data into a
 * plain-English score with grade, color, positive/negative factors, and
 * ranked recommendations — no security jargon required.
 */
import { ShieldCheck, TrendingUp, TrendingDown, ArrowRight, RefreshCw, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import { useSecurityScore } from '@/hooks/useApi'
import type { ScoreFactor, ScoreRecommendation } from '@/api/client'

// ── Design tokens (match rest of app) ────────────────────────────────────────
const BLACK  = '#111111'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'
const BORDER = '#c8c2b8'
const ORANGE = '#e54e1b'

// ── Helpers ───────────────────────────────────────────────────────────────────
function priorityColor(p: ScoreRecommendation['priority']): string {
  return p === 'critical' ? '#ef4444'
       : p === 'high'     ? ORANGE
       : p === 'medium'   ? '#f59e0b'
       : '#6b6560'
}

function priorityLabel(p: ScoreRecommendation['priority']): string {
  return p === 'critical' ? 'Critical'
       : p === 'high'     ? 'High'
       : p === 'medium'   ? 'Medium'
       : 'Low'
}

// ── Score ring SVG ────────────────────────────────────────────────────────────
function ScoreRing({ score, color, grade }: { score: number; color: string; grade: string }) {
  const R = 72
  const cx = 90
  const cy = 90
  const circumference = 2 * Math.PI * R
  const progress = (score / 100) * circumference
  const gap = circumference - progress

  return (
    <svg width={180} height={180} viewBox="0 0 180 180" aria-label={`Security score ${score} out of 100`}>
      {/* Track */}
      <circle
        cx={cx} cy={cy} r={R}
        fill="none"
        stroke={PARCH}
        strokeWidth={12}
      />
      {/* Progress arc */}
      <circle
        cx={cx} cy={cy} r={R}
        fill="none"
        stroke={color}
        strokeWidth={12}
        strokeLinecap="round"
        strokeDasharray={`${progress} ${gap}`}
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: 'stroke-dasharray 0.6s ease' }}
      />
      {/* Score number */}
      <text
        x={cx} y={cy - 8}
        textAnchor="middle"
        dominantBaseline="middle"
        style={{
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: 42,
          fill: BLACK,
          letterSpacing: '0.02em',
        }}
      >
        {score}
      </text>
      {/* Grade */}
      <text
        x={cx} y={cy + 28}
        textAnchor="middle"
        dominantBaseline="middle"
        style={{
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: 22,
          fill: color,
          letterSpacing: '0.1em',
        }}
      >
        {grade}
      </text>
    </svg>
  )
}

// ── Factor row ────────────────────────────────────────────────────────────────
function FactorRow({ factor }: { factor: ScoreFactor }) {
  const isPositive = factor.impact === 'positive'
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 0', borderBottom: `1px solid ${BORDER}` }}>
      <div style={{ marginTop: 2, flexShrink: 0 }}>
        {isPositive
          ? <CheckCircle style={{ width: 14, height: 14, color: '#22c55e' }} />
          : <TrendingDown style={{ width: 14, height: 14, color: ORANGE }} />
        }
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>{factor.label}</div>
        <div style={{ fontSize: 11, color: GRAY, marginTop: 2, lineHeight: 1.5 }}>{factor.detail}</div>
      </div>
      <div style={{
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 11,
        fontWeight: 700,
        color: isPositive ? '#22c55e' : ORANGE,
        flexShrink: 0,
        marginTop: 2,
      }}>
        {isPositive ? '+' : '−'}
      </div>
    </div>
  )
}

// ── Recommendation card ───────────────────────────────────────────────────────
function RecommendationCard({ rec, index }: { rec: ScoreRecommendation; index: number }) {
  const pColor = priorityColor(rec.priority)
  return (
    <div style={{
      background: CREAM,
      border: `1px solid ${BORDER}`,
      borderLeft: `3px solid ${pColor}`,
      borderRadius: 4,
      padding: '14px 16px',
      display: 'flex',
      alignItems: 'flex-start',
      gap: 14,
    }}>
      {/* Index badge */}
      <div style={{
        width: 22, height: 22, borderRadius: '50%',
        background: pColor, color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700, flexShrink: 0, marginTop: 1,
      }}>
        {index + 1}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
          <span style={{
            fontSize: 10, fontWeight: 600, textTransform: 'uppercase',
            letterSpacing: '0.08em', color: pColor,
            fontFamily: 'JetBrains Mono, monospace',
          }}>
            {priorityLabel(rec.priority)}
          </span>
          <span style={{ fontSize: 12, fontWeight: 600, color: BLACK }}>{rec.title}</span>
        </div>
        <div style={{ fontSize: 11, color: GRAY, lineHeight: 1.6 }}>{rec.detail}</div>
      </div>

      <ArrowRight style={{ width: 12, height: 12, color: GRAY, flexShrink: 0, marginTop: 4 }} />
    </div>
  )
}

// ── Data snapshot row ─────────────────────────────────────────────────────────
function SnapshotItem({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: `1px solid ${BORDER}` }}>
      <span style={{ fontSize: 11, color: GRAY }}>{label}</span>
      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12, fontWeight: 600, color: BLACK }}>{value}</span>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function SecurityScorePage() {
  const { data, isLoading, isError, refetch, isFetching, dataUpdatedAt } = useSecurityScore()

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null

  // ── Loading skeleton ──────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div>
          <div style={{ height: 48, background: PARCH, borderRadius: 4, width: 280, marginBottom: 8 }} />
          <div style={{ height: 12, background: PARCH, borderRadius: 4, width: 200 }} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 20 }}>
          <div style={{ height: 240, background: PARCH, borderRadius: 4 }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[1,2,3,4].map(i => <div key={i} style={{ height: 56, background: PARCH, borderRadius: 4 }} />)}
          </div>
        </div>
      </div>
    )
  }

  // ── Error state ───────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div>
          <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>Security Score</h2>
          <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>How secure is your app right now?</p>
        </div>
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 24, textAlign: 'center' }}>
          <AlertTriangle style={{ width: 32, height: 32, color: ORANGE, margin: '0 auto 12px' }} />
          <div style={{ fontSize: 14, color: BLACK, fontWeight: 500, marginBottom: 6 }}>Could not load security score</div>
          <div style={{ fontSize: 12, color: GRAY, marginBottom: 16 }}>Check that the backend is running and you are signed in with the right account.</div>
          <button
            onClick={() => refetch()}
            style={{ fontSize: 11, color: BLACK, border: `1px solid ${BORDER}`, padding: '6px 14px', borderRadius: 2, background: 'transparent', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const { score, color, status, summary, grade, factors, recommendations, data_snapshot } = data

  const snapshotLabels: Record<string, string> = {
    open_critical_incidents: 'Open critical incidents',
    open_high_incidents:     'Open high incidents',
    open_medium_low_incidents: 'Open medium/low incidents',
    total_users:             'Total users',
    users_without_mfa:       'Users without MFA',
    users_with_failed_logins:'Users with failed login attempts',
    locked_users:            'Accounts currently locked',
    overdue_compliance:      'Overdue compliance items',
    recent_403s_24h:         'Forbidden-access attempts (24h)',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
            Security Score
          </h2>
          <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
            Your security health score — calculated from live data, updated every minute
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            fontSize: 11, color: GRAY, border: `1px solid ${BORDER}`,
            padding: '6px 12px', borderRadius: 2, background: 'transparent',
            cursor: isFetching ? 'default' : 'pointer',
            textTransform: 'uppercase', letterSpacing: '0.06em',
            opacity: isFetching ? 0.5 : 1,
          }}
        >
          <RefreshCw style={{ width: 12, height: 12, animation: isFetching ? 'spin 1s linear infinite' : 'none' }} />
          {isFetching ? 'Recalculating...' : 'Recalculate'}
        </button>
      </div>

      {/* Score + Summary */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '220px 1fr',
        gap: 20,
        background: CREAM,
        border: `1px solid ${BORDER}`,
        borderTop: `3px solid ${color}`,
        borderRadius: 4,
        padding: 24,
        alignItems: 'center',
      }}>
        {/* Ring */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <ScoreRing score={score} color={color} grade={grade} />
          <div style={{
            fontSize: 12, fontWeight: 600, color,
            textTransform: 'uppercase', letterSpacing: '0.1em',
            fontFamily: 'JetBrains Mono, monospace',
          }}>
            {status}
          </div>
          {lastUpdated && (
            <div style={{ fontSize: 10, color: GRAY }}>Updated {lastUpdated}</div>
          )}
        </div>

        {/* Summary */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <ShieldCheck style={{ width: 18, height: 18, color }} />
            <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 22, color: BLACK, letterSpacing: '0.04em' }}>
              What this means for you
            </span>
          </div>
          <p style={{ fontSize: 13, color: BLACK, lineHeight: 1.7, marginBottom: 16 }}>{summary}</p>

          {/* Quick stats */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {[
              { label: 'Open Critical', value: data_snapshot.open_critical_incidents, bad: true },
              { label: 'Without MFA',   value: data_snapshot.users_without_mfa, bad: true },
              { label: 'Overdue Rules', value: data_snapshot.overdue_compliance, bad: true },
              { label: 'Auth Attacks (24h)', value: data_snapshot.recent_403s_24h, bad: Number(data_snapshot.recent_403s_24h) > 50 },
            ].map(({ label, value, bad }) => (
              <div key={label} style={{
                background: bad && Number(value) > 0 ? 'rgba(229,78,27,0.06)' : PARCH,
                border: `1px solid ${bad && Number(value) > 0 ? 'rgba(229,78,27,0.25)' : BORDER}`,
                borderRadius: 4, padding: '8px 14px', textAlign: 'center', minWidth: 80,
              }}>
                <div style={{
                  fontFamily: "'Bebas Neue', sans-serif",
                  fontSize: 26,
                  color: bad && Number(value) > 0 ? ORANGE : BLACK,
                  lineHeight: 1,
                }}>
                  {value}
                </div>
                <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 3 }}>
                  {label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <TrendingUp style={{ width: 15, height: 15, color: ORANGE }} />
            <h3 style={{ fontSize: 13, fontWeight: 600, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              How to improve your score
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recommendations.map((rec, i) => (
              <RecommendationCard key={i} rec={rec} index={i} />
            ))}
          </div>
        </div>
      )}

      {/* Factors */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Positive */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <CheckCircle style={{ width: 14, height: 14, color: '#22c55e' }} />
            <h3 style={{ fontSize: 12, fontWeight: 600, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Working in your favour
            </h3>
          </div>
          <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '4px 16px' }}>
            {factors.filter(f => f.impact === 'positive').length === 0
              ? <p style={{ fontSize: 11, color: GRAY, padding: '12px 0' }}>No positive factors detected yet.</p>
              : factors.filter(f => f.impact === 'positive').map((f, i) => <FactorRow key={i} factor={f} />)
            }
          </div>
        </div>

        {/* Negative */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <AlertTriangle style={{ width: 14, height: 14, color: ORANGE }} />
            <h3 style={{ fontSize: 12, fontWeight: 600, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Reducing your score
            </h3>
          </div>
          <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '4px 16px' }}>
            {factors.filter(f => f.impact === 'negative').length === 0
              ? <p style={{ fontSize: 11, color: '#22c55e', padding: '12px 0' }}>No negative factors — great job!</p>
              : factors.filter(f => f.impact === 'negative').map((f, i) => <FactorRow key={i} factor={f} />)
            }
          </div>
        </div>
      </div>

      {/* Data snapshot */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <Info style={{ width: 14, height: 14, color: GRAY }} />
          <h3 style={{ fontSize: 12, fontWeight: 600, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Data used to calculate this score
          </h3>
        </div>
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '4px 16px' }}>
          {Object.entries(data_snapshot).map(([key, value]) => (
            <SnapshotItem key={key} label={snapshotLabels[key] ?? key} value={value} />
          ))}
        </div>
        <p style={{ fontSize: 10, color: GRAY, marginTop: 8 }}>
          Score recalculates automatically every 60 seconds from live database state.
        </p>
      </div>

      {/* Spin animation for refresh icon */}
      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
