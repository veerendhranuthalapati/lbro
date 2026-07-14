import { useState } from 'react'
import { Terminal, ChevronDown, ChevronUp, Copy, Download } from 'lucide-react'
import type { IncidentDetail } from '@/types'
import { ORANGE, BLACK, BORDER, GRAY, CREAM, PARCH, GREEN, Card, CardHead } from '../WorkspaceShared'

interface Props { incident: IncidentDetail }

function JsonBlock({ label, data }: { label: string; data: unknown }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const text = JSON.stringify(data, null, 2)

  const copyText = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const download = () => {
    const blob = new Blob([text], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${label.toLowerCase().replace(/\s+/g, '_')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden', marginBottom: 10 }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          padding: '9px 12px', background: PARCH, border: 'none', cursor: 'pointer', textAlign: 'left',
        }}
        aria-expanded={open}
      >
        {open
          ? <ChevronUp style={{ width: 13, height: 13, color: GRAY }} />
          : <ChevronDown style={{ width: 13, height: 13, color: GRAY }} />
        }
        <span style={{ fontSize: 10, fontWeight: 600, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.07em', flex: 1 }}>
          {label}
        </span>
        <div style={{ display: 'flex', gap: 6 }} onClick={e => e.stopPropagation()}>
          <button
            onClick={copyText}
            style={{ fontSize: 9, color: copied ? GREEN : ORANGE, border: `1px solid ${ORANGE}30`, background: `${ORANGE}08`, borderRadius: 2, padding: '2px 7px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <Copy style={{ width: 9, height: 9 }} />
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            onClick={download}
            style={{ fontSize: 9, color: GRAY, border: `1px solid ${BORDER}`, background: 'white', borderRadius: 2, padding: '2px 7px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <Download style={{ width: 9, height: 9 }} />
            JSON
          </button>
        </div>
      </button>

      {open && (
        <pre style={{
          margin: 0, padding: '12px 14px',
          fontFamily: 'JetBrains Mono, monospace', fontSize: 10, lineHeight: 1.7,
          color: BLACK, background: CREAM, overflowX: 'auto',
          maxHeight: 400, overflowY: 'auto',
        }}>
          {text}
        </pre>
      )}
    </div>
  )
}

export function RawEventTab({ incident }: Props) {
  // Build the full incident JSON (without file_data)
  const rawIncident: Record<string, unknown> = {
    id:               incident.id,
    external_id:      incident.external_id,
    title:            incident.title,
    description:      incident.description,
    status:           incident.status,
    severity:         incident.severity,
    attack_category:  incident.attack_category,
    confidence_score: incident.confidence_score,
    ml_model_version: incident.ml_model_version,
    needs_analyst_review: incident.needs_analyst_review,
    source_ip:        incident.source_ip,
    destination_ip:   incident.destination_ip,
    source_port:      incident.source_port,
    destination_port: incident.destination_port,
    protocol:         incident.protocol,
    personal_data_involved: incident.personal_data_involved,
    health_data_involved:   incident.health_data_involved,
    affected_jurisdictions: incident.affected_jurisdictions,
    assigned_to:      incident.assigned_to,
    created_by:       incident.created_by,
    detected_at:      incident.detected_at,
    closed_at:        incident.closed_at,
    created_at:       incident.created_at,
    updated_at:       incident.updated_at,
  }

  const networkFeatures = (incident as any).network_features ?? null

  return (
    <Card>
      <CardHead
        icon={<Terminal style={{ width: 13, height: 13, color: ORANGE }} />}
        title="Raw Event Data"
        extra={<span style={{ fontSize: 9, color: GRAY }}>Expand sections to view</span>}
      />

      <JsonBlock label="Incident Record" data={rawIncident} />

      {networkFeatures && <JsonBlock label="Network Flow Features (ML Input)" data={networkFeatures} />}

      {(incident.actions?.length ?? 0) > 0 && (
        <JsonBlock label="Incident Actions / Status History" data={incident.actions} />
      )}

      {/* Metadata */}
      <div style={{ background: PARCH, borderRadius: 4, padding: '10px 12px', marginTop: 8 }}>
        <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Metadata</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {[
            ['Incident UUID', String(incident.id)],
            ['ML Model', incident.ml_model_version ?? '—'],
            ['Attack Category', incident.attack_category ?? '—'],
            ['Protocol', incident.protocol ?? '—'],
            ['Source Port', String(incident.source_port ?? '—')],
            ['Dest Port', String(incident.destination_port ?? '—')],
          ].map(([k, v]) => (
            <div key={k}>
              <span style={{ fontSize: 9, color: GRAY }}>{k}: </span>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: BLACK }}>{v}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
