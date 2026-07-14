import { Globe, Hash, Server, Wifi, Download } from 'lucide-react'
import { useIncidentIOC } from '@/hooks/useApi'
import { ORANGE, BLACK, BORDER, GRAY, CREAM, PARCH, GREEN, BLUE,
  Card, CardHead, Skeleton, CopyButton, Tag } from '../WorkspaceShared'

interface Props { incidentId: string }

function IOCSection({
  icon, title, color, rows,
}: {
  icon: React.ReactNode
  title: string
  color: string
  rows: { label: string; value: string; note?: string }[]
}) {
  if (rows.length === 0) return null

  const exportCSV = () => {
    const csv = ['label,value,note', ...rows.map(r => `"${r.label}","${r.value}","${r.note ?? ''}"`)].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `ioc_${title.toLowerCase().replace(/\s/g, '_')}.csv`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
        <span style={{ color }}>{icon}</span>
        <span style={{ fontSize: 10, fontWeight: 600, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.08em', flex: 1 }}>
          {title}
        </span>
        <button
          onClick={exportCSV}
          style={{ fontSize: 9, color: GRAY, border: `1px solid ${BORDER}`, background: 'white', borderRadius: 2, padding: '2px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
        >
          <Download style={{ width: 9, height: 9 }} /> CSV
        </button>
      </div>
      <div style={{ border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
        {rows.map((r, i) => (
          <div
            key={i}
            style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', gap: 10, background: i % 2 === 0 ? CREAM : 'white', borderBottom: i < rows.length - 1 ? `1px solid ${PARCH}` : 'none' }}
          >
            <span style={{ fontSize: 9, color: GRAY, width: 80, flexShrink: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{r.label}</span>
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: BLACK, flex: 1, wordBreak: 'break-all' }}>{r.value}</span>
            {r.note && <span style={{ fontSize: 9, color: GRAY }}>{r.note}</span>}
            <CopyButton text={r.value} />
          </div>
        ))}
      </div>
    </div>
  )
}

export function IOCTab({ incidentId }: Props) {
  const { data: ioc, isLoading, isError } = useIncidentIOC(incidentId)

  if (isLoading) return <Skeleton lines={6} />
  if (isError || !ioc) return <p style={{ fontSize: 11, color: GRAY }}>Could not load IOC data.</p>

  const ipRows = ioc.ips.map(ip => ({ label: ip.role, value: ip.ip, note: ip.type }))
  const portRows = ioc.ports.map(p => ({ label: p.role, value: String(p.port), note: p.protocol.toUpperCase() }))
  const hashRows = ioc.hashes.map(h => ({ label: h.type.toUpperCase(), value: h.hash, note: h.filename }))
  const protoRows = ioc.protocols.map(p => ({ label: 'proto', value: p.toUpperCase() }))

  const exportAll = () => {
    const lines = [
      '# LBRO Incident IOC Export',
      `# Incident: ${ioc.incident_id}`,
      '',
      '## IPs',
      ...ioc.ips.map(ip => `${ip.role.padEnd(15)} ${ip.ip}`),
      '',
      '## Ports',
      ...ioc.ports.map(p => `${p.role.padEnd(15)} ${p.port}/${p.protocol}`),
      '',
      '## Hashes (SHA-256)',
      ...ioc.hashes.map(h => `${h.filename.padEnd(30)} ${h.hash}`),
      '',
      '## MITRE Techniques',
      ...ioc.mitre_techniques,
      '',
      `OWASP: ${ioc.owasp_category ?? 'N/A'}`,
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `ioc_${ioc.incident_id.slice(0, 8)}.txt`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <Card>
      <CardHead
        icon={<Globe style={{ width: 13, height: 13, color: ORANGE }} />}
        title="Indicators of Compromise"
        extra={
          <button
            onClick={exportAll}
            style={{ fontSize: 9, color: ORANGE, border: `1px solid ${ORANGE}40`, background: `${ORANGE}08`, borderRadius: 2, padding: '3px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}
          >
            <Download style={{ width: 9, height: 9 }} /> Export All
          </button>
        }
      />

      <IOCSection icon={<Globe style={{ width: 12, height: 12 }} />} title="IP Addresses" color={ORANGE} rows={ipRows} />
      <IOCSection icon={<Server style={{ width: 12, height: 12 }} />} title="Ports"       color="#3b82f6" rows={portRows} />
      <IOCSection icon={<Hash   style={{ width: 12, height: 12 }} />} title="File Hashes" color={GREEN}   rows={hashRows} />
      {protoRows.length > 0 && (
        <IOCSection icon={<Wifi style={{ width: 12, height: 12 }} />} title="Protocols" color={GRAY} rows={protoRows} />
      )}

      {ioc.mitre_techniques?.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>MITRE ATT&CK</div>
          <div>{ioc.mitre_techniques.map(t => <Tag key={t} text={t} color="#8b5cf6" />)}</div>
        </div>
      )}
      {ioc.owasp_category && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 9, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>OWASP</div>
          <Tag text={ioc.owasp_category} color={BLUE} />
        </div>
      )}

      {ipRows.length === 0 && portRows.length === 0 && hashRows.length === 0 && (
        <p style={{ fontSize: 11, color: GRAY }}>No IOCs extracted for this incident.</p>
      )}
    </Card>
  )
}

import React from 'react'
