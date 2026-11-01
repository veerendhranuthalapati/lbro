"""Typed ML classification result — single contract for API, worker, and events."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ClassificationSource = Literal["model", "heuristic", "insufficient_features"]


@dataclass
class TopClassProbability:
    """One entry in the top-k probability list."""

    attack_category: str
    probability: float


@dataclass
class ClassificationResult:
    """
    Canonical output of AttackClassifier.predict().

    Backward-compatible dict keys are produced by ``to_dict()`` so existing
    callers that expect ``probabilities`` / ``top_features`` keep working.
    """

    attack_category: str
    is_attack: bool
    severity: str
    confidence: float
    top_k: list[TopClassProbability]
    source: ClassificationSource
    model_version: str
    feature_coverage: float
    ood_score: float
    ood_flag: bool
    needs_review: bool
    reasons: list[str] = field(default_factory=list)
    # Legacy explainability — populated for model/heuristic paths when available.
    top_features: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON responses and IncidentAction metadata."""
        proba_map = {t.attack_category: t.probability for t in self.top_k}
        # Include full probability map under legacy key when we only store top-k.
        return {
            "attack_category": self.attack_category,
            "is_attack": self.is_attack,
            "severity": self.severity,
            "confidence": self.confidence,
            "top_k": [
                {"attack_category": t.attack_category, "probability": t.probability}
                for t in self.top_k
            ],
            "source": self.source,
            "model_version": self.model_version,
            "feature_coverage": self.feature_coverage,
            "ood_score": self.ood_score,
            "ood_flag": self.ood_flag,
            "needs_review": self.needs_review,
            "reasons": self.reasons,
            "probabilities": proba_map,
            "top_features": self.top_features,
        }
