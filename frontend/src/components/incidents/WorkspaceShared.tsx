/**
 * Shared primitives for the Incident Investigation Workspace.
 * Imported by all tab components to ensure visual consistency.
 */
export const ORANGE = '#e54e1b'
export const BLACK  = '#111111'
export const BORDER = '#c8c2b8'
export const GRAY   = '#6b6560'
export const CREAM  = '#f9f5ef'
export const PARCH  = '#e8e2d9'
export const GREEN  = '#3a7a50'
export const BLUE   = '#3b82f6'

export function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 4, padding: 16, ...style }}>
      {children}
    </div>
  )
}

export function CardHead({
  icon, title, extra,
}: { icon: React.ReactNode; title: string; extra?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
      {icon}
      <span style={{ fontSize: 10, fontWeight: 600, color: BLACK, textTransform: 'uppercase', letterSpacing: '0.09em' }}>
        {title}
      </span>
      {extra && <span style={{ marginLeft: 'auto' }}>{extra}</span>}
    </div>
  )
}

export function KV({ label, value, mono = false }: { label: string; value: string | number | null | undefined; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, padding: '5px 0', borderBottom: `1px solid ${PARCH}` }}>
      <span style={{ color: GRAY, flexShrink: 0, marginRight: 8 }}>{label}</span>
      <span style={{
        fontFamily: mono ? 'JetBrains Mono, monospace' : undefined,
        fontSize: mono ? 10 : 11,
        color: BLACK,
        textAlign: 'right',
        wordBreak: 'break-all',
      }}>
        {value ?? '—'}
      </span>
    </div>
  )
}

export function Tag({ text, color }: { text: string; color?: string }) {
  return (
    <span style={{
      display: 'inline-block',
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: 9,
      color: color ?? GRAY,
      background: color ? `${color}18` : PARCH,
      border: `1px solid ${color ? `${color}40` : BORDER}`,
      borderRadius: 2,
      padding: '2px 7px',
      marginRight: 5,
      marginBottom: 4,
    }}>
      {text}
    </span>
  )
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = React.useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }
  return (
    <button
      onClick={copy}
      style={{
        fontSize: 9, color: copied ? GREEN : ORANGE,
        border: `1px solid ${copied ? GREEN : ORANGE}30`,
        background: copied ? `${GREEN}10` : `${ORANGE}08`,
        borderRadius: 2, padding: '2px 8px', cursor: 'pointer',
        textTransform: 'uppercase', letterSpacing: '0.06em', transition: 'all .2s',
      }}
    >
      {copied ? '✓ Copied' : label}
    </button>
  )
}

export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} style={{ height: 11, background: PARCH, borderRadius: 2, width: `${70 + (i % 3) * 10}%` }} />
      ))}
    </div>
  )
}

export function ActionBtn({
  label, onClick, variant = 'default', disabled = false,
}: { label: string; onClick: () => void; variant?: 'default' | 'primary' | 'danger'; disabled?: boolean }) {
  const bg = variant === 'primary' ? ORANGE : variant === 'danger' ? '#ef444420' : 'transparent'
  const col = variant === 'primary' ? '#fff' : variant === 'danger' ? '#ef4444' : GRAY
  const bdr = variant === 'primary' ? ORANGE : variant === 'danger' ? '#ef444440' : BORDER
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontSize: 10, fontWeight: 500, color: disabled ? BORDER : col,
        background: disabled ? 'transparent' : bg,
        border: `1px solid ${disabled ? BORDER : bdr}`,
        borderRadius: 2, padding: '6px 12px', cursor: disabled ? 'not-allowed' : 'pointer',
        textTransform: 'uppercase', letterSpacing: '0.07em', transition: 'opacity .15s',
        opacity: disabled ? 0.5 : 1,
        width: '100%', textAlign: 'left',
      }}
    >
      {label}
    </button>
  )
}

// Re-export React so tab files can use it without another import
import React from 'react'
export { React }
