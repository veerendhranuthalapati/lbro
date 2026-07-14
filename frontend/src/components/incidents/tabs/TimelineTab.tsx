import { Clock, Zap, Shield, Cpu, Activity, CheckCircle, Plus, Paperclip } from 'lucide-react'
import { useIncidentTimeline } from '@/hooks/useApi'
import { formatDate } from '@/utils'
import { ORANGE, BLACK, BORDER, GRAY, CREAM, GREEN, Skeleton, Card, CardHead } from '../WorkspaceShared'

const ICON_MAP: Record<string, React.ReactNode> = {
  plus:         <Plus        style={{ width: 12, height: 12 }} />,
  zap:          <Zap         style={{ width: 12, height: 12 }} />,
  cpu:          <Cpu         style={{ width: 12, height: 12 }} />,
  activity:     <Activity    style={{ width: 12, height: 12 }} />,
  paperclip:    <Paperclip   style={{ width: 12, height: 12 }} />,
  shield:       <Shield      style={{ width: 12, height: 12 }} />,
  'check-circle': <CheckCircle style={{ width: 12, height: 12 }} />,
}

interface Props { incidentId: string }

export function TimelineTab({ incidentId }: Props) {
  const { data, isLoading, isError } = useIncidentTimeline(incidentId)
  const events = data?.events ?? []

  if (isLoading) return <Skeleton lines={6} />
  if (isError)   return <p style={{ fontSize: 11, color: GRAY }}>Could not load timeline.</p>

  return (
    <Card>
      <CardHead icon={<Clock style={{ width: 13, height: 13, color: ORANGE }} />} title="Investigation Timeline" extra={
        <span style={{ fontSize: 9, color: GRAY }}>{events.length} events</span>
      } />

      {events.length === 0 ? (
        <p style={{ fontSize: 11, color: GRAY }}>No timeline events recorded yet.</p>
      ) : (
        <div style={{ position: 'relative' }}>
          {/* Vertical rail */}
          <div style={{ position: 'absolute', left: 10, top: 0, bottom: 0, width: 1, background: BORDER }} />

          {events.map((evt, i) => (
            <div key={i} style={{ display: 'flex', gap: 14, paddingBottom: i < events.length - 1 ? 18 : 0 }}>
              {/* Dot */}
              <div style={{
                width: 21, height: 21, borderRadius: '50%',
                background: evt.color ?? GRAY,
                flexShrink: 0, zIndex: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#fff',
              }}>
                {ICON_MAP[evt.icon] ?? <Activity style={{ width: 12, height: 12 }} />}
              </div>

              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 2 }}>
                  <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: evt.color ?? GRAY }}>
                    {evt.event_type.replace(/_/g, ' ')}
                  </span>
                  <span style={{ fontSize: 9, color: GRAY }}>· {evt.actor}</span>
                </div>
                <p style={{ fontSize: 12, color: BLACK, margin: 0, lineHeight: 1.6 }}>{evt.description}</p>
                <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: GRAY, marginTop: 3 }}>
                  {formatDate(evt.occurred_at)}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

import React from 'react'
