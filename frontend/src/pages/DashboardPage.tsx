/**
 * Application Security Dashboard
 *
 * Displays a personalised greeting, overall security health, key metrics,
 * recent activity timeline, top threat, and recommended actions.
 * All data sourced from real backend APIs — no mock data.
 */
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ShieldCheck, AlertTriangle, ArrowRight,
  Activity, Clock, Zap, Shield, ChevronRight, Sparkles, Loader2,
} from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useIncidents, useDashboardSummary, useSecurityScore } from '@/hooks/useApi'
import { useAuthStore } from '@/store/authStore'
import { SeverityBadge } from '@/components/ui/SeverityBadge'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { timeAgo, truncate } from '@/utils'
import { demoApi } from '@/api/client'
import { useProjectStore } from '@/store/projectStore'
import type { IncidentSeverity, IncidentStatus } from '@/types'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#e4ddd5'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#ede8e0'
const GREEN  = '#16a34a'
const AMBER  = '#d97706'
const RED    = '#dc2626'

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

function getTopThreat(incidents: readonly any[]): string | null {
  const counts: Record<string, number> = {}
  for (const inc of incidents) {
    const cat = inc.attack_category
    if (cat && cat !== 'BENIGN' && cat !== 'Unknown') {
      counts[cat] = (counts[cat] ?? 0) + 1
    }
  }
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]
  return top?.[0] ?? null
}

function getMostTargetedPort(incidents: readonly any[]): string | null {
  const counts: Record<string, number> = {}
  for (const inc of incidents) {
    if (inc.destination_port) {
      const p = String(inc.destination_port)
      counts[p] = (counts[p] ?? 0) + 1
    }
  }
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]
  if (!top) return null
  const labels: Record<string, string> = {
    '80': 'Port 80 (HTTP)', '443': 'Port 443 (HTTPS)', '22': 'Port 22 (SSH)',
    '21': 'Port 21 (FTP)', '3306': 'Port 3306 (MySQL)', '5432': 'Port 5432 (PostgreSQL)',
    '8080': 'Port 8080 (HTTP Alt)',
  }
  return labels[top[0]] ?? `Port ${top[0]}`
}

function StatCard({ label, value, sub, accent = false, onClick }: {
  label: string; value: React.ReactNode; sub?: string; accent?: boolean; onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '18px 20px', cursor: onClick ? 'pointer' : 'default', transition: 'border-color 0.15s' }}
      onMouseEnter={e => { if (onClick) e.currentTarget.style.borderColor = ORANGE }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = BORDER }}
    >
      <div style={{ fontSize: 11, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>{label}</div>
      <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 40, lineHeight: 1, color: accent ? ORANGE : BLACK }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: GRAY, marginTop: 6 }}>{sub}</div>}
    </div>
  )
}

