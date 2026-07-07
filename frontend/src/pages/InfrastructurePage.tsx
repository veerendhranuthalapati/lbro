import { Server, Database, HardDrive, Activity, Zap, AlertTriangle } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { StatCard } from '@/components/ui/StatCard'
import { useInfrastructure, useSqsHistory } from '@/hooks/useApi'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'


function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '8px 12px', fontSize: 11 }}>
      <div style={{ fontFamily: 'JetBrains Mono, monospace', color: GRAY, marginBottom: 5 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: p.color }} />
          <span style={{ color: GRAY }}>{p.name}:</span>
          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: BLACK }}>{p.value}</span>
        </div>
      ))}
    </div>
  )
}

function HealthDot({ status }: { status: 'healthy' | 'degraded' | 'unhealthy' }) {
  const colors = {
    healthy:   { bg: 'rgba(58,122,80,0.08)',  border: 'rgba(58,122,80,0.3)',  text: '#3a7a50', dot: '#3a7a50'  },
    degraded:  { bg: 'rgba(217,119,6,0.08)',  border: 'rgba(217,119,6,0.3)', text: '#d97706', dot: '#d97706'  },
    unhealthy: { bg: 'rgba(229,78,27,0.08)',  border: 'rgba(229,78,27,0.3)', text: ORANGE,    dot: ORANGE     },
  }[status]
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, fontFamily: 'JetBrains Mono, monospace', padding: '2px 8px', borderRadius: 2, background: colors.bg, border: `1px solid ${colors.border}`, color: colors.text }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: colors.dot }} />
      {status.toUpperCase()}
    </span>
  )
}

function MiniBar({ pct }: { pct: number }) {
  const color = pct > 80 ? ORANGE : pct > 60 ? '#d97706' : '#3a7a50'
  return (
    <div style={{ height: 4, background: PARCH, borderRadius: 2, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2 }} />
    </div>
  )
}

function SkeletonBlock({ width = '60%', height = 12 }: { width?: string; height?: number }) {
  return <div style={{ height, background: PARCH, borderRadius: 2, width }} />
}

