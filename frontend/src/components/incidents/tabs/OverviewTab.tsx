import {
  Globe, Clock, Database, Shield, Lock, AlertCircle,
  Server, Cpu, FileCode, Target, Activity,
} from 'lucide-react'
import { SeverityBadge } from '@/components/ui/SeverityBadge'
import { StatusBadge } from '@/components/ui/StatusBadge'
import type { IncidentDetail } from '@/types'
import type { IncidentSeverity, IncidentStatus } from '@/types'
import { formatDate, timeAgo } from '@/utils'
import {
  ORANGE, BLACK, BORDER, GRAY, CREAM, PARCH, GREEN, BLUE,
  Card, CardHead, KV, Tag,
} from '../WorkspaceShared'

interface Props {
  incident: IncidentDetail
}

const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#f59e0b',
  low:      '#22c55e',
  info:     '#3b82f6',
}

export function OverviewTab({ incident }: Props) {
  const conf = incident.confidence_score != null
    ? Math.round(incident.confidence_score * 100)
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* ── Stat strip ────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {[
          { label: 'Severity',    value: incident.severity.toUpperCase(), icon: AlertCircle, color: SEV_COLOR[incident.severity] ?? GRAY },
          { label: 'Status',      value: incident.status.toUpperCase(),   icon: Activity,    color: ORANGE },
          { label: 'Attack Type', value: incident.attack_category ?? '—', icon: Shield,      color: '#8b5cf6' },
          { label: 'Confidence',  value: conf != null ? `${conf}%` : '—', icon: Cpu,         color: conf && conf >= 90 ? GREEN : conf && conf >= 70 ? '#d97706' : GRAY },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 9, color: GRAY, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              <Icon style={{ width: 11, height: 11 }} aria-hidden />
              {label}
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* ── Main grid ─────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>

        {/* Incident Identity */}
        <Card>
          <CardHead icon={<FileCode style={{ width: 13, height: 13, color: ORANGE }} />} title="Incident Identity" />
          <KV label="Incident ID"   value={incident.external_id ?? String(incident.id).slice(0, 8)} mono />
          <KV label="Project"       value={(incident as any).project_name ?? '—'} />
          <KV label="Detection Time" value={formatDate(incident.detected_at)} mono />
          <KV label="Last Updated"  value={formatDate(incident.updated_at)} mono />
          <KV label="Closed At"     value={incident.closed_at ? formatDate(incident.closed_at) : '—'} mono />
          <KV label="ML Model"      value={incident.ml_model_version ?? '—'} mono />
          <KV label="Needs Review"  value={incident.needs_analyst_review ? 'YES' : 'No'} />
        </Card>

        {/* Network Details */}
        <Card>
          <CardHead icon={<Globe style={{ width: 13, height: 13, color: '#3b82f6' }} />} title="Network Details" />
          <KV label="Source IP"          value={incident.source_ip}           mono />
          <KV label="Destination IP"     value={incident.destination_ip}      mono />
          <KV label="Source Port"        value={incident.source_port}         mono />
          <KV label="Destination Port"   value={incident.destination_port}    mono />
          <KV label="Protocol"           value={incident.protocol?.toUpperCase()} mono />
          <KV label="Country"            value={(incident as any).country ?? '—'} />
          <KV label="User Agent"         value={(incident as any).user_agent ?? '—'} />
          <KV label="Application"        value={(incident as any).application ?? '—'} />
        </Card>

        {/* Security Classification */}
        <Card>
          <CardHead icon={<Target style={{ width: 13, height: 13, color: '#8b5cf6' }} />} title="Security Classification" />
          <KV label="Attack Category"    value={incident.attack_category} />
          <KV label="ML Confidence"      value={conf != null ? `${conf}%` : '—'} mono />
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>MITRE ATT&CK</div>
            <div>
              {(incident as any).mitre_techniques?.length > 0
                ? (incident as any).mitre_techniques.map((t: string) => <Tag key={t} text={t} color="#8b5cf6" />)
                : <span style={{ fontSize: 10, color: GRAY }}>Resolve via Explain tab</span>
              }
            </div>
          </div>
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>OWASP</div>
            <div>
              {(incident as any).owasp_category
                ? <Tag text={(incident as any).owasp_category} color={BLUE} />
                : <span style={{ fontSize: 10, color: GRAY }}>Resolve via Explain tab</span>
              }
            </div>
          </div>
        </Card>

        {/* Data Classification */}
        <Card>
          <CardHead icon={<Lock style={{ width: 13, height: 13, color: ORANGE }} />} title="Data & Compliance" />
          {[
            { label: 'Personal Data',    active: incident.personal_data_involved,                 color: '#7c3aed' },
            { label: 'Health Data',      active: incident.health_data_involved,                   color: ORANGE   },
            { label: 'GDPR Notifiable',  active: incident.affected_jurisdictions?.includes('EU'), color: BLUE     },
            { label: 'HIPAA Notifiable', active: incident.affected_jurisdictions?.includes('US'), color: '#a78bfa' },
            { label: 'DPDPA Notifiable', active: incident.affected_jurisdictions?.includes('IN'), color: ORANGE   },
          ].map(({ label, active, color }) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, padding: '5px 0', borderBottom: `1px solid ${PARCH}` }}>
              <span style={{ color: GRAY }}>{label}</span>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: active ? color : BORDER }}>
                {active ? 'YES' : 'NO'}
              </span>
            </div>
          ))}
          {incident.affected_jurisdictions?.length ? (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>Jurisdictions</div>
              <div>
                {incident.affected_jurisdictions.map(j => <Tag key={j} text={j} color={BLUE} />)}
              </div>
            </div>
          ) : null}
        </Card>

      </div>

      {/* ── Description ───────────────────────────────────────────────── */}
      {incident.description && (
        <Card>
          <CardHead icon={<Server style={{ width: 13, height: 13, color: GRAY }} />} title="Description" />
          <p style={{ fontSize: 12, color: BLACK, lineHeight: 1.7, margin: 0 }}>{incident.description}</p>
        </Card>
      )}
    </div>
  )
}
