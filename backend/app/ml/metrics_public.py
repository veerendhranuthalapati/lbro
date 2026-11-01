"""Metrics shown in UI/API when bundle status is demo-synthetic (not real evaluation)."""
DEMO_SYNTHETIC_METRIC_NA = "n/a - demo-synthetic"


def sanitize_metrics_summary_for_public(manifest: dict | None) -> dict:
    """Strip misleading numeric headline metrics for demo bundles."""
    if not manifest:
        return {}
    summary = dict(manifest.get("metrics_summary") or {})
    if manifest.get("status") != "demo-synthetic":
        return summary
    return {
        "headline_evaluation": DEMO_SYNTHETIC_METRIC_NA,
        "algorithm": summary.get("algorithm"),
        "calibration_method": summary.get("calibration_method"),
        "realistic": DEMO_SYNTHETIC_METRIC_NA,
        "optimistic": DEMO_SYNTHETIC_METRIC_NA,
        "validation_macro_f1": DEMO_SYNTHETIC_METRIC_NA,
        "note": "See ML_MODEL_EVALUATION.md appendix for synthetic lab metrics only.",
    }
