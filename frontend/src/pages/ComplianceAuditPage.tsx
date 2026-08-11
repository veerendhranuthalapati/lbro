/**
 * Compliance Audit Report — all metrics sourced from backend API.
 * Obligations: GET /api/v1/compliance/obligations
 * Incident records: GET /api/v1/compliance/dashboard
 * PDF: GET /api/v1/reports/compliance/pdf (same DB source)
 */
import { useEffect, useMemo, useState } from 'react'
import { logger } from '@/lib/logger'
import { useNavigate } from 'react-router-dom'
import {
  ShieldCheck, AlertTriangle, CheckCircle, XCircle, Clock,
  Download, ChevronRight, BarChart2, FileText, Info,
} from 'lucide-react'
import { getAccessToken } from '@/store/authStore'
import { downloadMockPdf } from '@/mocks/mockPdf'
import { complianceApi, type ObligationResponse } from '@/api/client'
import { useProjectStore } from '@/store/projectStore'

const BLACK  = '#111111'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'
const BORDER = '#c8c2b8'
const ORANGE = '#e54e1b'
const GREEN  = '#16a34a'
const RED    = '#dc2626'
const AMBER  = '#d97706'

type ControlStatus = 'pass' | 'fail' | 'partial' | 'na'

interface Control {
  id: string
  domain: string
  title: string
  description: string
  status: ControlStatus
  evidence?: string
  finding?: string
}

interface Framework {
  id: string
  name: string
  full: string
  color: string
  controls: Control[]
  pct: number | null
  has_data: boolean
}

const FRAMEWORK_META: Record<string, { name: string; full: string; color: string }> = {
  GDPR:  { name: 'GDPR',  full: 'General Data Protection Regulation', color: '#3b82f6' },
  HIPAA: { name: 'HIPAA', full: 'Health Insurance Portability and Accountability Act', color: '#a78bfa' },
  DPDPA: { name: 'DPDPA', full: 'Digital Personal Data Protection Act', color: ORANGE },
  SOC2:  { name: 'SOC 2', full: 'Service Organisation Control 2', color: '#7c3aed' },
  ISO27001: { name: 'ISO 27001', full: 'Information Security Management System', color: GREEN },
}

function obligationStatus(s: string): ControlStatus {
  if (s === 'compliant') return 'pass'
  if (s === 'non_compliant') return 'fail'
  if (s === 'in_progress') return 'partial'
  return 'na'
}

function statusColor(s: ControlStatus) {
  return s === 'pass' ? GREEN : s === 'fail' ? RED : s === 'partial' ? AMBER : GRAY
}

function StatusIcon({ s }: { s: ControlStatus }) {
  const col = statusColor(s)
  if (s === 'pass') return <CheckCircle style={{ width: 14, height: 14, color: col }} />
  if (s === 'fail') return <XCircle style={{ width: 14, height: 14, color: col }} />
  if (s === 'partial') return <AlertTriangle style={{ width: 14, height: 14, color: col }} />
  return <Info style={{ width: 14, height: 14, color: col }} />
}

