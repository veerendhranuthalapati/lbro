"""Read active model metadata from signed bundle manifest."""
from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.ml.bundle_io import MANIFEST_NAME, BundleLoadError, verify_bundle_directory
from app.ml.metrics_public import sanitize_metrics_summary_for_public

BUNDLE_DIR = Path(settings.ML_MODEL_BUNDLE_DIR)


def _load_manifest_safe() -> dict | None:
    manifest_path = BUNDLE_DIR / MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    try:
        return verify_bundle_directory(BUNDLE_DIR)
    except BundleLoadError:
        return json.loads(manifest_path.read_text(encoding="utf-8"))


def _with_realistic_block(summary: dict) -> dict:
    """Expose the bundle's held-out CICIDS2017 evaluation as the 'realistic' block the API reads.

    The shipped CICIDS2017 manifest reports its evaluation under 'held_out_test' rather than
    'realistic'. Without this mapping the API sees no metrics and shows N/A.
    """
    if isinstance(summary.get("realistic"), dict):
        return summary
    held = summary.get("held_out_test")
    if not isinstance(held, dict):
        return summary
    out = dict(summary)
    out["realistic"] = {k: held[k] for k in ("accuracy", "macro_f1", "weighted_f1") if k in held}
    out.setdefault("headline_evaluation", "held_out_test (20% stratified split of CICIDS2017)")
    return out


def get_active_model_info() -> dict:
    manifest = _load_manifest_safe()
    if not manifest:
        return {
            "version": settings.ML_MODEL_VERSION,
            "metrics": {},
            "registered_at": None,
            "notes": "No bundle manifest found",
            "status": "unavailable",
        }
    summary = manifest.get("metrics_summary") or {}
    if manifest.get("status") == "demo-synthetic":
        summary = sanitize_metrics_summary_for_public(manifest)
    else:
        summary = _with_realistic_block(summary)
    return {
        "version": manifest.get("version"),
        "registered_at": manifest.get("created_at"),
        "status": manifest.get("status"),
        "metrics": summary.get("realistic")
        if isinstance(summary.get("realistic"), dict)
        else {},
        "metrics_summary": summary,
        "notes": f"Bundle status={manifest.get('status')}; headline={summary.get('headline_evaluation')}",
    }


def list_models() -> list[dict]:
    info = get_active_model_info()
    if info.get("version"):
        return [info]
    return []


def model_artifact_exists() -> bool:
    return (BUNDLE_DIR / MANIFEST_NAME).is_file() and (BUNDLE_DIR / "model.joblib").is_file()


def has_verified_evaluation() -> bool:
    if not model_artifact_exists():
        return False
    info = get_active_model_info()
    if info.get("status") == "demo-synthetic":
        return False
    metrics = info.get("metrics") or {}
    return metrics.get("macro_f1") is not None


def get_evaluation_metrics() -> dict | None:
    if not has_verified_evaluation():
        return None
    info = get_active_model_info()
    metrics = info.get("metrics") or {}
    summary = info.get("metrics_summary") or {}
    return {
        "version": info.get("version"),
        "trained_at": info.get("registered_at"),
        "status": info.get("status"),
        "accuracy": metrics.get("accuracy"),
        "macro_f1": metrics.get("macro_f1"),
        "weighted_f1": metrics.get("weighted_f1"),
        "log_loss": metrics.get("log_loss"),
        "ece": metrics.get("ece"),
        "optimistic": summary.get("optimistic"),
    }


def register_model(*_args, **_kwargs) -> dict:
    """Deprecated — training pipeline writes manifest.json directly."""
    raise NotImplementedError("Use scripts/train_models_cli.py to register models via manifest")
