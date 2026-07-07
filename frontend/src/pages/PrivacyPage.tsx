/**
 * Privacy & Data Handling
 *
 * Plain-English explanation of what LBRO stores, how it protects data,
 * what gets redacted, and how long records are kept.
 */
import { Lock, Shield, Database, Clock, Eye, CheckCircle } from 'lucide-react'

const BLACK  = '#111111'
const BORDER = '#e4ddd5'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#ede8e0'
const ORANGE = '#e54e1b'
const GREEN  = '#16a34a'

function Section({
  icon, title, children,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}) {
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '22px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 16, paddingBottom: 14, borderBottom: `1px solid ${BORDER}` }}>
        {icon}
        <h2 style={{ fontSize: 13, fontWeight: 600, color: BLACK, margin: 0 }}>{title}</h2>
      </div>
      {children}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '9px 0', borderBottom: `1px solid ${BORDER}` }}>
      <span style={{ fontSize: 13, color: BLACK }}>{label}</span>
      <span style={{ fontSize: 12, fontFamily: 'JetBrains Mono, monospace', color: GRAY }}>{value}</span>
    </div>
  )
}

function Chip({ text }: { text: string }) {
  return (
    <span style={{
      display: 'inline-block',
      fontSize: 11,
      fontFamily: 'JetBrains Mono, monospace',
      color: ORANGE,
      background: 'rgba(229,78,27,0.07)',
      border: '1px solid rgba(229,78,27,0.25)',
      borderRadius: 3,
      padding: '3px 8px',
      marginRight: 6,
      marginBottom: 6,
    }}>
      {text}
    </span>
  )
}

function BulletItem({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
      <CheckCircle style={{ width: 14, height: 14, color: GREEN, flexShrink: 0, marginTop: 1 }} />
      <span style={{ fontSize: 13, color: BLACK, lineHeight: 1.7 }}>{children}</span>
    </div>
  )
}

