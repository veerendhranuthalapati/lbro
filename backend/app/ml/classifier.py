"""CICIDS2017 attack classifier — signed bundle + honest confidence contract."""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np

from app.config import settings
from app.ml.bundle_io import BundleLoadError, LoadedBundle, load_verified_bundle
from app.ml.contract import ClassificationResult, TopClassProbability
from app.ml.features import ATTACK_CLASSES, CICIDS2017_FEATURES, SEVERITY_MAP
from app.ml.heuristic import heuristic_classify
from app.ml.metrics_public import sanitize_metrics_summary_for_public
from app.ml.preprocessing import (
    build_imputation_vector,
    compute_ood_fraction,
    count_supplied_features,
    sanitize_feature_dict,
)

logger = logging.getLogger(__name__)


class AttackClassifier:
    """Thread-safe singleton that loads one verified bundle per process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bundle: LoadedBundle | None = None
        self._load_error_reason: str | None = None
        self._load_error_code: str | None = None
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                self._bundle = load_verified_bundle()
                self._load_error_reason = None
                self._load_error_code = None
                logger.info(
                    "ML bundle loaded version=%s status=%s verified=%s",
                    self._bundle.version,
                    self._bundle.status,
                    self._bundle.signature_verified,
                )
            except BundleLoadError as exc:
                self._bundle = None
                self._load_error_code = exc.reason_code
                self._load_error_reason = str(exc)
                logger.error(
                    "ML bundle load failed [%s]: %s — heuristic fallback active",
                    exc.reason_code,
                    exc,
                )
            except Exception as exc:
                self._bundle = None
                self._load_error_code = "unexpected_load_error"
                self._load_error_reason = str(exc)
                logger.error("ML bundle load failed: %s", exc)
            self._loaded = True

    def reload(self) -> None:
        """Force reload (intended for super-admin tooling only)."""
        with self._lock:
            self._loaded = False
            self._bundle = None
            self._load_error_reason = None
            self._load_error_code = None
        self._load()

    @property
    def load_error_reason(self) -> str | None:
        self._load()
        return self._load_error_reason

    @property
    def load_error_code(self) -> str | None:
        self._load()
        return self._load_error_code

    @property
    def bundle(self) -> LoadedBundle | None:
        self._load()
        return self._bundle

    def status_snapshot(self) -> dict[str, Any]:
        self._load()
        b = self._bundle
        return {
            "model_version": b.version if b else settings.ML_MODEL_VERSION,
            "bundle_status": b.status if b else "unavailable",
            "signature_verified": b.signature_verified if b else False,
            "load_error_reason": self._load_error_reason,
            "load_error_code": self._load_error_code,
            "heuristic_fallback_active": b is None,
            "metrics_summary": sanitize_metrics_summary_for_public(b.manifest) if b else {},
            "thresholds": {
                "ML_CONFIDENCE_THRESHOLD": settings.ML_CONFIDENCE_THRESHOLD,
                "ML_REVIEW_THRESHOLD": settings.ML_REVIEW_THRESHOLD,
                "ML_MIN_FEATURE_COVERAGE": settings.ML_MIN_FEATURE_COVERAGE,
                "ML_OOD_MAX_OUTLIER_FRACTION": settings.ML_OOD_MAX_OUTLIER_FRACTION,
                "ML_HEURISTIC_MAX_CONFIDENCE": settings.ML_HEURISTIC_MAX_CONFIDENCE,
                "ML_AUTO_CONTAIN_ENABLED": settings.ML_AUTO_CONTAIN_ENABLED,
                "ML_AUTO_CONTAIN_THRESHOLD": settings.ML_AUTO_CONTAIN_THRESHOLD,
            },
        }

    def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        """Return classification dict (legacy-compatible) from ``ClassificationResult``."""
        return self.predict_result(features).to_dict()

    classify = predict

    def predict_result(self, features: dict[str, Any]) -> ClassificationResult:
        self._load()
        supplied, coverage = count_supplied_features(features or {})
        cleaned, sanitize_reasons = sanitize_feature_dict(features or {})

        if coverage < settings.ML_MIN_FEATURE_COVERAGE:
            reasons = sanitize_reasons + [f"low_feature_coverage:{coverage:.2f}"]
            result = heuristic_classify(
                cleaned or features or {}, feature_coverage=coverage, reasons=reasons
            )
            result.source = "insufficient_features"
            return result

        if self._bundle is None:
            reasons = sanitize_reasons + [self._load_error_code or "model_unavailable"]
            return heuristic_classify(cleaned, feature_coverage=coverage, reasons=reasons)

        return self._predict_with_bundle(cleaned, coverage, sanitize_reasons)

    def _predict_with_bundle(
        self,
        cleaned: dict[str, float],
        coverage: float,
        sanitize_reasons: list[str],
    ) -> ClassificationResult:
        bundle = self._bundle
        assert bundle is not None

        reasons = list(sanitize_reasons)
        ood_fraction, ood_flag = compute_ood_fraction(
            cleaned, bundle.low_bounds, bundle.high_bounds
        )
        if ood_fraction > settings.ML_OOD_MAX_OUTLIER_FRACTION:
            ood_flag = True

        # Uniform dense vectors (e.g. all 1.0 with only port differing) are not real flows.
        if cleaned and coverage >= settings.ML_MIN_FEATURE_COVERAGE:
            values = list(cleaned.values())
            if len(values) >= 10:
                from collections import Counter

                counts = Counter(values)
                most_common_count = counts.most_common(1)[0][1]
                if most_common_count / len(values) >= 0.90:
                    ood_flag = True
                    reasons.append("mostly_uniform_feature_vector")
            if len(set(values)) == 1:
                ood_flag = True
                reasons.append("uniform_feature_vector")
            elif np.std(values) < 1e-6:
                ood_flag = True
                reasons.append("near_zero_feature_variance")

        vec = build_imputation_vector(cleaned, bundle.medians)
        try:
            probas = bundle.model.predict_proba(vec)[0]
        except Exception as exc:
            logger.error("Model predict_proba failed: %s", exc)
            return heuristic_classify(
                cleaned,
                feature_coverage=coverage,
                reasons=sanitize_reasons + ["predict_proba_failed"],
            )

        class_idx = int(np.argmax(probas))
        raw_confidence = float(probas[class_idx])
        classes = bundle.classes or ATTACK_CLASSES
        attack_category = classes[class_idx] if class_idx < len(classes) else "Unknown"

        sorted_idx = np.argsort(probas)[::-1][:3]
        top_k = [
            TopClassProbability(classes[i] if i < len(classes) else "Unknown", float(probas[i]))
            for i in sorted_idx
        ]

        confidence = raw_confidence
        needs_review = confidence < settings.ML_REVIEW_THRESHOLD

        if ood_flag:
            reasons.append(f"ood_outlier_fraction:{ood_fraction:.2f}")
            confidence = min(confidence, settings.ML_HEURISTIC_MAX_CONFIDENCE)
            needs_review = True

        if coverage >= 0.99 and ood_flag:
            reasons.append("full_coverage_but_ood")
            confidence = min(confidence, settings.ML_HEURISTIC_MAX_CONFIDENCE)
            needs_review = True

        top_features = self._compute_top_features(vec[0])

        return ClassificationResult(
            attack_category=attack_category,
            is_attack=attack_category != "BENIGN",
            severity=SEVERITY_MAP.get(attack_category, "medium"),
            confidence=confidence,
            top_k=top_k,
            source="model",
            model_version=bundle.version,
            feature_coverage=coverage,
            ood_score=ood_fraction,
            ood_flag=ood_flag,
            needs_review=needs_review,
            reasons=reasons,
            top_features=top_features,
        )

    def _compute_top_features(self, vec: np.ndarray, top_n: int = 10) -> list[dict]:
        sorted_idx = np.argsort(np.abs(vec))[::-1][:top_n]
        denom = float(np.sum(np.abs(vec)) + 1e-9)
        return [
            {
                "feature": CICIDS2017_FEATURES[i],
                "value": float(vec[i]),
                "importance": float(np.abs(vec[i]) / denom),
            }
            for i in sorted_idx
            if i < len(CICIDS2017_FEATURES)
        ]


classifier = AttackClassifier()
LBROClassifier = AttackClassifier


def get_classifier() -> AttackClassifier:
    return classifier