function InfoCard({ icon, label, value, sub, empty }: {
  icon: React.ReactNode; label: string; value?: string | null; sub?: string; empty?: string
}) {
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '18px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 14 }}>
        {icon}
        <span style={{ fontSize: 11, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</span>
      </div>
      {value ? (
        <>
          <div style={{ fontSize: 14, fontWeight: 600, color: BLACK, marginBottom: 4 }}>{value}</div>
          {sub && <div style={{ fontSize: 11, color: GRAY }}>{sub}</div>}
        </>
      ) : (
        <div style={{ fontSize: 12, color: GRAY, fontStyle: 'italic' }}>{empty ?? 'No data'}</div>
      )}
    </div>
  )
}

function EmptyTimeline() {
  const qc = useQueryClient()
  const currentProject = useProjectStore(s => s.currentProject)
  const [done, setDone] = useState(false)
  const [demoError, setDemoError] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: () => demoApi.generate(currentProject?.id),
    onSuccess: () => {
      setDone(true)
      setDemoError(null)
      qc.invalidateQueries({ queryKey: ['incidents'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['compliance'] })
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      setDemoError(
        typeof detail === 'string'
          ? detail
          : 'Demo generation failed — check backend connectivity.',
      )
    },
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '48px 24px', gap: 14 }}>
      <Shield style={{ width: 36, height: 36, color: BORDER }} />
      <div style={{ fontSize: 14, fontWeight: 500, color: BLACK }}>No attacks detected yet</div>
      <div style={{ fontSize: 12, color: GRAY, textAlign: 'center', maxWidth: 300, lineHeight: 1.7 }}>
        Your application is connected and waiting for traffic. Once LBRO receives logs, you'll see incidents here.
      </div>
      {done ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: GREEN }}>
          <ShieldCheck style={{ width: 14, height: 14 }} /> Demo data generated — refreshing…
        </div>
      ) : (
        <>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '9px 18px', background: 'rgba(229,78,27,0.08)', border: '1px solid rgba(229,78,27,0.3)', borderRadius: 5, color: ORANGE, fontSize: 12, fontWeight: 500, cursor: mutation.isPending ? 'not-allowed' : 'pointer', opacity: mutation.isPending ? 0.7 : 1 }}
          >
            {mutation.isPending
              ? <><Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} /> Generating…</>
              : <><Sparkles style={{ width: 13, height: 13 }} /> Generate Demo Data</>
            }
          </button>
          {demoError && (
            <div style={{ fontSize: 11, color: '#ef4444', textAlign: 'center', maxWidth: 320 }}>
              {demoError}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function TimelineSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {[1, 2, 3, 4].map(i => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 20px', borderBottom: `1px solid ${BORDER}` }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: PARCH, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ height: 12, background: PARCH, borderRadius: 3, width: '60%', marginBottom: 6 }} />
            <div style={{ height: 10, background: PARCH, borderRadius: 3, width: '35%' }} />
          </div>
          <div style={{ width: 60, height: 10, background: PARCH, borderRadius: 3 }} />
        </div>
      ))}
    </div>
  )
}

const SEVERITY_DOT: Record<string, string> = {
  critical: RED, high: ORANGE, medium: AMBER, low: GREEN, info: '#94a3b8',
}

