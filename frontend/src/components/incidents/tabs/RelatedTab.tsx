import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useRelatedIncidents } from '@/hooks/useApi'
import { timeAgo } from '@/utils'
import { SeverityBadge } from '@/components/ui/SeverityBadge'
import { StatusBadge } from '@/components/ui/StatusBadge'
import type { IncidentSeverity, IncidentStatus } from '@/types'
import { ORANGE, BLACK, BORDER, GRAY, CREAM, PARCH, GREEN, BLUE,
  Card, CardHead, Skeleton, Tag } from '../WorkspaceShared'

const RELATION_LABELS: Record<string, string> = {
  same_ip:       'Same Source IP',
  same_dest_ip:  'Same Dest IP',
  same_attack:   'Same Attack Type',
  same_project:  'Same Project',
  same_analyst:  'Same Analyst',
}

interface Props { incidentId: string }

export function RelatedTab({ incidentId }: Props) {
  const { data, isLoading, isError } = useRelatedIncidents(incidentId)
  const related = data?.related ?? []

  if (isLoading) return <Skeleton lines={5} />
  if (isError)   return <p style={{ fontSize: 11, color: GRAY }}>Could not load related incidents.</p>

  return (
    <Card>
      <CardHead
        icon={<ArrowRight style={{ width: 13, height: 13, color: ORANGE }} />}
        title="Related Incidents"
        extra={<span style={{ fontSize: 9, color: GRAY }}>{related.length} found</span>}
      />

      {related.length === 0 ? (
        <p style={{ fontSize: 11, color: GRAY }}>No related incidents found for this IP, attack type, or project.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {related.map(r => (
            <Link
              key={r.id}
              to={`/incidents/${r.id}`}
              style={{ textDecoration: 'none' }}
            >
              <div style={{
                border: `1px solid ${BORDER}`, borderRadius: 4, padding: '10px 12px',
                background: CREAM, transition: 'border-color .15s',
                cursor: 'pointer',
              }}
                onMouseEnter={e => (e.currentTarget.style.borderColor = ORANGE)}
                onMouseLeave={e => (e.currentTarget.style.borderColor = BORDER)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5, flexWrap: 'wrap' }}>
                  <SeverityBadge severity={r.severity as IncidentSeverity} />
                  <StatusBadge   status={r.status   as IncidentStatus}   />
                  <span style={{ fontSize: 9, color: GRAY, marginLeft: 'auto' }}>{timeAgo(r.detected_at)}</span>
                </div>
                <div style={{ fontSize: 12, fontWeight: 600, color: BLACK, marginBottom: 5 }}>{r.title}</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  {r.attack_category && (
                    <Tag text={r.attack_category} color="#8b5cf6" />
                  )}
                  {r.source_ip && (
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: GRAY }}>
                      {r.source_ip}
                    </span>
                  )}
                  {r.relations.map(rel => (
                    <Tag key={rel} text={RELATION_LABELS[rel] ?? rel} color={ORANGE} />
                  ))}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </Card>
  )
}
