import { LBRO } from '@/lib/tokens'

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin',
  analyst: 'Analyst',
  viewer: 'Viewer',
  owner: 'Owner',
}

export function RoleBadge({ role }: { role: string }) {
  const label = ROLE_LABELS[role] ?? role
  return (
    <span
      className="text-[10px] uppercase tracking-wide font-medium px-1.5 py-0.5 rounded"
      style={{ background: LBRO.parchment, color: LBRO.gray }}
    >
      {label}
    </span>
  )
}