export default function InfrastructurePage() {
  // Both endpoints are MISSING -- GET /api/v1/infrastructure and GET /api/v1/infrastructure/sqs-history
  const { data: infra, isLoading: infraLoading, isError: infraError } = useInfrastructure()
  const { data: sqsHistory, isLoading: sqsLoading, isError: sqsError } = useSqsHistory()

  const rdsConns = infra?.rds_connections    ?? 0
  const rdsCpu   = infra?.rds_cpu_percent    ?? 0
  const apiP50   = infra?.api_latency_p50_ms ?? 0
  const apiP99   = infra?.api_latency_p99_ms ?? 0
  const s3SizeGb = infra?.s3_evidence_size_gb ?? 0

  // ECS: sum running/desired across all services for the KPI
  const ecsRunning = infra?.ecs_services.reduce((s, svc) => s + svc.tasks_running, 0) ?? 0
  const ecsDesired = infra?.ecs_services.reduce((s, svc) => s + svc.tasks_desired, 0) ?? 0

  // SQS: map queue array, colour by position
  const SQS_DOTS = [ORANGE, '#d97706', '#3a7a50']
  const sqsQueues = (infra?.sqs_queues ?? []).map((q, i) => ({ ...q, dot: SQS_DOTS[i] ?? GRAY }))

  // ECS services with real cpu/memory from API
  const ecsServices = infra?.ecs_services ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>Infrastructure</h2>
        <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>ECS Fargate · RDS · SQS · S3 · CloudWatch -- ap-south-1 (Mumbai)</p>
      </div>

      {/* Live status notice when infra endpoint is unavailable */}
      {(infraError || sqsError) && (
        <div style={{ background: 'rgba(217,119,6,0.06)', border: `1px solid rgba(217,119,6,0.3)`, borderLeft: `3px solid #d97706`, borderRadius: 4, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle style={{ width: 13, height: 13, color: '#d97706', flexShrink: 0 }} aria-hidden="true" />
          <span style={{ fontSize: 11, color: GRAY }}>
            Infrastructure metrics are unavailable. AWS connectivity is required — data will appear automatically once the service is reachable.
          </span>
        </div>
      )}

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        <StatCard
          label="ECS Tasks"
          value={infraLoading ? '…' : infraError ? '--' : `${ecsRunning}/${ecsDesired}`}
          sub={infraError ? 'unavailable' : 'all healthy'}
          icon={Server} accent="green"
        />
        <StatCard
          label="API p50"
          value={infraLoading ? '…' : infraError ? '--' : `${apiP50}ms`}
          sub={infraError ? 'unavailable' : `p99: ${apiP99}ms`}
          icon={Zap} accent="orange"
        />
        <StatCard
          label="RDS CPU"
          value={infraLoading ? '…' : infraError ? '--' : `${rdsCpu}%`}
          sub={infraError ? 'unavailable' : `${rdsConns} connections`}
          icon={Database} accent="orange"
        />
        <StatCard
          label="Evidence (S3)"
          value={infraLoading ? '…' : infraError ? '--' : `${s3SizeGb} GB`}
          sub={infraError ? 'unavailable' : 'Object Lock active'}
          icon={HardDrive} accent="purple"
        />
      </div>

      {/* Service status panels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {/* ECS */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Server style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
              <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>ECS Fargate</span>
            </div>
            {infra ? <HealthDot status="healthy" /> : <span style={{ fontSize: 10, color: GRAY }}>pending</span>}
          </div>

          {infraLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <SkeletonBlock /><SkeletonBlock width="80%" /><SkeletonBlock width="40%" />
            </div>
          )}

          {infraError && (
            <div style={{ fontSize: 11, color: GRAY, textAlign: 'center', padding: '16px 0' }}>
              No data — AWS connection required
            </div>
          )}

          {!infraLoading && !infraError && ecsServices.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {ecsServices.map(svc => (
                <div key={svc.name} style={{ background: PARCH, borderRadius: 4, padding: '10px 12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BLACK }}>{svc.name}</span>
                    <span style={{ fontSize: 10, color: '#3a7a50' }}>{svc.tasks_running}/{svc.tasks_desired} running</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {[{ label: 'CPU', pct: svc.cpu_percent }, { label: 'Memory', pct: svc.memory_percent }].map(m => (
                      <div key={m.label}>
                        <div style={{ fontSize: 9, color: GRAY, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{m.label}</div>
                        <MiniBar pct={m.pct} />
                        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: GRAY, marginTop: 3 }}>{m.pct.toFixed(0)}%</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* SQS */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Activity style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
              <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>SQS Queues</span>
            </div>
            {infra ? <HealthDot status="healthy" /> : <span style={{ fontSize: 10, color: GRAY }}>pending</span>}
          </div>

          {infraLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[0, 1, 2].map(i => <SkeletonBlock key={i} />)}
            </div>
          )}

          {infraError && (
            <div style={{ fontSize: 11, color: GRAY, textAlign: 'center', padding: '16px 0' }}>
              No data — AWS connection required
            </div>
          )}

          {!infraLoading && !infraError && sqsQueues.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {sqsQueues.map(q => (
                <div key={q.name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: q.dot, flexShrink: 0 }} />
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BLACK }}>{q.name}</span>
                    </div>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: q.depth > 10 ? ORANGE : q.depth > 5 ? '#d97706' : '#3a7a50' }}>
                      {q.depth} msgs
                    </span>
                  </div>
                  <MiniBar pct={Math.min(100, q.depth * 5)} />
                  {q.dlq_depth > 0 && (
                    <div style={{ fontSize: 9, color: ORANGE, marginTop: 3 }}>DLQ: {q.dlq_depth}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* RDS */}
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Database style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
              <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>RDS PostgreSQL</span>
            </div>
            {infra ? <HealthDot status="healthy" /> : <span style={{ fontSize: 10, color: GRAY }}>pending</span>}
          </div>

          {infraLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <SkeletonBlock /><SkeletonBlock width="80%" />
            </div>
          )}

          {infraError && (
            <div style={{ fontSize: 11, color: GRAY, textAlign: 'center', padding: '16px 0' }}>
              No data — AWS connection required
            </div>
          )}

          {!infraLoading && !infraError && infra && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { label: 'Connections', value: `${rdsConns}/500`, pct: (rdsConns / 500) * 100 },
                { label: 'CPU Util',    value: `${rdsCpu}%`,      pct: rdsCpu                  },
              ].map(m => (
                <div key={m.label}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                    <span style={{ color: GRAY }}>{m.label}</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: BLACK }}>{m.value}</span>
                  </div>
                  <MiniBar pct={m.pct} />
                </div>
              ))}
              <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 5 }}>
                {[
                  ['Instance',   'db.t3.medium'],
                  ['Engine',     'PostgreSQL 16.1'],
                  ['Multi-AZ',   'Enabled'],
                  ['Encryption', 'AES-256'],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
                    <span style={{ color: GRAY }}>{k}</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: BLACK }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* SQS History chart */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <Activity style={{ width: 13, height: 13, color: ORANGE }} aria-hidden="true" />
          <span style={{ fontSize: 11, fontWeight: 500, color: BLACK }}>SQS Queue Depth (10h)</span>
        </div>

        {sqsLoading && (
          <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ fontSize: 11, color: GRAY }}>Loading SQS history...</span>
          </div>
        )}

        {sqsError && (
          <div style={{ height: 200, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <span style={{ fontSize: 12, color: BLACK, fontWeight: 500 }}>Queue history unavailable</span>
            <span style={{ fontSize: 11, color: GRAY }}>AWS connection required to display SQS metrics</span>
          </div>
        )}

        {!sqsLoading && !sqsError && sqsHistory && sqsHistory.length > 0 && (
          <>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sqsHistory} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                <XAxis dataKey="time" tick={{ fill: GRAY, fontSize: 10 }} interval={4} />
                <YAxis tick={{ fill: GRAY, fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="incident"     stackId="a" fill={ORANGE}  opacity={0.85} radius={[0,0,0,0]} />
                <Bar dataKey="containment"  stackId="a" fill="#d97706" opacity={0.85} />
                <Bar dataKey="notification" stackId="a" fill="#3a7a50" opacity={0.85} radius={[2,2,0,0]} />
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: 10 }}>
              {[['incident', ORANGE], ['containment', '#d97706'], ['notification', '#3a7a50']].map(([label, color]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: color as string }} />
                  <span style={{ color: GRAY }}>{label}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
