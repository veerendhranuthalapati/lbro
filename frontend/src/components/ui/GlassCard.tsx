import { cn } from '@/utils'
import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  className?: string
  glow?: 'orange' | 'red' | 'green' | 'none'
  onClick?: () => void
}

export function GlassCard({ children, className, glow = 'none', onClick }: Props) {
  const glowMap: Record<string, string> = {
    orange: 'border-lbro-orange/40',
    red: 'border-red-400/40',
    green: 'border-green-600/30',
    none: 'border-lbro-border',
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        'rounded border p-4',
        glowMap[glow],
        onClick && 'cursor-pointer transition-colors hover:border-lbro-orange/40',
        className
      )}
      style={{ background: '#f9f5ef', borderColor: glow === 'none' ? '#c8c2b8' : undefined }}
    >
      {children}
    </div>
  )
}
