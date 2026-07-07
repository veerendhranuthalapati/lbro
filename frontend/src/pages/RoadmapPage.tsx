/**
 * Product Roadmap
 *
 * A forward-looking view of planned LBRO features.
 * None of these features are implemented yet — this page is informational only.
 */
import { Sparkles, Cloud, Shield, Bell, Lock, Chrome, Code2, Zap } from 'lucide-react'

const BLACK  = '#111111'
const BORDER = '#e4ddd5'
const GRAY   = '#6b6560'
const CREAM  = '#f9f5ef'
const PARCH  = '#ede8e0'
const ORANGE = '#e54e1b'

const VERSION_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  'v2': { bg: 'rgba(229,78,27,0.07)', text: ORANGE, border: 'rgba(229,78,27,0.25)' },
  'v3': { bg: 'rgba(99,102,241,0.07)', text: '#6366f1', border: 'rgba(99,102,241,0.25)' },
}

interface RoadmapItem {
  version: 'v2' | 'v3'
  icon: React.ReactNode
  title: string
  description: string
}

const ITEMS: RoadmapItem[] = [
  {
    version: 'v2',
    icon: <Sparkles style={{ width: 16, height: 16 }} />,
    title: 'LBRO Agent',
    description: 'An autonomous security agent that monitors your application 24/7, classifies threats in real time, and can initiate containment workflows without human input — while keeping you in the loop.',
  },
  {
    version: 'v2',
    icon: <Cloud style={{ width: 16, height: 16 }} />,
    title: 'Cloudflare Integration',
    description: 'Connect LBRO to your Cloudflare account to pull WAF events, DDoS signals, and bot scores directly into the incident timeline. No more switching between dashboards.',
  },
  {
    version: 'v2',
    icon: <Shield style={{ width: 16, height: 16 }} />,
    title: 'AWS WAF Integration',
    description: 'Pull AWS WAF rule match events and managed rule group findings into LBRO automatically. Incidents are created, classified, and linked to the offending rule.',
  },
  {
    version: 'v2',
    icon: <Bell style={{ width: 16, height: 16 }} />,
    title: 'Slack Notifications',
    description: 'Get real-time Slack alerts for critical incidents, compliance deadlines, and high-priority recommendations — delivered to the channel of your choice with a one-click acknowledge button.',
  },
  {
    version: 'v3',
    icon: <Lock style={{ width: 16, height: 16 }} />,
    title: 'Automatic IP Blocking',
    description: 'When LBRO detects a confirmed attack from a specific IP, it can automatically update your firewall rules (Cloudflare, AWS WAF, or a custom webhook) to block it — with a configurable review window.',
  },
  {
    version: 'v3',
    icon: <Chrome style={{ width: 16, height: 16 }} />,
    title: 'Browser Extension',
    description: 'A lightweight browser extension that lets you receive LBRO alerts, acknowledge incidents, and check your security score without opening a new tab.',
  },
  {
    version: 'v3',
    icon: <Code2 style={{ width: 16, height: 16 }} />,
    title: 'VS Code Extension',
    description: 'View your live security posture, open incidents, and recommendations directly inside VS Code. Designed for developers who want security context without leaving their editor.',
  },
]

function RoadmapCard({ item }: { item: RoadmapItem }) {
  const vc = VERSION_COLORS[item.version]
  return (
    <div style={{
      background: CREAM,
      border: `1px solid ${BORDER}`,
      borderRadius: 6,
      padding: '20px 22px',
      display: 'flex',
      gap: 16,
    }}>
      <div style={{
        width: 38, height: 38, borderRadius: 6,
        background: vc.bg,
        border: `1px solid ${vc.border}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: vc.text, flexShrink: 0,
      }}>
        {item.icon}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: BLACK }}>{item.title}</span>
          <span style={{
            fontSize: 10, fontFamily: 'JetBrains Mono, monospace',
            color: vc.text, background: vc.bg, border: `1px solid ${vc.border}`,
            borderRadius: 3, padding: '2px 7px',
          }}>
            {item.version === 'v2' ? 'Version 2' : 'Version 3'}
          </span>
          <span style={{
            fontSize: 10, fontFamily: 'JetBrains Mono, monospace',
            color: GRAY, background: PARCH, border: `1px solid ${BORDER}`,
            borderRadius: 3, padding: '2px 7px', marginLeft: 'auto',
          }}>
            Coming Soon
          </span>
        </div>
        <p style={{ fontSize: 13, color: GRAY, lineHeight: 1.7, margin: 0 }}>
          {item.description}
        </p>
      </div>
    </div>
  )
}

const V2_ITEMS = ITEMS.filter(i => i.version === 'v2')
const V3_ITEMS = ITEMS.filter(i => i.version === 'v3')

export default function RoadmapPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28, maxWidth: 760 }}>

      {/* Header */}
      <div>
        <h1 style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 48, color: BLACK, letterSpacing: '0.04em', lineHeight: 1, margin: 0 }}>
          Roadmap
        </h1>
        <p style={{ fontSize: 12, color: GRAY, marginTop: 6, lineHeight: 1.6 }}>
          What's coming to LBRO. None of these features are available today — this page is a preview only.
        </p>
      </div>

      {/* Version 2 */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <div style={{
            fontFamily: "'Bebas Neue', sans-serif", fontSize: 18, letterSpacing: '0.1em',
            color: ORANGE,
          }}>
            Version 2
          </div>
          <div style={{ flex: 1, height: 1, background: BORDER }} />
          <span style={{
            fontSize: 10, fontFamily: 'JetBrains Mono, monospace',
            color: ORANGE, background: 'rgba(229,78,27,0.07)',
            border: '1px solid rgba(229,78,27,0.25)',
            borderRadius: 3, padding: '2px 8px',
          }}>
            Integrations & Automation
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {V2_ITEMS.map(item => <RoadmapCard key={item.title} item={item} />)}
        </div>
      </div>

      {/* Version 3 */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <div style={{
            fontFamily: "'Bebas Neue', sans-serif", fontSize: 18, letterSpacing: '0.1em',
            color: '#6366f1',
          }}>
            Version 3
          </div>
          <div style={{ flex: 1, height: 1, background: BORDER }} />
          <span style={{
            fontSize: 10, fontFamily: 'JetBrains Mono, monospace',
            color: '#6366f1', background: 'rgba(99,102,241,0.07)',
            border: '1px solid rgba(99,102,241,0.25)',
            borderRadius: 3, padding: '2px 8px',
          }}>
            Active Defence & Developer Tools
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {V3_ITEMS.map(item => <RoadmapCard key={item.title} item={item} />)}
        </div>
      </div>

      {/* Note */}
      <div style={{
        background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '14px 18px',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <Zap style={{ width: 13, height: 13, color: ORANGE, flexShrink: 0 }} />
        <p style={{ fontSize: 12, color: GRAY, margin: 0, lineHeight: 1.6 }}>
          Roadmap priorities may shift based on user feedback. Have a feature request? Contact us through the Settings page.
        </p>
      </div>
    </div>
  )
}