function ScoreRing({ pct, color, label }: { pct: number | null; color: string; label: string }) {
  const R = 44; const cx = 52; const cy = 52; const circ = 2 * Math.PI * R
  const display = pct != null ? `${pct}%` : 'N/A'
  return (
    <svg width={104} height={104} viewBox="0 0 104 104">
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={PARCH} strokeWidth={8} />
      {pct != null && (
        <circle cx={cx} cy={cy} r={R} fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * circ} ${circ}`}
          transform={`rotate(-90 ${cx} ${cy})`} />
      )}
      <text x={cx} y={cy - 6} textAnchor="middle" style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: pct != null ? 24 : 16, fill: BLACK }}>{display}</text>
      <text x={cx} y={cy + 14} textAnchor="middle" style={{ fontSize: 9, fill: GRAY, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</text>
    </svg>
  )
}

export default function ComplianceAuditPage() {
  const navigate = useNavigate()
  const projectId = useProjectStore(s => s.currentProject?.id)
  const [obligations, setObligations] = useState<ObligationResponse[]>([])
  const [recordPct, setRecordPct] = useState<number | null>(null)
  const [recordHasData, setRecordHasData] = useState(false)
  const [activeFramework, setActiveFramework] = useState<string>('GDPR')
  const [expandedControl, setExpandedControl] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)
  const isMock = import.meta.env.VITE_MOCK === 'true'
  const mockFilename = `lbro-compliance-audit-${new Date().toISOString().slice(0, 10)}.pdf`

  useEffect(() => {
    if (!projectId) {
      setObligations([])
      setRecordPct(null)
      setRecordHasData(false)
      return
    }
    complianceApi.getObligations(projectId).then(setObligations).catch(() => setObligations([]))
    complianceApi.dashboard(projectId).then(d => {
      setRecordPct(d.overall_compliance_pct ?? null)
      setRecordHasData(!!d.has_data)
    }).catch(() => {
      setRecordPct(null)
      setRecordHasData(false)
    })
  }, [projectId])

  const frameworks: Framework[] = useMemo(() => {
    const grouped: Record<string, Control[]> = {}
    for (const o of obligations) {
      grouped[o.framework] = grouped[o.framework] ?? []
      grouped[o.framework].push({
        id: o.control_id,
        domain: o.framework,
        title: o.control_name,
        description: o.description ?? '',
        status: obligationStatus(o.status),
        evidence: o.evidence_reference ?? undefined,
        finding: o.recommendations ?? undefined,
      })
    }
    return Object.entries(grouped).map(([fw, controls]) => {
      const pass = controls.filter(c => c.status === 'pass').length
      const meta = FRAMEWORK_META[fw] ?? { name: fw, full: fw, color: GRAY }
      return {
        id: fw.toLowerCase(),
        name: meta.name,
        full: meta.full,
        color: meta.color,
        controls,
        pct: controls.length ? Math.round(pass / controls.length * 100) : null,
        has_data: controls.length > 0,
      }
    })
  }, [obligations])

  const fw = frameworks.find(f => f.id === activeFramework.toLowerCase() || f.name === activeFramework) ?? frameworks[0]
  const hasAnyData = frameworks.some(f => f.has_data) || recordHasData

  const handleDownload = async () => {
    if (downloading) return
    setDownloading(true)
    try {
      const token = getAccessToken()
      const res = await fetch('/api/v1/reports/compliance/pdf', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = mockFilename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 10_000)
    } catch (err) {
      logger.error('Compliance PDF download failed', { error: err instanceof Error ? err.message : String(err) })
      alert('Download failed. Please try again.')
    } finally {
      setDownloading(false)
    }
  }

  if (!hasAnyData) {
    return (
      <div style={{ maxWidth: 720, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK }}>Compliance Audit</h2>
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 24, textAlign: 'center' }}>
          <ShieldCheck style={{ width: 32, height: 32, color: GRAY, margin: '0 auto 12px' }} />
          <p style={{ fontSize: 14, color: BLACK, fontWeight: 500 }}>No compliance data available</p>
          <p style={{ fontSize: 12, color: GRAY, marginTop: 8 }}>
            Configure project obligations in the Compliance Center or create incidents with compliance records.
          </p>
          <button onClick={() => navigate('/compliance')} style={{ marginTop: 16, fontSize: 11, padding: '8px 16px', border: `1px solid ${BORDER}`, background: PARCH, cursor: 'pointer' }}>
            Go to Compliance Center
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, lineHeight: 1, margin: 0 }}>Compliance Audit</h2>
          <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
            Sourced from project obligations and incident compliance records · PDF matches database
          </p>
        </div>
        <button onClick={isMock ? () => downloadMockPdf(mockFilename) : handleDownload} disabled={downloading}
          style={{ fontSize: 11, padding: '7px 14px', border: `1px solid ${BORDER}`, background: PARCH, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
          <Download style={{ width: 12, height: 12 }} />
          {downloading ? 'Generating…' : 'Download PDF'}
        </button>
      </div>

      {recordHasData && (
        <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
          <ScoreRing pct={recordPct != null ? Math.round(recordPct) : null} color={GREEN} label="Incident records" />
          <div>
            <div style={{ fontSize: 12, fontWeight: 500, color: BLACK }}>Breach notification compliance (incident records)</div>
            <div style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
              {recordPct != null ? `${recordPct}% of incident-linked requirements met` : 'No compliance data available'}
            </div>
          </div>
        </div>
      )}

      {frameworks.length > 0 && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(frameworks.length, 3)}, 1fr)`, gap: 12 }}>
            {frameworks.map(f => (
              <div key={f.id} onClick={() => setActiveFramework(f.name)}
                style={{ background: activeFramework === f.name ? PARCH : CREAM, border: `1px solid ${BORDER}`, borderTop: `3px solid ${f.color}`, borderRadius: 4, padding: 16, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12 }}>
                <ScoreRing pct={f.pct} color={f.color} label={f.name} />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{f.name}</div>
                  <div style={{ fontSize: 10, color: GRAY }}>{f.controls.length} controls tracked</div>
                </div>
              </div>
            ))}
          </div>

          {fw && (
            <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4 }}>
              <div style={{ padding: '14px 16px', borderBottom: `1px solid ${BORDER}` }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{fw.full}</div>
                <div style={{ fontSize: 10, color: GRAY, marginTop: 2 }}>{fw.controls.length} obligations from database</div>
              </div>
              {fw.controls.map(c => (
                <div key={c.id} style={{ borderBottom: `1px solid ${BORDER}`, padding: '12px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }} onClick={() => setExpandedControl(expandedControl === c.id ? null : c.id)}>
                    <StatusIcon s={c.status} />
                    <span style={{ fontSize: 12, flex: 1 }}>{c.title}</span>
                    <span style={{ fontSize: 10, color: statusColor(c.status), textTransform: 'uppercase' }}>{c.status}</span>
                    <ChevronRight style={{ width: 12, height: 12, color: GRAY, transform: expandedControl === c.id ? 'rotate(90deg)' : undefined }} />
                  </div>
                  {expandedControl === c.id && (
                    <div style={{ marginTop: 8, fontSize: 11, color: GRAY, paddingLeft: 22 }}>
                      {c.evidence && <p><strong>Evidence:</strong> {c.evidence}</p>}
                      {c.finding && <p><strong>Finding:</strong> {c.finding}</p>}
                      {!c.evidence && !c.finding && <p>No additional notes.</p>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