export default function DashboardPage() {
  const navigate  = useNavigate()
  const user      = useAuthStore(s => s.user)
  const firstName = user?.name?.split(' ')[0] ?? 'there'

  const { data: summary, isLoading: sumLoading } = useDashboardSummary()
  const { data: incidentsData, isLoading: incLoading } = useIncidents({ page_size: 12 })
  const { data: scoreData } = useSecurityScore()

  const incidents   = incidentsData?.items ?? []
  const critical    = summary?.critical_incidents ?? 0
  const openCount   = summary?.open_incidents ?? 0
  const newToday    = summary?.new_last_24h ?? 0
  const needsReview = summary?.needs_analyst_review ?? 0

  const topThreat        = useMemo(() => getTopThreat(incidents), [incidents])
  const mostTargetedPort = useMemo(() => getMostTargetedPort(incidents), [incidents])
  const latestIncident   = incidents[0] ?? null

  const health = useMemo(() => {
    if (scoreData) {
      if (scoreData.score >= 75) return { dot: GREEN, label: 'No critical issues detected.' }
      if (scoreData.score >= 50) return { dot: AMBER, label: 'Some items need your attention.' }
      return { dot: RED, label: 'Immediate attention required.' }
    }
    if (!sumLoading) {
      if (critical === 0) return { dot: GREEN, label: 'No critical issues detected.' }
      return { dot: RED, label: 'Immediate attention required.' }
    }
    return null
  }, [scoreData, critical, sumLoading])

  const topRecommendations = scoreData?.recommendations?.slice(0, 3) ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Greeting */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '24px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24 }}>
        <div>
          <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 34, color: BLACK, letterSpacing: '0.03em', lineHeight: 1.1 }}>
            {getGreeting()}, {firstName}
          </div>
          <div style={{ fontSize: 11, color: GRAY, marginTop: 5 }}>Your app's security at a glance</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '11px 16px', flexShrink: 0 }}>
          {health ? (
            <>
              <span style={{ width: 9, height: 9, borderRadius: '50%', background: health.dot, flexShrink: 0, boxShadow: `0 0 0 3px ${health.dot}22` }} />
              <span style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>{health.label}</span>
            </>
          ) : (
            <>
              <span style={{ width: 9, height: 9, borderRadius: '50%', background: PARCH, border: `1px solid ${BORDER}` }} />
              <span style={{ fontSize: 12, color: GRAY }}>Checking status…</span>
            </>
          )}
          {scoreData && (
            <button
              onClick={() => navigate('/security-score')}
              style={{ marginLeft: 8, fontSize: 11, color: ORANGE, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3, padding: 0 }}
            >
              Score: {scoreData.score}
              <ChevronRight style={{ width: 12, height: 12 }} />
            </button>
          )}
        </div>
      </div>

      {/* Critical banner */}
      {!sumLoading && critical > 0 && (
        <div
          onClick={() => navigate('/incidents?severity=critical')}
          role="alert"
          style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(220,38,38,0.05)', border: `1px solid rgba(220,38,38,0.25)`, borderLeft: `3px solid ${RED}`, borderRadius: 6, padding: '12px 18px', cursor: 'pointer' }}
        >
          <AlertTriangle style={{ width: 15, height: 15, color: RED, flexShrink: 0 }} />
          <span style={{ fontSize: 13, fontWeight: 500, color: RED, flex: 1 }}>
            {critical} critical incident{critical !== 1 ? 's' : ''} require immediate attention
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: RED }}>
            View now <ArrowRight style={{ width: 12, height: 12 }} />
          </span>
        </div>
      )}

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        <StatCard label="Today's Events"  value={sumLoading ? '—' : newToday}    sub="new in last 24 hours"      onClick={() => navigate('/incidents')} />
        <StatCard label="Critical"        value={sumLoading ? '—' : critical}    sub="need immediate attention"  accent={critical > 0} onClick={() => navigate('/incidents?severity=critical')} />
        <StatCard label="Open Issues"     value={sumLoading ? '—' : openCount}   sub="across all severity levels" onClick={() => navigate('/incidents')} />
        <StatCard label="Needs Attention" value={sumLoading ? '—' : needsReview} sub="flagged for your review"    onClick={() => navigate('/incidents')} />
      </div>

      {/* Insight cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
        <InfoCard icon={<AlertTriangle style={{ width: 13, height: 13, color: ORANGE }} />} label="Top Threat"      value={incLoading ? 'Loading…' : topThreat}        sub={topThreat ? 'most frequent attack type' : undefined}          empty="No threats detected yet" />
        <InfoCard icon={<Activity      style={{ width: 13, height: 13, color: ORANGE }} />} label="Most Attacked"  value={incLoading ? 'Loading…' : mostTargetedPort}  sub={mostTargetedPort ? 'highest volume entry point' : undefined} empty="No attack data yet" />
        <InfoCard icon={<Clock         style={{ width: 13, height: 13, color: ORANGE }} />} label="Latest Incident" value={latestIncident ? truncate(latestIncident.title, 36) : incLoading ? 'Loading…' : null} sub={latestIncident ? timeAgo(latestIncident.detected_at) : undefined} empty="No incidents recorded yet" />
      </div>

      {/* Timeline + Recommendations */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 10, alignItems: 'start' }}>

        {/* Recent Activity */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 20px', borderBottom: `1px solid ${BORDER}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Activity style={{ width: 14, height: 14, color: ORANGE }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: BLACK }}>Recent Activity</span>
            </div>
            <button
              onClick={() => navigate('/incidents')}
              style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: ORANGE, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            >
              View all <ArrowRight style={{ width: 11, height: 11 }} />
            </button>
          </div>

          {incLoading
            ? <TimelineSkeleton />
            : incidents.length === 0
              ? <EmptyTimeline />
              : (
                <div>
                  {incidents.slice(0, 8).map((inc, idx, arr) => (
                    <div
                      key={inc.id}
                      onClick={() => navigate(`/incidents/${inc.id}`)}
                      style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 20px', borderBottom: idx < arr.length - 1 ? `1px solid ${BORDER}` : 'none', cursor: 'pointer', transition: 'background 0.1s' }}
                      onMouseEnter={e => (e.currentTarget.style.background = PARCH)}
                      onMouseLeave={e => (e.currentTarget.style.background = '')}
                    >
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: SEVERITY_DOT[inc.severity] ?? GRAY, flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: BLACK, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {truncate(inc.title, 52)}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3 }}>
                          <SeverityBadge severity={inc.severity as IncidentSeverity} size="sm" />
                          <StatusBadge status={inc.status as IncidentStatus} size="sm" />
                          {inc.attack_category && inc.attack_category !== 'BENIGN' && (
                            <span style={{ fontSize: 10, color: GRAY, fontFamily: 'JetBrains Mono, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }}>
                              {inc.attack_category}
                            </span>
                          )}
                        </div>
                      </div>
                      <div style={{ fontSize: 11, color: GRAY, flexShrink: 0, whiteSpace: 'nowrap' }}>
                        {timeAgo(inc.detected_at)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
        </div>

        {/* Recommended Actions */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '15px 20px', borderBottom: `1px solid ${BORDER}` }}>
            <Zap style={{ width: 14, height: 14, color: ORANGE }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: BLACK }}>Recommended Actions</span>
          </div>

          {topRecommendations.length === 0 ? (
            <div style={{ padding: '36px 20px', textAlign: 'center' }}>
              <ShieldCheck style={{ width: 28, height: 28, color: GREEN, margin: '0 auto 10px' }} />
              <div style={{ fontSize: 13, fontWeight: 500, color: BLACK, marginBottom: 4 }}>You're in good shape</div>
              <div style={{ fontSize: 12, color: GRAY, lineHeight: 1.6 }}>No urgent actions needed right now.</div>
            </div>
          ) : (
            <div>
              {topRecommendations.map((rec: any, idx: number, arr: any[]) => {
                const priorityColor: Record<string, string> = { critical: RED, high: ORANGE, medium: AMBER, low: GREEN }
                const col = priorityColor[rec.priority] ?? GRAY
                return (
                  <div
                    key={idx}
                    onClick={() => navigate(rec.link ?? '/security-score')}
                    style={{ padding: '14px 20px', borderBottom: idx < arr.length - 1 ? `1px solid ${BORDER}` : 'none', cursor: 'pointer', transition: 'background 0.1s' }}
                    onMouseEnter={e => (e.currentTarget.style.background = PARCH)}
                    onMouseLeave={e => (e.currentTarget.style.background = '')}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                      <span style={{ marginTop: 4, width: 7, height: 7, borderRadius: '50%', background: col, flexShrink: 0 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: BLACK, marginBottom: 4, lineHeight: 1.4 }}>{rec.title}</div>
                        <div style={{ fontSize: 11, color: GRAY, lineHeight: 1.6 }}>
                          {rec.detail && rec.detail.length > 90 ? rec.detail.slice(0, 90) + '...' : rec.detail}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 8, fontSize: 11, color: col }}>
                          {rec.action} <ArrowRight style={{ width: 11, height: 11 }} />
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
              <div style={{ padding: '12px 20px', borderTop: `1px solid ${BORDER}` }}>
                <button
                  onClick={() => navigate('/security-score')}
                  style={{ width: '100%', fontSize: 12, color: ORANGE, background: 'none', border: `1px solid ${BORDER}`, borderRadius: 4, padding: '8px 0', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}
                >
                  Full security report <ArrowRight style={{ width: 12, height: 12 }} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
