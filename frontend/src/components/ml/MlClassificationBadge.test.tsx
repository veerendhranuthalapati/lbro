import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MlClassificationBadge, mlSourceLabel } from '@/components/ml/MlClassificationBadge'

describe('MlClassificationBadge', () => {
  it('mlSourceLabel_model', () => {
    expect(mlSourceLabel('model')).toBe('Model')
  })

  it('mlSourceLabel_heuristic', () => {
    expect(mlSourceLabel('heuristic')).toBe('Heuristic — needs review')
  })

  it('mlSourceLabel_insufficient', () => {
    expect(mlSourceLabel('insufficient_features')).toBe('Insufficient data')
  })

  it('badge_model_with_confidence', () => {
    render(<MlClassificationBadge source="model" confidence={0.91} needsReview={false} />)
    expect(screen.getByTestId('ml-source-badge').textContent).toBe('Model')
    expect(screen.getByTestId('ml-confidence').textContent).toBe('91%')
  })

  it('badge_heuristic_needs_review', () => {
    render(<MlClassificationBadge source="heuristic" needsReview confidence={0.5} />)
    expect(screen.getByTestId('ml-needs-review-badge')).toBeTruthy()
    expect(screen.queryByTestId('ml-confidence')).toBeNull()
  })

  it('badge_insufficient_features', () => {
    render(<MlClassificationBadge source="insufficient_features" needsReview />)
    expect(screen.getByTestId('ml-source-badge').textContent).toBe('Insufficient data')
    expect(screen.getByTestId('ml-needs-review-badge')).toBeTruthy()
  })

  it('badge_model_needs_review_no_confidence', () => {
    render(<MlClassificationBadge source="model" needsReview confidence={0.91} />)
    expect(screen.queryByTestId('ml-confidence')).toBeNull()
  })

  it('badge_ood_and_demo', () => {
    render(
      <MlClassificationBadge source="model" needsReview oodFlag bundleStatus="demo-synthetic" />,
    )
    expect(screen.getByTestId('ml-ood-badge')).toBeTruthy()
    expect(screen.getByTestId('ml-demo-notice')).toBeTruthy()
  })
})
