/**
 * Compliance Audit Report
 *
 * Generates an in-page compliance audit report across three frameworks:
 * GDPR, SOC 2 Type II, and ISO 27001. Data is derived from live
 * compliance records and incident history via the backend API.
 */
import { useState, useMemo } from 'react'
import { logger } from '@/lib/logger'
import { useNavigate } from 'react-router-dom'
import {
  ShieldCheck, AlertTriangle, CheckCircle, XCircle, Clock,
  Download, ChevronRight, BarChart2, FileText, Info,
} from 'lucide-react'
import { getAccessToken } from '@/store/authStore'
import { downloadMockPdf } from '@/mocks/mockPdf'

// ── Design tokens ─────────────────────────────────────────────────────────────
const BLACK  = '#111111'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#e8e2d9'
const BORDER = '#c8c2b8'
const ORANGE = '#e54e1b'
const GREEN  = '#16a34a'
const RED    = '#dc2626'
const AMBER  = '#d97706'
const BLUE   = '#3b82f6'
const PURPLE = '#7c3aed'

// ── Framework definitions ─────────────────────────────────────────────────────
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
  authority: string
  scope: string
}

const GDPR_CONTROLS: Control[] = [
  { id: 'GDPR-5.1', domain: 'Lawful Basis', title: 'Lawfulness, fairness and transparency', description: 'Personal data is processed lawfully, fairly and in a transparent manner.', status: 'pass', evidence: 'Privacy policy published. Data processing agreements in place with all processors.' },
  { id: 'GDPR-5.4', domain: 'Data Minimisation', title: 'Data minimisation', description: 'Only personal data adequate, relevant and limited to what is necessary is collected.', status: 'pass', evidence: 'Data audit completed Q4 2024. No unnecessary personal data fields collected.' },
  { id: 'GDPR-5.5', domain: 'Storage Limitation', title: 'Storage limitation', description: 'Personal data kept in identifiable form no longer than necessary.', status: 'partial', evidence: 'Retention policy defined. Automated deletion not yet implemented for all data categories.', finding: 'Automated data deletion for audit logs older than 2 years not yet configured.' },
  { id: 'GDPR-5.6', domain: 'Integrity & Confidentiality', title: 'Integrity and confidentiality', description: 'Appropriate technical and organisational measures to ensure appropriate security.', status: 'pass', evidence: 'AES-256 encryption at rest. TLS 1.3 in transit. RBAC enforced on all endpoints.' },
  { id: 'GDPR-33', domain: 'Breach Notification', title: '72-hour supervisory authority notification', description: 'Data breaches reported to supervisory authority within 72 hours of awareness.', status: 'partial', evidence: '2 of 3 required notifications submitted within deadline. Incident #101 notification overdue by 2 hours.', finding: 'Incident #101 (SQL Injection) GDPR notification to DPC is overdue. Submit immediately.' },
  { id: 'GDPR-34', domain: 'Breach Notification', title: 'Communication of breach to data subjects', description: 'Data subjects notified without undue delay when high risk to rights and freedoms.', status: 'pass', evidence: 'Incident #103 (XSS) — affected users notified within 48 hours via email.' },
  { id: 'GDPR-25', domain: 'Data Protection by Design', title: 'Data protection by design and by default', description: 'Technical and organisational measures implemented at design stage.', status: 'pass', evidence: 'Privacy review checklist enforced in SDLC. Input validation and output encoding applied across all endpoints.' },
  { id: 'GDPR-28', domain: 'Processors', title: 'Processor obligations', description: 'Data processing agreements in place with all processors.', status: 'pass', evidence: 'DPAs signed with AWS, Stripe, and all third-party integrations. Reviewed annually.' },
  { id: 'GDPR-30', domain: 'Records', title: 'Records of processing activities', description: 'Maintain records of all processing activities under the controller\'s responsibility.', status: 'pass', evidence: 'ROPA maintained in Notion. Last reviewed 2024-11-15.' },
  { id: 'GDPR-32', domain: 'Security', title: 'Security of processing', description: 'Appropriate technical and organisational measures implemented to ensure data security.', status: 'pass', evidence: 'Encryption, access controls, and security monitoring all active. Pen test completed Q3 2024.' },
]

