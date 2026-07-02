import { cn } from '@/utils'
import type { IncidentSeverity } from '@/types'

interface Props {
  severity: IncidentSeverity
  size?: 'sm' | 'md'
  pulse?: boolean
  ariaLabel?: string
}

// Keys must match backend IncidentSeverity enum (lowercase)
const SEV_STYLES: Record<string, { color: string; bg: string; border: string; dot: string }> = {
  critical: { color: '#e54e1b', bg: 'rgba(229,78,27,0.08)', border: 'rgba(229,78,27,0.35)', dot: '#e54e1b' },
  high:     { color: '#d97706', bg: 'rgba(217,119,6,0.08)', border: 'rgba(217,119,6,0.35)', dot: '#d97706' },
  medium:   { color: '#6b6560', bg: 'rgba(107,101,96,0.08)', border: 'rgba(107,101,96,0.35)', dot: '#6b6560' },
  low:      { color: '#3a7a50', bg: 'rgba(58,122,80,0.08)', border: 'rgba(58,122,80,0.35)', dot: '#4ade80' },
  info:     { color: '#3b82f6', bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.35)', dot: '#3b82f6' },
}

export function SeverityBadge({ severity, size = 'md', pulse = false, ariaLabel }: Props) {
  const s = SEV_STYLES[severity] ?? SEV_STYLES.medium
  return (
    <span
      role="status"
      aria-label={ariaLabel ?? `Severity: ${severity}`}
      className={cn(
        'inline-flex items-center gap-1.5 font-mono font-semibold border',
        size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1',
      )}
      style={{
        color: s.color,
        background: s.bg,
        borderColor: s.border,
        borderRadius: 2,
        textTransform: 'uppercase',
        letterSpacing: '0.06em',
      }}
    >
      <span
        aria-hidden="true"
        className={cn(
          'rounded-full flex-shrink-0',
          size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2',
          pulse && severity === 'critical' && 'animate-pulse',
        )}
        style={{ background: s.dot }}
      />
      {severity}
    </span>
  )
}
