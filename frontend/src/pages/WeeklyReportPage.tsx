/**
 * Weekly Security Report Page
 *
 * Displays a full preview of the automatically generated weekly report
 * pulled from live backend data, with a one-click PDF download.
 */
import { logger } from '@/lib/logger'
import {
  Download, RefreshCw, TrendingUp, TrendingDown, Minus,
  Shield, AlertTriangle, CheckCircle, FileText, Lock,
  BarChart2, Target,
} from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWeeklyReport } from '@/hooks/useApi'
import { getAccessToken } from '@/store/authStore'
import { downloadMockPdf } from '@/mocks/mockPdf'
import type { WeeklyReport } from '@/api/client'

// ── Design tokens ─────────────────────────────────────────────────────────────
const BLACK  = '#111111'
const ORANGE = '#e54e1b'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'
const BORDER = '#c8c2b8'
const GREEN  = '#22c55e'
const RED    = '#ef4444'
const AMBER  = '#f59e0b'

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function fmtShort(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function severityColor(s: string) {
  return s === 'critical' ? RED : s === 'high' ? ORANGE : s === 'medium' ? AMBER : GRAY
}

function priorityColor(p: string) {
  return p === 'critical' ? RED : p === 'high' ? ORANGE : p === 'medium' ? AMBER : GRAY
}

// ── Sub-components ────────────────────────────────────────────────────────────
function SectionHead({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, paddingBottom: 8, borderBottom: `1px solid ${BORDER}` }}>
      {icon}
      <span style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', color: BLACK }}>
        {title}
      </span>
    </div>
  )
}

function Card({ children, style: s }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16, ...s }}>
      {children}
    </div>
  )
}

function StatBox({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 4,
      padding: '14px 12px', textAlign: 'center',
    }}>
      <div style={{
        fontFamily: "'Bebas Neue', sans-serif",
        fontSize: 32, lineHeight: 1,
        color: color ?? BLACK,
      }}>
        {value}
      </div>
      <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: 4 }}>
        {label}
      </div>
    </div>
  )
}

