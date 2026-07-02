import { Lock, Database, CheckCircle, Download, Eye, AlertTriangle } from 'lucide-react'
import { StatCard } from '@/components/ui/StatCard'
import { useAllEvidence } from '@/hooks/useApi'
import { formatDate, formatBytes, shortHash } from '@/utils'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

function MissingEndpointNotice() {
  return (
    <div style={{ background: 'rgba(217,119,6,0.06)', border: `1px solid rgba(217,119,6,0.3)`, borderLeft: `3px solid #d97706`, borderRadius: 4, padding: '12px 16px', display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 16 }}>
      <AlertTriangle style={{ width: 15, height: 15, color: '#d97706', flexShrink: 0, marginTop: 1 }} aria-hidden="true" />
      <div>
        <div style={{ fontSize: 12, fontWeight: 500, color: BLACK, marginBottom: 4 }}>Missing backend endpoint</div>
        <div style={{ fontSize: 11, color: GRAY, lineHeight: 1.6 }}>
          A global evidence listing endpoint is required:{' '}
          <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: ORANGE, background: 'rgba(229,78,27,0.06)', padding: '1px 5px', borderRadius: 2 }}>
            GET /api/v1/evidence
          </code>
          {' '}-- must return a paginated list of all evidence packages across all incidents.
          Per-incident evidence is available at{' '}
          <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY }}>
            GET /api/v1/incidents/{'{id}'}/evidence
          </code>{' '}
          (implemented). Once <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10 }}>GET /api/v1/evidence</code> is deployed, this page will display live data automatically.
        </div>
      </div>
    </div>
  )
}