export default function PrivacyPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 720 }}>

      {/* Header */}
      <div>
        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1, margin: 0 }}>
          Privacy & Data
        </h1>
        <p style={{ fontSize: 12, color: GRAY, marginTop: 6, lineHeight: 1.6 }}>
          How LBRO handles your data — what we store, how we protect it, and how long we keep it.
        </p>
      </div>

      {/* Transport security */}
      <Section icon={<Lock style={{ width: 15, height: 15, color: ORANGE }} />} title="Transport Security">
        <BulletItem>
          All communication between your browser and the LBRO API uses <strong>TLS (HTTPS)</strong>. Data is encrypted in transit and cannot be read by anyone between you and the server.
        </BulletItem>
        <BulletItem>
          API requests are authenticated using short-lived <strong>Bearer tokens (JWT)</strong>. Tokens expire automatically and are never stored in cookies or local storage.
        </BulletItem>
        <BulletItem>
          Security headers are enforced on every response: <strong>Strict-Transport-Security</strong>, <strong>Content-Security-Policy</strong>, <strong>X-Frame-Options</strong>, and more.
        </BulletItem>
      </Section>

      {/* What gets redacted */}
      <Section icon={<Eye style={{ width: 15, height: 15, color: ORANGE }} />} title="What We Redact Before Long-Term Storage">
        <p style={{ fontSize: 13, color: GRAY, lineHeight: 1.7, marginBottom: 16 }}>
          Sensitive values are identified using pattern-based rules and replaced with a placeholder before any record is written to long-term storage. The original value is never stored.
        </p>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: GRAY, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Redacted automatically</div>
          <div style={{ display: 'flex', flexWrap: 'wrap' }}>
            <Chip text="Passwords" />
            <Chip text="API keys" />
            <Chip text="Bearer tokens" />
            <Chip text="Authorization headers" />
            <Chip text="Credit card numbers" />
            <Chip text="Social security numbers" />
            <Chip text="Email addresses (in payloads)" />
            <Chip text="Phone numbers" />
            <Chip text="Private IP ranges" />
          </div>
        </div>

        <div style={{ background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '12px 16px', fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: GRAY, lineHeight: 1.7 }}>
          <div style={{ color: BLACK, marginBottom: 4, fontFamily: 'inherit', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Example — before and after</div>
          <div><span style={{ color: '#dc2626' }}>Authorization: Bearer eyJhbGc...</span></div>
          <div style={{ color: GRAY, margin: '4px 0' }}>↓ stored as</div>
          <div><span style={{ color: GREEN }}>Authorization: [REDACTED]</span></div>
        </div>
      </Section>

      {/* What is stored */}
      <Section icon={<Database style={{ width: 15, height: 15, color: ORANGE }} />} title="What We Analyse and Store">
        <p style={{ fontSize: 13, color: GRAY, lineHeight: 1.7, marginBottom: 16 }}>
          LBRO analyses <strong>behavioural metadata</strong> — network flow patterns, timing, protocol usage, and traffic volume — not the content of your users' data. Long-term storage contains only sanitised events.
        </p>
        <BulletItem>
          <strong>Network flow metadata:</strong> source IP, destination IP, ports, protocol, packet counts, byte counts, timing.
        </BulletItem>
        <BulletItem>
          <strong>Incident records:</strong> attack category, severity, status, assigned user, and response timeline. No raw payload content.
        </BulletItem>
        <BulletItem>
          <strong>Compliance records:</strong> regulation name, deadline, status. No personal health or financial records.
        </BulletItem>
        <BulletItem>
          <strong>Audit logs:</strong> user action, resource type, timestamp, IP address, HTTP method, and response status. No request or response bodies.
        </BulletItem>
        <BulletItem>
          <strong>Evidence packages:</strong> files uploaded by your team, stored encrypted in S3 with access-controlled pre-signed URLs.
        </BulletItem>
      </Section>

      {/* Authentication data */}
      <Section icon={<Shield style={{ width: 15, height: 15, color: ORANGE }} />} title="Authentication & Credentials">
        <BulletItem>
          <strong>Passwords</strong> are hashed with bcrypt before storage. The original password is never stored or transmitted after login.
        </BulletItem>
        <BulletItem>
          <strong>Session tokens (JWT)</strong> are stored only in browser memory for the duration of your session. They are cleared when you close the tab. Refresh tokens are stored in sessionStorage — not localStorage — and cleared on browser close.
        </BulletItem>
        <BulletItem>
          <strong>API keys</strong> are single-use secrets generated on rotation. They are shown once and never retrieved again. Store them securely.
        </BulletItem>
        <BulletItem>
          <strong>MFA secrets</strong> (when enabled) are stored encrypted and are only used to verify TOTP codes. They are never returned by the API.
        </BulletItem>
      </Section>

      {/* Retention */}
      <Section icon={<Clock style={{ width: 15, height: 15, color: ORANGE }} />} title="Data Retention Policy">
        <p style={{ fontSize: 13, color: GRAY, lineHeight: 1.7, marginBottom: 16 }}>
          Data is retained only as long as needed for its security purpose. Older records are purged automatically on the schedule below.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {[
            { label: 'Routine network flow events', retention: '7 days', note: 'High volume, short-lived diagnostic value' },
            { label: 'Dashboard & analytics aggregates', retention: '30 days', note: 'Trend data for weekly reports' },
            { label: 'Security incidents', retention: '90 days', note: 'Required for post-incident review' },
            { label: 'Audit logs', retention: '180 days', note: 'Required for regulatory compliance' },
            { label: 'Compliance records', retention: '365 days', note: 'Required by GDPR, HIPAA, DPDPA obligations' },
            { label: 'Evidence packages', retention: 'Manual deletion', note: 'Files kept until manually deleted by your team' },
          ].map(r => (
            <div key={r.label} style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '10px 0', borderBottom: `1px solid ${BORDER}` }}>
              <div>
                <div style={{ fontSize: 13, color: BLACK, marginBottom: 2 }}>{r.label}</div>
                <div style={{ fontSize: 11, color: GRAY }}>{r.note}</div>
              </div>
              <div style={{
                fontSize: 12,
                fontFamily: 'JetBrains Mono, monospace',
                color: BLACK,
                background: PARCH,
                border: `1px solid ${BORDER}`,
                borderRadius: 3,
                padding: '3px 10px',
                flexShrink: 0,
                marginLeft: 16,
              }}>
                {r.retention}
              </div>
            </div>
          ))}
        </div>

        <p style={{ fontSize: 12, color: GRAY, marginTop: 16, lineHeight: 1.7 }}>
          To request early deletion of your data, contact your account administrator. LBRO does not share data with third parties.
        </p>
      </Section>

    </div>
  )
}