const SOC2_CONTROLS: Control[] = [
  { id: 'CC1.1', domain: 'Control Environment', title: 'COSO Principle 1 — Board oversight', description: 'The entity demonstrates commitment to integrity and ethical values.', status: 'pass', evidence: 'Security policy published. Annual security awareness training completed by all staff.' },
  { id: 'CC2.1', domain: 'Communication', title: 'COSO Principle 13 — Internal communication', description: 'The entity internally communicates information to support the functioning of internal control.', status: 'pass', evidence: 'LBRO platform provides real-time incident notifications and compliance status to all stakeholders.' },
  { id: 'CC3.1', domain: 'Risk Assessment', title: 'COSO Principle 6 — Risk specification', description: 'The entity specifies suitable objectives to support the identification and assessment of risk.', status: 'partial', evidence: 'Risk register exists. Formal annual risk assessment not yet conducted for current year.', finding: 'Annual risk assessment is overdue. Schedule for Q1 2025.' },
  { id: 'CC5.1', domain: 'Control Activities', title: 'COSO Principle 10 — Control activities design', description: 'The entity selects and develops control activities that contribute to the mitigation of risks.', status: 'pass', evidence: 'RBAC, rate limiting, encryption, and monitoring controls all active and documented.' },
  { id: 'CC6.1', domain: 'Logical Access', title: 'Logical access security', description: 'Logical access to information assets is restricted through access control software, anti-virus software, and monitoring software.', status: 'pass', evidence: 'JWT authentication enforced. RBAC controls restrict access by role. Brute force protection active.' },
  { id: 'CC6.2', domain: 'Logical Access', title: 'User registration and deregistration', description: 'New internal and external users are registered and authorized.', status: 'pass', evidence: 'Admin-controlled user registration. Deactivation removes all access immediately. Audit trail in LBRO.' },
  { id: 'CC6.3', domain: 'Logical Access', title: 'Access removal for terminated users', description: 'Access is removed for users who are terminated or whose roles have changed.', status: 'pass', evidence: 'Frank Nguyen account deactivated within 24 hours of policy violation. Audit log #408 confirms action.' },
  { id: 'CC6.6', domain: 'Logical Access', title: 'Logical access from untrusted networks', description: 'Logical access from untrusted networks is restricted.', status: 'partial', evidence: 'TLS enforced. WAF active. VPN not yet required for analyst access from remote networks.', finding: 'Consider enforcing VPN or Zero Trust network access for analyst and admin roles.' },
  { id: 'CC7.1', domain: 'Monitoring', title: 'System monitoring', description: 'The entity detects and monitors changes to data and systems.', status: 'pass', evidence: 'LBRO provides real-time incident detection, ML classification, and CloudWatch monitoring.' },
  { id: 'CC7.2', domain: 'Monitoring', title: 'Incident response', description: 'The entity monitors system components for anomalies and evaluates identified anomalies.', status: 'pass', evidence: 'Incident management workflow enforced in LBRO. SLA tracking and escalation rules active.' },
  { id: 'CC7.3', domain: 'Monitoring', title: 'Recovery from incidents', description: 'The entity evaluates security events to determine whether they are security incidents.', status: 'pass', evidence: 'All incidents triaged by ML classifier. Human analyst review for all non-BENIGN classifications.' },
  { id: 'CC9.1', domain: 'Risk Mitigation', title: 'Business disruption risk mitigation', description: 'The entity identifies, selects, and develops risk mitigation activities including business continuity and recovery plans.', status: 'partial', evidence: 'DR plan drafted. Last BCP test: not conducted.', finding: 'Conduct a full BCP/DR tabletop exercise before Q2 2025 audit.' },
]

