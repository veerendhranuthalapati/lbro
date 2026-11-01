/**
 * Badges for ML classification source, review state, and demo bundle notice.
 */
export type MlClassificationSource = 'model' | 'heuristic' | 'insufficient_features' | string | null | undefined

export interface MlClassificationBadgeProps {
  source?: MlClassificationSource
  needsReview?: boolean | null
  oodFlag?: boolean | null
  bundleStatus?: string | null
  confidence?: number | null
}

export function mlSourceLabel(source: MlClassificationSource): string {
  if (!source || source === 'model') return 'Model'
  if (source === 'heuristic') return 'Heuristic — needs review'
  if (source === 'insufficient_features') return 'Insufficient data'
  return String(source)
}

export function MlClassificationBadge({
  source,
  needsReview,
  oodFlag,
  bundleStatus,
  confidence,
}: MlClassificationBadgeProps) {
  const isDemo = bundleStatus === 'demo-synthetic'
  const showConfidence = source === 'model' && confidence != null && !needsReview

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      {source && (
        <span
          data-testid="ml-source-badge"
          className="text-xs px-1.5 py-0.5 rounded border border-[#c8c2b8]"
          style={{ color: source === 'model' ? '#15803d' : '#b45309' }}
        >
          {mlSourceLabel(source)}
        </span>
      )}
      {needsReview && (
        <span data-testid="ml-needs-review-badge" className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
          Needs review
        </span>
      )}
      {oodFlag && (
        <span data-testid="ml-ood-badge" className="text-xs px-1.5 py-0.5 rounded bg-orange-100 text-orange-900">
          OOD
        </span>
      )}
      {isDemo && (
        <span data-testid="ml-demo-notice" className="text-xs px-1.5 py-0.5 rounded bg-zinc-200 text-zinc-800">
          Demo model
        </span>
      )}
      {showConfidence && (
        <span data-testid="ml-confidence" className="text-xs font-mono text-zinc-600">
          {(confidence * 100).toFixed(0)}%
        </span>
      )}
    </span>
  )
}
