"""Rule-based fallback when the signed model is unavailable or input is insufficient."""
from __future__ import annotations

from typing import Any

from app.config import settings
from app.ml.contract import ClassificationResult, TopClassProbability
from app.ml.features import SEVERITY_MAP


def heuristic_classify(
    features: dict[str, Any],
    *,
    feature_coverage: float,
    reasons: list[str] | None = None,
) -> ClassificationResult:
    """
    Port-based rules used when we must not trust the sklearn artifact.

    Heuristic output is always ``needs_review=True`` and never eligible for automation.
    """
    dst_port = int(features.get("destination_port") or 0)
    syn_flags = float(features.get("syn_flag_count") or 0)
    pkt_rate = float(features.get("flow_packets_per_sec") or 0)

    if pkt_rate > 10000:
        category = "DDoS"
    elif syn_flags > 1000:
        category = "DoS Hulk"
    elif dst_port == 21:
        category = "FTP-Patator"
    elif dst_port == 22:
        category = "SSH-Patator"
    elif dst_port in (80, 443, 8080):
        category = "Web Attack - Brute Force"
    else:
        category = "BENIGN"

    cap = settings.ML_HEURISTIC_MAX_CONFIDENCE
    confidence = min(cap, 0.65)
    merged_reasons = list(reasons or [])
    merged_reasons.append("heuristic_fallback")

    top_features = [
        {"feature": "destination_port", "value": dst_port, "importance": 0.3},
        {"feature": "syn_flag_count", "value": syn_flags, "importance": 0.25},
        {"feature": "flow_packets_per_sec", "value": pkt_rate, "importance": 0.2},
    ]

    return ClassificationResult(
        attack_category=category,
        is_attack=category != "BENIGN",
        severity=SEVERITY_MAP.get(category, "medium"),
        confidence=confidence,
        top_k=[
            TopClassProbability(category, confidence),
            TopClassProbability("BENIGN", max(0.0, 1.0 - confidence)),
        ],
        source="heuristic",
        model_version="heuristic-fallback",
        feature_coverage=feature_coverage,
        ood_score=0.0,
        ood_flag=False,
        needs_review=True,
        reasons=merged_reasons,
        top_features=top_features,
    )