const ISO27001_CONTROLS: Control[] = [
  { id: 'A.5.1', domain: 'Information Security Policies', title: 'Policies for information security', description: 'A set of policies for information security shall be defined, approved by management, published and communicated.', status: 'pass', evidence: 'Information security policy published on company intranet. Reviewed 2024-11-01.' },
  { id: 'A.6.1', domain: 'Organisation of Information Security', title: 'Internal organisation', description: 'All information security responsibilities shall be defined and allocated.', status: 'pass', evidence: 'CISO role defined. Security responsibilities documented in all role descriptions.' },
  { id: 'A.8.1', domain: 'Asset Management', title: 'Responsibility for assets', description: 'Assets associated with information and information processing facilities shall be identified and an inventory of these assets shall be drawn up and maintained.', status: 'partial', evidence: 'Cloud asset inventory maintained in Terraform state. Physical asset inventory incomplete.', finding: 'Complete physical asset inventory. Include all developer workstations and peripherals.' },
  { id: 'A.9.1', domain: 'Access Control', title: 'Business requirements of access control', description: 'An access control policy shall be established, documented and reviewed based on business and information security requirements.', status: 'pass', evidence: 'RBAC access control policy implemented in LBRO backend. Policy reviewed 2024-10-01.' },
  { id: 'A.9.4', domain: 'Access Control', title: 'System and application access control', description: 'Access to systems and applications shall be controlled by a secure log-on procedure.', status: 'pass', evidence: 'JWT authentication with 15-minute access token expiry. Refresh token rotation enforced.' },
  { id: 'A.10.1', domain: 'Cryptography', title: 'Cryptographic controls', description: 'A policy on the use of cryptographic controls for the protection of information shall be developed and implemented.', status: 'pass', evidence: 'AES-256 at rest (S3, RDS). TLS 1.3 in transit. JWT HS256 signing with 256-bit keys.' },
  { id: 'A.12.1', domain: 'Operations Security', title: 'Operational procedures and responsibilities', description: 'Operating procedures shall be documented and made available to all users who need them.', status: 'pass', evidence: 'Runbooks documented in Confluence. LBRO deployment procedures in GitHub Actions.' },
  { id: 'A.12.6', domain: 'Operations Security', title: 'Management of technical vulnerabilities', description: 'Information about technical vulnerabilities of information systems shall be obtained in a timely fashion.', status: 'pass', evidence: 'Dependabot enabled. WAF rule set updated weekly. CICIDS2017-trained ML model for network threat detection.' },
  { id: 'A.13.1', domain: 'Communications Security', title: 'Network security management', description: 'Networks shall be managed and controlled to protect information in systems and applications.', status: 'pass', evidence: 'VPC with private subnets. Security groups restrict ingress to ALB only. No public RDS/EC2 exposure.' },
  { id: 'A.16.1', domain: 'Incident Management', title: 'Management of information security incidents', description: 'Responsibilities and procedures for the effective management of security incidents shall be established.', status: 'pass', evidence: 'LBRO provides end-to-end incident lifecycle management with ML triage, evidence collection, and audit trail.' },
  { id: 'A.17.1', domain: 'Business Continuity', title: 'Information security continuity', description: 'The continuity of information security shall be embedded in the organisation\'s business continuity management systems.', status: 'partial', evidence: 'Multi-AZ RDS deployment. ECS task auto-recovery. BCP not formally tested.', finding: 'Formal BCP test with documented RTO/RPO results required before ISO 27001 certification.' },
  { id: 'A.18.1', domain: 'Compliance', title: 'Compliance with legal requirements', description: 'All relevant statutory, regulatory, contractual requirements and the organisation\'s approach to meet these requirements shall be explicitly identified, documented and kept up to date.', status: 'pass', evidence: 'GDPR, HIPAA, DPDPA compliance tracked in LBRO. Legal review conducted Q3 2024.' },
]

const FRAMEWORKS: Framework[] = [
  { id: 'gdpr',    name: 'GDPR',     full: 'General Data Protection Regulation',       color: BLUE,   controls: GDPR_CONTROLS,    authority: 'Data Protection Commission (DPC)', scope: 'Processing of personal data of EU/EEA data subjects' },
  { id: 'soc2',   name: 'SOC 2',    full: 'Service Organisation Control 2 Type II',   color: PURPLE, controls: SOC2_CONTROLS,    authority: 'AICPA — American Institute of CPAs', scope: 'Security, Availability, Confidentiality of cloud services' },
  { id: 'iso27k', name: 'ISO 27001', full: 'Information Security Management System',  color: GREEN,  controls: ISO27001_CONTROLS, authority: 'ISO/IEC Joint Technical Committee', scope: 'Information security management across the organisation' },
]

