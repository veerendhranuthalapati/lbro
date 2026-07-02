import type { LucideIcon } from 'lucide-react'

interface Props {
  label: string
  value: string | number
  sub?: string
  icon: LucideIcon
  accent?: 'orange' | 'red' | 'green' | 'amber' | 'purple' | 'cyan'
  trend?: 'up' | 'down' | 'neutral'
}

const accentMap: Record<string, { value: string; dot: string }> = {
  orange: { value: '#e54e1b', dot: '#e54e1b' },
  red:    { value: '#e54e1b', dot: '#e54e1b' },
  cyan:   { value: '#e54e1b', dot: '#e54e1b' },
  amber:  { value: '#d97706', dot: '#d97706' },
  green:  { value: '#3a7a50', dot: '#3a7a50' },
  purple: { value: '#7c3aed', dot: '#7c3aed' },
}

export function StatCard({ label, value, sub, icon: Icon, accent = 'orange' }: Props) {
  const a = accentMap[accent] ?? accentMap.orange
  return (
    <div style={{ background: '#f9f5ef', border: '1px solid #c8c2b8', borderRadius: 4, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 10, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#6b6560' }}>
          {label}
        </span>
        <Icon style={{ width: 14, height: 14, color: a.dot }} aria-hidden="true" />
      </div>
      <div>
        <div style={{ fontFamily: "'Bebas Neue', sans-serif", fontSize: 36, lineHeight: 1, color: a.value, letterSpacing: '0.02em' }}>
          {value}
        </div>
        {sub && (
          <div style={{ fontSize: 11, marginTop: 4, color: '#6b6560' }}>
            {sub}
          </div>
        )}
      </div>
    </div>
  )
}
