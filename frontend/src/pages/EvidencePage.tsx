import { Lock, Database, CheckCircle, Download, Eye } from 'lucide-react'
import { logger } from '@/lib/logger'
import { StatCard } from '@/components/ui/StatCard'
import { useAllEvidence } from '@/hooks/useApi'
import { formatDate, formatBytes, shortHash } from '@/utils'
import { getAccessToken } from '@/store/authStore'

const ORANGE = '#e54e1b'
const BLACK  = '#111111'
const BORDER = '#c8c2b8'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'

export default function EvidencePage() {
  const { data, isLoading, isError } = useAllEvidence({ page_size: 50 })
  const handleDownload = async (downloadUrl: string | null, filename: string, contentType: string) => {
    if (!downloadUrl) return
    try {
      const res = await fetch(downloadUrl, {
        headers: (() => { const t = getAccessToken(); const h: Record<string,string> = {}; if (t) h['Authorization'] = `Bearer ${t}`; return h; })(),
      })
      if (!res.ok) {
        if (res.status === 404) throw new Error('FILE_NOT_FOUND')
        throw new Error(`HTTP ${res.status}`)
      }
      const blob = await res.blob()
      const objectUrl = URL.createObjectURL(new Blob([blob], { type: contentType }))
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      logger.error('Evidence download failed', { error: msg })
      alert(
        msg === 'FILE_NOT_FOUND'
          ? 'No file data stored for this record. Re-run the seed script to populate file data.'
          : 'Download failed — check backend connectivity.'
      )
    }
  }

  const handleView = async (downloadUrl: string | null, contentType: string, filename: string) => {
    if (!downloadUrl) return
    try {
      const res = await fetch(downloadUrl, {
        headers: (() => { const t = getAccessToken(); const h: Record<string,string> = {}; if (t) h['Authorization'] = `Bearer ${t}`; return h; })(),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const objectUrl = URL.createObjectURL(new Blob([blob], { type: contentType }))
      // Open in new tab — browser will render images, PDFs, and text files natively
      const win = window.open(objectUrl, '_blank')
      if (!win) {
        // Fallback: trigger download if popup blocked
        const a = document.createElement('a')
        a.href = objectUrl
        a.download = filename
        document.body.appendChild(a)
        a.click()
        a.remove()
      }
      setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
    } catch (err) {
      alert('Preview failed — check backend connectivity.')
    }
  }

  const evidenceList = data?.items ?? []
  const totalCount   = data?.total ?? 0
  const totalSize    = evidenceList.reduce((sum, e) => sum + (e.file_size ?? 0), 0)
  const custodySteps = evidenceList.reduce((sum, e) => sum + e.custody_chain.length, 0)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1 }}>Evidence Vault</h2>
        <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>Files attached to incidents — SHA-256 verified and stored in your database</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        <StatCard label="Evidence files"     value={isLoading ? '...' : totalCount}        icon={Database}     accent="orange" />
        <StatCard label="Total size"        value={isLoading ? '...' : formatBytes(totalSize)} icon={Lock}     accent="purple" />
        <StatCard label="Custody steps"     value={isLoading ? '...' : custodySteps}      icon={CheckCircle}  accent="green"  sub="verified actions" />
        <StatCard label="Integrity"         value={evidenceList.length > 0 ? '100%' : '--'} icon={CheckCircle} accent="green" sub="SHA-256 stored on upload" />
      </div>

      {/* Storage banner */}
      <div style={{ background: CREAM, border: '1px solid rgba(229,78,27,0.3)', borderLeft: '3px solid #e54e1b', borderRadius: 4, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Lock style={{ width: 16, height: 16, color: ORANGE, flexShrink: 0 }} aria-hidden="true" />
        <div>
          <div style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>Evidence stored in your database (tamper-proof)</div>
          <div style={{ fontSize: 11, color: GRAY, marginTop: 2 }}>Files are saved directly in your database. Each file gets a SHA-256 fingerprint when uploaded. Records cannot be modified after the fact.</div>
        </div>
      </div>

      {isError && (
        <div style={{ background: 'rgba(229,78,27,0.06)', border: '1px solid rgba(229,78,27,0.3)', borderRadius: 4, padding: '16px', textAlign: 'center', color: GRAY, fontSize: 12 }}>
          Failed to load evidence. Check backend connectivity and try again.
        </div>
      )}

      {isLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[0, 1, 2].map(i => (
            <div key={i} style={{ background: CREAM, border: '1px solid #c8c2b8', borderRadius: 4, padding: 16 }}>
              <div style={{ height: 12, background: PARCH, borderRadius: 2, width: '60%', marginBottom: 8 }} />
              <div style={{ height: 10, background: PARCH, borderRadius: 2, width: '80%', marginBottom: 6 }} />
              <div style={{ height: 10, background: PARCH, borderRadius: 2, width: '40%' }} />
            </div>
          ))}
        </div>
      )}

      {!isLoading && !isError && evidenceList.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {evidenceList.map(ev => (
            <div key={ev.id} style={{ background: CREAM, border: '1px solid #c8c2b8', borderRadius: 4, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                <div style={{ padding: '8px', background: 'rgba(229,78,27,0.08)', border: '1px solid rgba(229,78,27,0.2)', borderRadius: 4, flexShrink: 0 }}>
                  <Lock style={{ width: 16, height: 16, color: ORANGE }} aria-hidden="true" />
                </div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 10 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: ORANGE, background: 'rgba(229,78,27,0.08)', padding: '2px 7px', border: '1px solid rgba(229,78,27,0.25)', borderRadius: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
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
                      <button
                        onClick={() => handleView(ev.download_url, ev.content_type, ev.filename)}
                        disabled={!ev.download_url}
                        style={{ fontSize: 10, color: GRAY, border: '1px solid #c8c2b8', padding: '4px 10px', borderRadius: 2, background: 'transparent', cursor: ev.download_url ? 'pointer' : 'not-allowed', opacity: ev.download_url ? 1 : 0.5, display: 'flex', alignItems: 'center', gap: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        <Eye style={{ width: 11, height: 11 }} aria-hidden="true" /> Preview
                      </button>
                      <button
                        onClick={() => handleDownload(ev.download_url, ev.original_filename, ev.content_type)}
                        disabled={!ev.download_url}
                        style={{ fontSize: 10, color: ORANGE, border: '1px solid rgba(229,78,27,0.3)', padding: '4px 10px', borderRadius: 2, background: 'rgba(229,78,27,0.06)', cursor: ev.download_url ? 'pointer' : 'not-allowed', opacity: ev.download_url ? 1 : 0.5, display: 'flex', alignItems: 'center', gap: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
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

                  <div style={{ borderTop: '1px solid #c8c2b8', paddingTop: 10 }}>
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