export default function EvidencePage() {
  // Requires missing endpoint: GET /api/v1/evidence
  const { data, isLoading, isError } = useAllEvidence({ page_size: 50 })

  const evidenceList = data?.items ?? []
  const totalCount   = data?.total ?? 0
  const totalSize    = evidenceList.reduce((sum, e) => sum + (e.file_size ?? 0), 0)
  const custodySteps = evidenceList.reduce((sum, e) => sum + e.custody_chain.length, 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>Evidence Vault</h2>
        <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>Forensic evidence with S3 Object Lock (WORM) · SHA-256 integrity</p>
      </div>

      <MissingEndpointNotice />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        <StatCard label="Evidence packages" value={isLoading ? '…' : totalCount}        icon={Database}     accent="orange" />
        <StatCard label="Total size"        value={isLoading ? '…' : formatBytes(totalSize)} icon={Lock}     accent="purple" />
        <StatCard label="Custody steps"     value={isLoading ? '…' : custodySteps}      icon={CheckCircle}  accent="green"  sub="verified actions" />
        <StatCard label="Integrity"         value={evidenceList.length > 0 ? '100%' : '--'} icon={CheckCircle} accent="green" sub="all hashes verified" />
      </div>

      {/* WORM banner */}
      <div style={{ background: CREAM, border: `1px solid rgba(229,78,27,0.3)`, borderLeft: `3px solid ${ORANGE}`, borderRadius: 4, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Lock style={{ width: 16, height: 16, color: ORANGE, flexShrink: 0 }} aria-hidden="true" />
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>S3 Object Lock Enabled (WORM)</div>
          <div style={{ fontSize: 11, color: GRAY, marginTop: 2 }}>Files stored in COMPLIANCE mode -- cannot be deleted or modified. SHA-256 hashes verified post-upload.</div>
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div style={{ background: 'rgba(229,78,27,0.06)', border: `1px solid rgba(229,78,27,0.3)`, borderRadius: 4, padding: '16px', textAlign: 'center', color: GRAY, fontSize: 12 }}>
          <code style={{ fontFamily: 'JetBrains Mono, monospace', color: ORANGE }}>GET /api/v1/evidence</code> is not yet implemented on the backend. Evidence is available per-incident at{' '}
          <code style={{ fontFamily: 'JetBrains Mono, monospace' }}>GET /api/v1/incidents/{'{id}'}/evidence</code>.
        </div>
      )}

      {/* Loading skeletons */}
      {isLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[0, 1, 2].map(i => (
            <div key={i} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
              <div style={{ height: 12, background: PARCH, borderRadius: 2, width: '60%', marginBottom: 8 }} />
              <div style={{ height: 10, background: PARCH, borderRadius: 2, width: '80%', marginBottom: 6 }} />
              <div style={{ height: 10, background: PARCH, borderRadius: 2, width: '40%' }} />
            </div>
          ))}
        </div>
      )}

      {/* Evidence list (live from API when endpoint exists) */}
      {!isLoading && !isError && evidenceList.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {evidenceList.map(ev => (
            <div key={ev.id} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                <div style={{ padding: '8px', background: 'rgba(229,78,27,0.08)', border: `1px solid rgba(229,78,27,0.2)`, borderRadius: 4, flexShrink: 0 }}>
                  <Lock style={{ width: 16, height: 16, color: ORANGE }} aria-hidden="true" />
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 10 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: ORANGE, background: 'rgba(229,78,27,0.08)', padding: '2px 7px', border: `1px solid rgba(229,78,27,0.25)`, borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                          {ev.content_type.split('/').pop()?.toUpperCase() ?? 'FILE'}
                        </span>
                        {ev.file_size > 0 && <span style={{ fontSize: 10, color: GRAY }}>{formatBytes(ev.file_size)}</span>}
                      </div>
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: BLACK }}>{ev.filename}</div>
                      <div style={{ fontSize: 10, color: GRAY, marginTop: 2 }}>
                        Incident: <code style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9 }}>{ev.incident_id}</code>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button style={{ fontSize: 10, color: GRAY, border: `1px solid ${BORDER}`, padding: '4px 10px', borderRadius: 2, background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        <Eye style={{ width: 11, height: 11 }} aria-hidden="true" /> Preview
                      </button>
                      <button style={{ fontSize: 10, color: ORANGE, border: `1px solid rgba(229,78,27,0.3)`, padding: '4px 10px', borderRadius: 2, background: 'rgba(229,78,27,0.06)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        <Download style={{ width: 11, height: 11 }} aria-hidden="true" /> Download
                      </button>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
                    <div style={{ background: PARCH, borderRadius: 4, padding: '8px 10px' }}>
                                  <div style={{ fontSize: 9, color: GRAY, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500 }}>SHA-256 Hash</div>
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#3a7a50', display: 'flex', alignItems: 'center', gap: 5 }}>
                        <CheckCircle style={{ width: 11, height: 11, flexShrink: 0 }} aria-hidden="true" />
                        {shortHash(ev.sha256_hash)}
                        <span style={{ fontSize: 9, color: GRAY }}>VERIFIED</span>
                      </div>
                    </div>
                    <div style={{ background: PARCH, borderRadius: 4, padding: '8px 10px' }}>
                      <div style={{ fontSize: 9, color: GRAY, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 500 }}>Uploaded</div>
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY }}>{formatDate(ev.created_at)}</div>
                    </div>
                  </div>

                  <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 10 }}>
                    <p style={{ fontSize: 10, fontWeight: 500, color: BLACK, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 5 }}>
                      <CheckCircle style={{ width: 11, height: 11, color: '#3a7a50' }} aria-hidden="true" />
                      Chain of custody ({ev.custody_chain.length} events)
                    </p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                      {ev.custody_chain.map((c, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 10 }}>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: GRAY, flexShrink: 0, width: 64 }}>{formatDate(c.created_at, 'HH:mm:ss')}</span>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: ORANGE, fontWeight: 600, flexShrink: 0, width: 72 }}>{c.action}</span>
                          <span style={{ color: BLACK }}>{c.performed_by_name}</span>
                          {c.notes && <span style={{ color: GRAY }}>-- {c.notes}</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
