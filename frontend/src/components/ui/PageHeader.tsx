import type { ReactNode } from 'react'
import { LBRO } from '@/lib/tokens'

interface PageHeaderProps {
  title?: string
  description?: string
  actions?: ReactNode
  /** Hide duplicate title when Navbar already shows it */
  compact?: boolean
}

export function PageHeader({ title, description, actions, compact }: PageHeaderProps) {
  if (compact) {
    return (
      <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
        {description && (
          <p className="text-sm flex-1 min-w-0" style={{ color: LBRO.gray }}>{description}</p>
        )}
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    )
  }

  return (
    <header className="flex flex-wrap items-start justify-between gap-4 mb-6">
      <div className="min-w-0">
        <h1
          className="font-display leading-none mb-1"
          style={{ fontSize: 32, color: LBRO.black, letterSpacing: '0.03em' }}
        >
          {title}
        </h1>
        {description && (
          <p className="text-sm max-w-2xl" style={{ color: LBRO.gray }}>{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </header>
  )
}