function TrendBadge({ trend }: { trend: WeeklyReport['trend'] }) {
  const cfg = {
    improving: { icon: TrendingUp,   color: GREEN,  label: 'Improving' },
    stable:    { icon: Minus,        color: GRAY,   label: 'Stable'    },
    worsening: { icon: TrendingDown, color: RED,    label: 'Worsening' },
  }[trend]
  const Icon = cfg.icon
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      fontSize: 10, fontWeight: 600, color: cfg.color,
      background: `${cfg.color}15`, border: `1px solid ${cfg.color}40`,
      borderRadius: 2, padding: '3px 10px',
      fontFamily: 'JetBrains Mono, monospace',
    }}>
      <Icon style={{ width: 11, height: 11 }} />
      {cfg.label}
    </span>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function WeeklyReportPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, refetch, isFetching } = useWeeklyReport()
  const [downloading, setDownloading] = useState(false)
  const isMock = import.meta.env.VITE_MOCK === 'true'
  const mockFilename = `lbro-security-report-${new Date().toISOString().slice(0, 10)}.pdf`

  // Production-only download (mock uses a plain <a> link instead)
  const handleDownload = async () => {
    if (downloading) return
    setDownloading(true)
    try {
      const token = getAccessToken()
      const res = await fetch('/api/v1/reports/weekly/pdf', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = mockFilename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
    } catch (e) {
      logger.error('Weekly PDF download failed', { error: e instanceof Error ? e.message : String(e) })
      alert('PDF download failed. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  // ── Loading ─────────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ height: 48, background: PARCH, borderRadius: 4, width: 300 }} />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
          {[0,1,2,3].map(i => <div key={i} style={{ height: 80, background: PARCH, borderRadius: 4 }} />)}
        </div>
        {[1,2,3].map(i => <div key={i} style={{ height: 100, background: PARCH, borderRadius: 4 }} />)}
      </div>
    )
  }

  // ── Error ───────────────────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
          Weekly Report
        </h2>
        <Card>
          <div style={{ textAlign: 'center', padding: 24 }}>
            <AlertTriangle style={{ width: 32, height: 32, color: ORANGE, margin: '0 auto 12px' }} />
            <div style={{ fontSize: 14, color: BLACK, fontWeight: 500, marginBottom: 8 }}>Could not load report</div>
            <div style={{ fontSize: 12, color: GRAY, marginBottom: 16 }}>Backend connectivity issue or insufficient permissions.</div>
            <button
              onClick={() => refetch()}
              style={{ fontSize: 11, color: BLACK, border: `1px solid ${BORDER}`, padding: '6px 14px', borderRadius: 2, background: 'transparent', cursor: 'pointer' }}
            >
              Retry
            </button>
          </div>
        </Card>
      </div>
    )
  }

  const inc = data.incidents

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Page header ────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>
            Weekly Security Report
          </h2>
          <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
            {fmtShort(data.period_start)} – {fmt(data.period_end)} · Generated {fmt(data.generated_at)}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 11, color: GRAY, border: `1px solid ${BORDER}`,
              padding: '7px 12px', borderRadius: 2, background: 'transparent',
              cursor: isFetching ? 'default' : 'pointer',
              opacity: isFetching ? 0.5 : 1,
              textTransform: 'uppercase', letterSpacing: '0.06em',
            }}
          >
            <RefreshCw style={{ width: 12, height: 12, animation: isFetching ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
          {isMock ? (
            <button
              onClick={() => downloadMockPdf(mockFilename)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                fontSize: 11, color: '#fff', border: 'none',
                padding: '7px 14px', borderRadius: 2,
                background: ORANGE, cursor: 'pointer',
                textTransform: 'uppercase', letterSpacing: '0.06em',
                fontWeight: 600,
              }}
            >
              <Download style={{ width: 12, height: 12 }} />
              Download PDF
            </button>
          ) : (
            <button
              onClick={handleDownload}
              disabled={downloading}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                fontSize: 11, color: '#fff', border: 'none',
                padding: '7px 14px', borderRadius: 2,
                background: ORANGE, cursor: downloading ? 'wait' : 'pointer',
                textTransform: 'uppercase', letterSpacing: '0.06em',
                fontWeight: 600, opacity: downloading ? 0.7 : 1,
              }}
            >
              <Download style={{ width: 12, height: 12 }} />
              {downloading ? 'Generating…' : 'Download PDF'}
            </button>
          )}
        </div>
      </div>

      {/* ── Score + Executive Summary ───────────────────────────────────────── */}
      <div style={{
        display: 'grid', gridTemplateColumns: '200px 1fr', gap: 0,
        border: `1px solid ${BORDER}`, borderTop: `3px solid ${data.security_color}`,
        borderRadius: 4, overflow: 'hidden',
      }}>
        {/* Score block */}
        <div style={{
          background: PARCH, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', padding: '24px 16px',
          borderRight: `1px solid ${BORDER}`,
        }}>
          <div style={{
            fontFamily: "'Bebas Neue', sans-serif",
            fontSize: 72, lineHeight: 1,
            color: data.security_color,
          }}>
            {data.security_score}
          </div>
          <div style={{
            fontFamily: "'Bebas Neue', sans-serif",
            fontSize: 18, color: data.security_color,
            letterSpacing: '0.1em', marginTop: 2,
          }}>
            Grade {data.security_grade}
          </div>
          <div style={{ fontSize: 10, color: GRAY, marginTop: 6, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            {data.security_status}
          </div>
          <div style={{ marginTop: 12 }}>
            <TrendBadge trend={data.trend} />
          </div>
        </div>

        {/* Summary block */}
        <div style={{ background: CREAM, padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Shield style={{ width: 16, height: 16, color: ORANGE }} />
            <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 20, color: BLACK, letterSpacing: '0.04em' }}>
              Executive Summary
            </span>
          </div>
          <p style={{ fontSize: 13, color: BLACK, lineHeight: 1.7, marginBottom: 12 }}>
            {data.executive_summary}
          </p>
          <p style={{ fontSize: 11, color: GRAY, lineHeight: 1.6 }}>
            {data.trend_reason}
          </p>
        </div>
      </div>

      {/* ── 4-stat overview ────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        <StatBox label="New This Week"    value={inc.new_this_week}    />
        <StatBox label="Resolved"         value={inc.closed_this_week} color={GREEN} />
        <StatBox label="Open Critical"    value={inc.open_critical}    color={inc.open_critical > 0 ? RED : BLACK} />
        <StatBox label="Total Incidents"  value={data.total_incidents} />
      </div>

      {/* ── Attack types + Targeted ports ──────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Top attack types */}
        <Card>
          <SectionHead icon={<Target style={{ width: 13, height: 13, color: ORANGE }} />} title="Top Attack Types" />
          {inc.top_attack_types.length === 0 ? (
            <p style={{ fontSize: 11, color: GRAY }}>No attack data this period.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {inc.top_attack_types.map((a, i) => {
                const max = inc.top_attack_types[0].count
                const pct = Math.round((a.count / max) * 100)
                return (
                  <div key={i}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{ fontSize: 11, color: BLACK, fontFamily: 'JetBrains Mono, monospace' }}>{a.category}</span>
                      <span style={{ fontSize: 11, color: ORANGE, fontWeight: 700 }}>{a.count}</span>
                    </div>
                    <div style={{ height: 4, background: PARCH, borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: ORANGE, borderRadius: 2 }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>

        {/* Most targeted ports */}
        <Card>
          <SectionHead icon={<BarChart2 style={{ width: 13, height: 13, color: ORANGE }} />} title="Most Targeted Ports" />
          {inc.most_targeted_ports.length === 0 ? (
            <p style={{ fontSize: 11, color: GRAY }}>No port data this period.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {inc.most_targeted_ports.map((p, i) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'space-between',
                  padding: '6px 0', borderBottom: `1px solid ${BORDER}`,
                }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: BLACK }}>
                    :{p.port}
                  </span>
                  <span style={{ fontSize: 11, color: ORANGE, fontWeight: 600 }}>{p.count} hits</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ── Open Critical Incidents ─────────────────────────────────────────── */}
      {inc.critical_incidents.length > 0 && (
        <Card>
          <SectionHead icon={<AlertTriangle style={{ width: 13, height: 13, color: RED }} />} title="Open Critical Incidents" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {inc.critical_incidents.map(ci => (
              <a
                key={ci.id}
                href={`/incidents/${ci.id}`}
                onClick={e => { e.preventDefault(); navigate(`/incidents/${ci.id}`) }}
                style={{ textDecoration: 'none' }}
              >
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 14px',
                  background: 'rgba(239,68,68,0.04)',
                  border: `1px solid rgba(239,68,68,0.2)`,
                  borderLeft: `3px solid ${RED}`,
                  borderRadius: 3, cursor: 'pointer',
                }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.08)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.04)')}
                >
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: BLACK, marginBottom: 2 }}>{ci.title}</div>
                    <div style={{ fontSize: 10, color: GRAY }}>
                      {ci.status.toUpperCase()} · Opened {fmtShort(ci.created_at)}
                    </div>
                  </div>
                  <span style={{
                    fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700,
                    color: RED, background: 'rgba(239,68,68,0.1)',
                    border: '1px solid rgba(239,68,68,0.3)',
                    borderRadius: 2, padding: '2px 8px',
                  }}>
                    CRITICAL
                  </span>
                </div>
              </a>
            ))}
          </div>
        </Card>
      )}

      {/* ── Resolved Incidents ──────────────────────────────────────────────── */}
      {inc.resolved_incidents.length > 0 && (
        <Card>
          <SectionHead icon={<CheckCircle style={{ width: 13, height: 13, color: GREEN }} />} title="Resolved This Week" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {inc.resolved_incidents.map(ri => (
              <div key={ri.id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 14px',
                borderLeft: `3px solid ${GREEN}`,
                background: 'rgba(34,197,94,0.04)',
                borderRadius: 3,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <CheckCircle style={{ width: 12, height: 12, color: GREEN, flexShrink: 0 }} />
                  <span style={{ fontSize: 11, color: BLACK }}>{ri.title}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 10, color: severityColor(ri.severity), fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase' }}>
                    {ri.severity}
                  </span>
                  <span style={{ fontSize: 10, color: GRAY }}>{fmtShort(ri.resolved_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Evidence + Compliance ───────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <Card>
          <SectionHead icon={<Lock style={{ width: 13, height: 13, color: ORANGE }} />} title="Evidence Vault" />
          <div style={{ textAlign: 'center', padding: '8px 0' }}>
            <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, lineHeight: 1 }}>
              {data.evidence_count}
            </div>
            <div style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
              evidence files stored with tamper-proof records
            </div>
          </div>
        </Card>

        <Card>
          <SectionHead icon={<FileText style={{ width: 13, height: 13, color: ORANGE }} />} title="Compliance" />
          <div style={{ textAlign: 'center', padding: '8px 0' }}>
            <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: data.compliance_met === data.compliance_total && data.compliance_total > 0 ? GREEN : AMBER, lineHeight: 1 }}>
              {data.compliance_total > 0
                ? `${Math.round(data.compliance_met / data.compliance_total * 100)}%`
                : '—'}
            </div>
            <div style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
              {data.compliance_met} of {data.compliance_total} requirements met
            </div>
          </div>
        </Card>
      </div>

      {/* ── Recommendations ─────────────────────────────────────────────────── */}
      {data.top_recommendations.length > 0 && (
        <Card>
          <SectionHead icon={<TrendingUp style={{ width: 13, height: 13, color: ORANGE }} />} title="Recommendations" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.top_recommendations.map((rec, i) => {
              const pColor = priorityColor(rec.priority)
              return (
                <div key={i} style={{
                  display: 'flex', gap: 14, alignItems: 'flex-start',
                  padding: '12px 14px',
                  border: `1px solid ${BORDER}`,
                  borderLeft: `3px solid ${pColor}`,
                  borderRadius: 3,
                  background: `${pColor}05`,
                }}>
                  <div style={{
                    width: 22, height: 22, borderRadius: '50%',
                    background: pColor, color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontWeight: 700, flexShrink: 0,
                  }}>
                    {i + 1}
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 9, fontWeight: 700, textTransform: 'uppercase',
                        color: pColor,
                      }}>
                        {rec.priority}
                      </span>
                      <span style={{ fontSize: 12, fontWeight: 600, color: BLACK }}>{rec.title}</span>
                    </div>
                    <div style={{ fontSize: 11, color: GRAY, lineHeight: 1.6 }}>{rec.detail}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* Spin keyframe */}
      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
