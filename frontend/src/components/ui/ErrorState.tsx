import { AlertTriangle } from 'lucide-react'
import { LBRO } from '@/lib/tokens'

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
}

export function ErrorState({
  message = 'Unable to load this page.',
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center rounded-lg border py-12 px-6"
      style={{ background: LBRO.cream, borderColor: LBRO.border }}
      role="alert"
    >
      <AlertTriangle className="w-8 h-8 mb-3" style={{ color: LBRO.orange }} aria-hidden />
      <p className="text-sm mb-4" style={{ color: LBRO.black }}>{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="px-4 py-2 rounded text-sm font-medium text-white"
          style={{ background: LBRO.orange }}
        >
          Retry
        </button>
      )}
    </div>
  )
}
