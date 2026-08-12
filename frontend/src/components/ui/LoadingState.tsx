import { Loader2 } from 'lucide-react'
import { LBRO } from '@/lib/tokens'

interface LoadingStateProps {
  label?: string
}

export function LoadingState({ label = 'Loading…' }: LoadingStateProps) {
  return (
    <div
      className="flex items-center justify-center gap-2 py-16 text-sm"
      style={{ color: LBRO.gray }}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
      {label}
    </div>
  )
}
