import { cn } from '@/utils'
import type { IncidentStatus } from '@/types'

interface Props {
  status: IncidentStatus
  size?: 'sm' | 'md'
}

const STATUS_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  detected:    { color: '#e54e1b', bg: 'rgba(229,78,27,0.08)', border: 'rgba(229,78,27,0.3)' },
  escalated:   { color: '#e54e1b', bg: 'rgba(229,78,27,0.08)', border: 'rgba(229,78,27,0.3)' },
  triaging:    { color: '#d97706', bg: 'rgba(217,119,6,0.08)', border: 'rgba(217,119,6,0.3)' },
  containing:  { color: '#d97706', bg: 'rgba(217,119,6,0.08)', border: 'rgba(217,119,6,0.3)' },
  contained:   { color: '#3a7a50', bg: 'rgba(58,122,80,0.08)', border: 'rgba(58,122,80,0.3)' },
  notifying:   { color: '#111111', bg: 'rgba(17,17,17,0.06)', border: '#c8c2b8' },
  closed:      { color: '#3a7a50', bg: 'rgba(58,122,80,0.08)', border: 'rgba(58,122,80,0.3)' },
  investigating: { color: '#6b6560', bg: 'rgba(107,101,96,0.08)', border: '#c8c2b8' },
}

const LABEL: Record<string, string> = {
  detected:    'Detected',
  escalated:   'Escalated',
  triaging:    'Triaging',
  containing:  'Containing',
  contained:   'Contained',
  notifying:   'Notifying',
  closed:      'Closed',
  investigating: 'Investigating',
}

export function StatusBadge({ status, size = 'md' }: Props) {
  const s = STATUS_STYLES[status] ?? { color: '#6b6560', bg: 'rgba(107,101,96,0.08)', border: '#c8c2b8' }
  return (
    <span
      className={cn(
        'inline-flex items-center font-mono font-medium border',
        size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1',
      )}
      style={{
        color: s.color,
        background: s.bg,
        borderColor: s.border,
        borderRadius: 2,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
      }}
    >
      {LABEL[status] ?? status}
    </span>
  )
}
