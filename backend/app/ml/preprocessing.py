"""Feature validation and vector construction for CICIDS2017 inference."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.ml.features import CICIDS2017_FEATURES

# Features that must not be negative in real flow statistics (ports, counts, durations).
NON_NEGATIVE_FEATURES = frozenset(
    {
        "destination_port",
        "flow_duration",
        "total_fwd_packets",
        "total_bwd_packets",
        "total_length_fwd_packets",
        "total_length_bwd_packets",
        *CICIDS2017_FEATURES[6:],  # remaining numeric flow stats are non-negative
    }
)


def feature_count() -> int:
    """Single source for 78-feature count used in docs and coverage checks."""
    return len(CICIDS2017_FEATURES)


def count_supplied_features(raw: dict[str, Any]) -> tuple[int, float]:
    """
    Count how many canonical features were explicitly provided with usable numeric values.

    Zeros supplied by the client still count as supplied — only missing keys / null /
    non-numeric values reduce coverage.
    """
    supplied = 0
    for name in CICIDS2017_FEATURES:
        if name not in raw:
            continue
        val = raw[name]
        if val is None:
            continue
        try:
            float(val)
        except (TypeError, ValueError):
            continue
        supplied += 1
    coverage = supplied / feature_count() if feature_count() else 0.0
    return supplied, coverage


def sanitize_feature_dict(raw: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    """
    Coerce incoming values to floats; drop invalid entries and record reason codes.

    NaN/inf are replaced with 0.0 so they cannot crash sklearn, but callers should
    treat accompanying reason codes as signals to flag ``needs_review``.
    """
    cleaned: dict[str, float] = {}
    reasons: list[str] = []
    for name in CICIDS2017_FEATURES:
        if name not in raw:
            continue
        val = raw[name]
        if val is None:
            continue
        try:
            f = float(val)
        except (TypeError, ValueError):
            reasons.append(f"invalid_type:{name}")
            continue
        if math.isnan(f) or math.isinf(f):
            reasons.append(f"non_finite:{name}")
            f = 0.0
        if name in NON_NEGATIVE_FEATURES and f < 0:
            reasons.append(f"negative_clamped:{name}")
            f = 0.0
        cleaned[name] = f
    return cleaned, reasons


def build_imputation_vector(
    cleaned: dict[str, float],
    medians: dict[str, float],
) -> np.ndarray:
    """Build a dense vector using training medians for missing columns."""
    row = []
    for name in CICIDS2017_FEATURES:
        if name in cleaned:
            row.append(cleaned[name])
        else:
            row.append(float(medians.get(name, 0.0)))
    return np.array(row, dtype=np.float64).reshape(1, -1)


def compute_ood_fraction(
    cleaned: dict[str, float],
    low_bounds: dict[str, float],
    high_bounds: dict[str, float],
) -> tuple[float, bool]:
    """
    Fraction of *supplied* features outside training 0.1–99.9 percentile bounds.

    Missing features are ignored — OOD is about whether provided values look like training data.
    """
    if not cleaned:
        return 0.0, False
    outliers = 0
    for name, val in cleaned.items():
        lo = low_bounds.get(name, float("-inf"))
        hi = high_bounds.get(name, float("inf"))
        if val < lo or val > hi:
            outliers += 1
    fraction = outliers / len(cleaned)
    return fraction, fraction > 0.0
