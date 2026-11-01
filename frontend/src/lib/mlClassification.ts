/**
 * Map incident API fields to ML badge props (no raw event required).
 */
import type { Incident } from '@/types'
import type { MlClassificationBadgeProps } from '@/components/ml/MlClassificationBadge'

export function incidentMlBadgeProps(incident: Incident): MlClassificationBadgeProps {
  if (incident.ml_classification_status === 'pending' && !incident.attack_category) {
    return { source: 'insufficient_features', needsReview: true }
  }
  const source = incident.ml_model_version ? 'model' : 'heuristic'
  return {
    source,
    needsReview: incident.needs_analyst_review,
    confidence: incident.confidence_score,
  }
}
