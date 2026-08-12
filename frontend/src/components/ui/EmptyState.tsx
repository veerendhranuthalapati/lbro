import type { ReactNode } from 'react'
import { LBRO } from '@/lib/tokens'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
}

export function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center rounded-lg border py-12 px-6"
      style={{ background: LBRO.cream, borderColor: LBRO.border }}
      role="status"
    >
      {icon && <div className="mb-3 opacity-60">{icon}</div>}
      <p className="font-medium text-sm mb-1" style={{ color: LBRO.black }}>{title}</p>
      {description && (
        <p className="text-sm max-w-md mb-4" style={{ color: LBRO.gray }}>{description}</p>
      )}
      {action}
    </div>
  )
}