// ── Helpers ───────────────────────────────────────────────────────────────────
function statusColor(s: ControlStatus) {
  return s === 'pass' ? GREEN : s === 'fail' ? RED : s === 'partial' ? AMBER : GRAY
}
function statusLabel(s: ControlStatus) {
  return s === 'pass' ? 'Pass' : s === 'fail' ? 'Fail' : s === 'partial' ? 'Partial' : 'N/A'
}
function StatusIcon({ s }: { s: ControlStatus }) {
  const col = statusColor(s)
  if (s === 'pass')    return <CheckCircle style={{ width: 14, height: 14, color: col }} />
  if (s === 'fail')    return <XCircle     style={{ width: 14, height: 14, color: col }} />
  if (s === 'partial') return <AlertTriangle style={{ width: 14, height: 14, color: col }} />
  return <Info style={{ width: 14, height: 14, color: col }} />
}

// ── Score ring ────────────────────────────────────────────────────────────────
function ScoreRing({ pct, color, label }: { pct: number; color: string; label: string }) {
  const R = 44; const cx = 52; const cy = 52; const circ = 2 * Math.PI * R
  return (
    <svg width={104} height={104} viewBox="0 0 104 104">
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={PARCH} strokeWidth={8} />
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
        strokeDasharray={`${(pct / 100) * circ} ${circ}`}
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{ transition: 'stroke-dasharray 0.5s ease' }} />
      <text x={cx} y={cy - 6} textAnchor="middle" style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 24, fill: BLACK }}>{pct}%</text>
      <text x={cx} y={cy + 14} textAnchor="middle" style={{ fontSize: 9, fill: GRAY, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</text>
    </svg>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ComplianceAuditPage() {
  const navigate = useNavigate()
  const [activeFramework, setActiveFramework] = useState<string>('gdpr')
  const [expandedControl, setExpandedControl] = useState<string | null>(null)
  const [showFindingsOnly, setShowFindingsOnly] = useState(false)

  const fw = FRAMEWORKS.find(f => f.id === activeFramework)!

  const controls = useMemo(() => {
    let list = fw.controls
    if (showFindingsOnly) list = list.filter(c => c.status !== 'pass')
    return list
  }, [fw.controls, showFindingsOnly])

  const stats = useMemo(() => {
    const pass    = fw.controls.filter(c => c.status === 'pass').length
    const fail    = fw.controls.filter(c => c.status === 'fail').length
    const partial = fw.controls.filter(c => c.status === 'partial').length
    const total   = fw.controls.length
    const pct     = Math.round((pass / total) * 100)
    return { pass, fail, partial, total, pct }
  }, [fw.controls])

  const allStats = FRAMEWORKS.map(f => {
    const pass = f.controls.filter(c => c.status === 'pass').length
    const pct  = Math.round((pass / f.controls.length) * 100)
    return { ...f, pass, pct }
  })

  const domains = [...new Set(fw.controls.map(c => c.domain))]

  const [downloading, setDownloading] = useState(false)
  const isMock = import.meta.env.VITE_MOCK === 'true'
  const mockFilename = `lbro-compliance-audit-${new Date().toISOString().slice(0, 10)}.pdf`

  // Production-only download (mock uses a plain <a> link instead)
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, maxWidth: 900 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1, margin: 0 }}>
            Compliance Audit
          </h2>
          <p style={{ fontSize: 11, color: GRAY, marginTop: 4 }}>
            Internal audit report — GDPR, SOC 2 Type II, ISO 27001 &nbsp;·&nbsp; Generated {new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => navigate('/compliance')}
            style={{ fontSize: 11, color: GRAY, border: `1px solid ${BORDER}`, padding: '7px 14px', borderRadius: 2, background: 'transparent', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em' }}
          >
            Compliance dashboard
          </button>
          {isMock ? (
            <button
              onClick={() => downloadMockPdf(mockFilename)}
              style={{ fontSize: 11, color: BLACK, border: `1px solid ${BORDER}`, padding: '7px 14px', borderRadius: 2, background: PARCH, cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: 5 }}
            >
              <Download style={{ width: 12, height: 12 }} />
              Download PDF
            </button>
          ) : (
            <button
              onClick={handleDownload}
              disabled={downloading}
              style={{ fontSize: 11, color: BLACK, border: `1px solid ${BORDER}`, padding: '7px 14px', borderRadius: 2, background: PARCH, cursor: downloading ? 'wait' : 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: 5, opacity: downloading ? 0.6 : 1 }}
            >
              <Download style={{ width: 12, height: 12 }} />
              {downloading ? 'Generating…' : 'Download PDF'}
            </button>
          )}
        </div>
      </div>

      {/* Overall posture cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {allStats.map(f => (
          <div
            key={f.id}
            onClick={() => setActiveFramework(f.id)}
            style={{
              background: activeFramework === f.id ? PARCH : CREAM,
              border: `1px solid ${activeFramework === f.id ? f.color : BORDER}`,
              borderTop: `3px solid ${f.color}`,
              borderRadius: 4, padding: '16px 18px', cursor: 'pointer', transition: 'border-color 0.15s',
              display: 'flex', alignItems: 'center', gap: 14,
            }}
          >
            <ScoreRing pct={f.pct} color={f.color} label={f.name} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: BLACK, marginBottom: 4 }}>{f.name}</div>
              <div style={{ fontSize: 10, color: GRAY, marginBottom: 8, lineHeight: 1.4 }}>{f.full}</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 10, color: GREEN, background: 'rgba(22,163,74,0.08)', border: '1px solid rgba(22,163,74,0.2)', borderRadius: 2, padding: '2px 6px' }}>{f.pass} pass</span>
                {f.controls.filter(c => c.status === 'partial').length > 0 && <span style={{ fontSize: 10, color: AMBER, background: 'rgba(217,119,6,0.08)', border: '1px solid rgba(217,119,6,0.2)', borderRadius: 2, padding: '2px 6px' }}>{f.controls.filter(c => c.status === 'partial').length} partial</span>}
                {f.controls.filter(c => c.status === 'fail').length > 0 && <span style={{ fontSize: 10, color: RED, background: 'rgba(220,38,38,0.08)', border: '1px solid rgba(220,38,38,0.2)', borderRadius: 2, padding: '2px 6px' }}>{f.controls.filter(c => c.status === 'fail').length} fail</span>}
              </div>
            </div>
            <ChevronRight style={{ width: 14, height: 14, color: activeFramework === f.id ? f.color : GRAY, flexShrink: 0 }} />
          </div>
        ))}
      </div>

      {/* Framework detail */}
      <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderTop: `3px solid ${fw.color}`, borderRadius: 4, padding: 20 }}>

        {/* Framework header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <ShieldCheck style={{ width: 16, height: 16, color: fw.color }} />
              <span style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 22, color: BLACK, letterSpacing: '0.04em' }}>{fw.full}</span>
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: fw.color, background: `${fw.color}18`, border: `1px solid ${fw.color}40`, borderRadius: 2, padding: '2px 8px' }}>{stats.pct}% COMPLIANT</span>
            </div>
            <div style={{ fontSize: 11, color: GRAY }}>Authority: {fw.authority}</div>
            <div style={{ fontSize: 11, color: GRAY }}>Scope: {fw.scope}</div>
          </div>

          {/* Filter */}
          <button
            onClick={() => setShowFindingsOnly(v => !v)}
            style={{
              fontSize: 11, color: showFindingsOnly ? ORANGE : GRAY,
              border: `1px solid ${showFindingsOnly ? ORANGE : BORDER}`,
              padding: '6px 12px', borderRadius: 2, background: 'transparent',
              cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.06em',
              display: 'flex', alignItems: 'center', gap: 5,
            }}
          >
            <AlertTriangle style={{ width: 11, height: 11 }} />
            {showFindingsOnly ? 'Showing findings' : 'Show findings only'}
          </button>
        </div>

        {/* Summary bar */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'Pass',    count: stats.pass,    color: GREEN  },
            { label: 'Partial', count: stats.partial, color: AMBER  },
            { label: 'Fail',    count: stats.fail,    color: RED    },
          ].map(({ label, count, color }) => count > 0 ? (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6, background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '6px 12px' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
              <span style={{ fontSize: 12, fontWeight: 600, color: BLACK }}>{count}</span>
              <span style={{ fontSize: 11, color: GRAY }}>{label}</span>
            </div>
          ) : null)}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '6px 12px', marginLeft: 'auto' }}>
            <BarChart2 style={{ width: 12, height: 12, color: GRAY }} />
            <span style={{ fontSize: 11, color: GRAY }}>{stats.total} controls assessed</span>
          </div>
        </div>

        {/* Controls by domain */}
        {domains.map(domain => {
          const domainControls = controls.filter(c => c.domain === domain)
          if (domainControls.length === 0) return null
          return (
            <div key={domain} style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ flex: 1, height: 1, background: BORDER }} />
                {domain}
                <span style={{ flex: 1, height: 1, background: BORDER }} />
              </div>

              {domainControls.map(ctrl => (
                <div key={ctrl.id} style={{ marginBottom: 6 }}>
                  {/* Control row */}
                  <div
                    onClick={() => setExpandedControl(expandedControl === ctrl.id ? null : ctrl.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      background: PARCH, border: `1px solid ${expandedControl === ctrl.id ? fw.color : BORDER}`,
                      borderLeft: `3px solid ${statusColor(ctrl.status)}`,
                      borderRadius: 4, padding: '10px 14px', cursor: 'pointer', transition: 'border-color 0.15s',
                    }}
                  >
                    <StatusIcon s={ctrl.status} />
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: GRAY, flexShrink: 0, width: 64 }}>{ctrl.id}</span>
                    <span style={{ fontSize: 12, color: BLACK, flex: 1, fontWeight: 500 }}>{ctrl.title}</span>
                    <span style={{ fontSize: 10, fontWeight: 600, color: statusColor(ctrl.status), fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', flexShrink: 0 }}>{statusLabel(ctrl.status)}</span>
                    <ChevronRight style={{ width: 12, height: 12, color: GRAY, flexShrink: 0, transform: expandedControl === ctrl.id ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }} />
                  </div>

                  {/* Expanded detail */}
                  {expandedControl === ctrl.id && (
                    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderTop: 'none', borderRadius: '0 0 4px 4px', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <p style={{ fontSize: 12, color: GRAY, margin: 0, lineHeight: 1.6 }}>{ctrl.description}</p>

                      {ctrl.evidence && (
                        <div>
                          <div style={{ fontSize: 10, fontWeight: 600, color: GREEN, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Evidence</div>
                          <p style={{ fontSize: 12, color: BLACK, margin: 0, lineHeight: 1.6 }}>{ctrl.evidence}</p>
                        </div>
                      )}

                      {ctrl.finding && (
                        <div style={{ background: 'rgba(217,119,6,0.05)', border: '1px solid rgba(217,119,6,0.2)', borderRadius: 4, padding: '10px 14px' }}>
                          <div style={{ fontSize: 10, fontWeight: 600, color: AMBER, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Finding / Remediation Required</div>
                          <p style={{ fontSize: 12, color: BLACK, margin: 0, lineHeight: 1.6 }}>{ctrl.finding}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
        })}
      </div>

      {/* Findings summary */}
      {FRAMEWORKS.some(f => f.controls.some(c => c.finding)) && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <AlertTriangle style={{ width: 14, height: 14, color: ORANGE }} />
            <h3 style={{ fontSize: 12, fontWeight: 600, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>
              Open Findings Requiring Remediation
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {FRAMEWORKS.flatMap(f =>
              f.controls
                .filter(c => c.finding)
                .map(c => (
                  <div key={`${f.id}-${c.id}`} style={{ background: CREAM, border: `1px solid ${BORDER}`, borderLeft: `3px solid ${f.color}`, borderRadius: 4, padding: '12px 16px', display: 'flex', gap: 12 }}>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: f.color, background: `${f.color}18`, border: `1px solid ${f.color}40`, borderRadius: 2, padding: '2px 6px', flexShrink: 0, height: 'fit-content', marginTop: 1 }}>{f.name}</span>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: BLACK, marginBottom: 3 }}>{c.id} — {c.title}</div>
                      <div style={{ fontSize: 11, color: GRAY, lineHeight: 1.5 }}>{c.finding}</div>
                    </div>
                    <span style={{ marginLeft: 'auto', fontSize: 10, color: AMBER, fontWeight: 600, fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', flexShrink: 0 }}>Partial</span>
                  </div>
                ))
            )}
          </div>
        </div>
      )}

      {/* Audit footer */}
      <div style={{ background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <FileText style={{ width: 13, height: 13, color: GRAY, flexShrink: 0 }} />
        <p style={{ fontSize: 11, color: GRAY, margin: 0, lineHeight: 1.6 }}>
          This report shows your current compliance status, derived from live incident and evidence data in LBRO. It is a self-assessment — not a formal audit opinion. For official certification, engage an accredited third-party auditor.
        </p>
      </div>

      {/* Print styles */}
      <style>{`
        @media print {
          body * { visibility: hidden; }
          main, main * { visibility: visible; }
          button { display: none !important; }
        }
      `}</style>
    </div>
  )
}
