import type { ReactNode } from 'react'
import { LBRO } from '@/lib/tokens'

interface CardProps {
  children: ReactNode
  className?: string
  title?: string
  description?: string
  danger?: boolean
}

export function Card({ children, className = '', title, description, danger }: CardProps) {
  return (
    <section
      className={`rounded-lg border p-5 ${className}`}
      style={{
        background: LBRO.card,
        borderColor: danger ? '#e54e1b44' : LBRO.border,
      }}
    >
      {title && (
        <div className="mb-4">
          <h2
            className="text-sm font-semibold"
            style={{ color: danger ? LBRO.danger : LBRO.black }}
          >
            {title}
          </h2>
          {description && (
            <p className="text-xs mt-0.5" style={{ color: LBRO.gray }}>{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  )
}
