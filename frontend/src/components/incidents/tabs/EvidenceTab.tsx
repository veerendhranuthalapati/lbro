import { useState } from 'react'
import { Lock, Download, Eye, CheckCircle, Upload, AlertTriangle } from 'lucide-react'
import { useEvidence, useUploadEvidence } from '@/hooks/useApi'
import { evidenceApi } from '@/api/client'
import { getAccessToken } from '@/store/authStore'
import { formatDate, formatBytes, shortHash } from '@/utils'
import { ORANGE, BLACK, BORDER, GRAY, CREAM, PARCH, GREEN, Card, CardHead, Skeleton } from '../WorkspaceShared'

interface Props { incidentId: string }

export function EvidenceTab({ incidentId }: Props) {
  const { data: evidenceList, isLoading, isError, refetch } = useEvidence(incidentId)
  const uploadMutation = useUploadEvidence()
  const evidence = evidenceList ?? []

  const [verifyState, setVerifyState] = useState<Record<string, 'idle' | 'verifying' | 'ok' | 'fail'>>({})

  const handleDownload = async (downloadUrl: string | null, filename: string, contentType: string) => {
    if (!downloadUrl) return
    try {
      const token = getAccessToken()
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(downloadUrl, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(new Blob([blob], { type: contentType }))
      const a = document.createElement('a')
      a.href = url; a.download = filename
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
    } catch { alert('Download failed — check backend connectivity.') }
  }

  const handlePreview = async (downloadUrl: string | null, contentType: string, filename: string) => {
    if (!downloadUrl) return
    try {
      const token = getAccessToken()
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(downloadUrl, { headers })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(new Blob([blob], { type: contentType }))
      const win = window.open(url, '_blank')
      if (!win) { const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); a.remove() }
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch { alert('Preview failed.') }
  }

  const handleVerify = async (evidenceId: string) => {
    setVerifyState(s => ({ ...s, [evidenceId]: 'verifying' }))
    try {
      const r = await evidenceApi.verify(evidenceId)
      setVerifyState(s => ({ ...s, [evidenceId]: r.hash_matched ? 'ok' : 'fail' }))
    } catch {
      setVerifyState(s => ({ ...s, [evidenceId]: 'fail' }))
    }
  }

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    uploadMutation.mutate({ incidentId, file }, { onSuccess: () => refetch() })
    e.target.value = ''
  }

  return (
    <Card>
      <CardHead
        icon={<Lock style={{ width: 13, height: 13, color: ORANGE }} />}
        title="Evidence Vault"
        extra={
          <label style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5, fontSize: 9, color: ORANGE, border: `1px solid ${ORANGE}40`, background: `${ORANGE}08`, borderRadius: 2, padding: '3px 10px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            <Upload style={{ width: 10, height: 10 }} /> Upload
            <input type="file" style={{ display: 'none' }} onChange={handleUpload} />
          </label>
        }
      />

      {isLoading ? <Skeleton lines={4} />
        : isError ? <p style={{ fontSize: 11, color: GRAY }}>Could not load evidence.</p>
        : evidence.length === 0 ? <p style={{ fontSize: 11, color: GRAY }}>No evidence files attached yet.</p>
        : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {evidence.map(ev => {
              const vs = verifyState[ev.id] ?? 'idle'
              return (
                <div key={ev.id} style={{ border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
                  {/* Header row */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, padding: '10px 12px', background: PARCH }}>
                    <div>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fontWeight: 700, color: ORANGE }}>
                        {ev.content_type.split('/').pop()?.toUpperCase() ?? 'FILE'}
                      </span>
                      {ev.file_size > 0 && <span style={{ fontSize: 10, color: GRAY, marginLeft: 8 }}>{formatBytes(ev.file_size)}</span>}
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, marginTop: 2 }}>{ev.filename}</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, fontSize: 10 }}>
                        <span style={{ color: GRAY }}>SHA-256:</span>
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', color: GREEN }}>{shortHash(ev.sha256_hash)}</span>
                      </div>
                      <div style={{ fontSize: 9, color: GRAY, marginTop: 2 }}>Uploaded {formatDate(ev.created_at)}</div>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flexShrink: 0 }}>
                      <button
                        onClick={() => handleDownload(ev.download_url, ev.original_filename, ev.content_type)}
                        disabled={!ev.download_url}
                        style={{ fontSize: 9, color: ORANGE, border: `1px solid ${ORANGE}40`, background: `${ORANGE}08`, padding: '3px 8px', borderRadius: 2, cursor: ev.download_url ? 'pointer' : 'not-allowed', opacity: ev.download_url ? 1 : 0.4, display: 'flex', alignItems: 'center', gap: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}
                      >
                        <Download style={{ width: 9, height: 9 }} /> Download
                      </button>
                      <button
                        onClick={() => handlePreview(ev.download_url, ev.content_type, ev.filename)}
                        disabled={!ev.download_url}
                        style={{ fontSize: 9, color: GRAY, border: `1px solid ${BORDER}`, background: 'white', padding: '3px 8px', borderRadius: 2, cursor: ev.download_url ? 'pointer' : 'not-allowed', opacity: ev.download_url ? 1 : 0.4, display: 'flex', alignItems: 'center', gap: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}
                      >
                        <Eye style={{ width: 9, height: 9 }} /> Preview
                      </button>
                      <button
                        onClick={() => handleVerify(ev.id)}
                        disabled={vs === 'verifying'}
                        style={{ fontSize: 9, color: vs === 'ok' ? GREEN : vs === 'fail' ? '#ef4444' : '#8b5cf6', border: `1px solid ${vs === 'ok' ? GREEN : vs === 'fail' ? '#ef4444' : '#8b5cf6'}40`, background: 'white', padding: '3px 8px', borderRadius: 2, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}
                      >
                        {vs === 'verifying' ? '...'
                          : vs === 'ok' ? <><CheckCircle style={{ width: 9, height: 9 }} /> Verified</>
                          : vs === 'fail' ? <><AlertTriangle style={{ width: 9, height: 9 }} /> Mismatch</>
                          : 'Verify Hash'}
                      </button>
                    </div>
                  </div>

                  {/* Chain of custody */}
                  {ev.custody_chain?.length > 0 && (
                    <div style={{ padding: '8px 12px', borderTop: `1px solid ${BORDER}` }}>
                      <p style={{ fontSize: 9, color: GRAY, fontWeight: 600, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Chain of Custody</p>
                      {ev.custody_chain.map((c, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, marginBottom: 3 }}>
                          <CheckCircle style={{ width: 10, height: 10, color: GREEN, flexShrink: 0 }} />
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: GRAY, width: 68, flexShrink: 0, fontSize: 9 }}>{formatDate(c.created_at, 'HH:mm:ss')}</span>
                          <span style={{ fontFamily: 'JetBrains Mono, monospace', color: ORANGE, fontWeight: 600, fontSize: 9 }}>{c.action}</span>
                          {c.notes && <span style={{ color: GRAY, fontSize: 9 }}>· {c.notes}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )
      }
    </Card>
  )
}
