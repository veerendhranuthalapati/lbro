"""Process startup checks for ML bundle signing and load readiness."""
from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.ml.bundle_io import MANIFEST_NAME, BundleLoadError, verify_bundle_directory
from app.ml.classifier import classifier
from app.ml.signing_policy import validate_signing_key_for_environment

logger = logging.getLogger(__name__)

BUNDLE_DIR = Path(settings.ML_MODEL_BUNDLE_DIR)


def run_ml_startup_check(*, fail_fast_in_production: bool = True) -> dict:
    """
    Validate signing key policy and attempt bundle verification.

    In production, a missing/invalid key or unsigned bundle prevents startup when
    fail_fast_in_production=True (API/worker entrypoints pass True).
    """
    env = settings.ENVIRONMENT.lower()
    report: dict = {
        "environment": env,
        "bundle_dir": str(BUNDLE_DIR),
        "signing_key_present": bool(settings.ML_MODEL_SIGNING_KEY),
        "heuristic_fallback": False,
        "startup_ok": True,
        "error_code": None,
        "error_message": None,
    }

    try:
        validate_signing_key_for_environment(settings.ML_MODEL_SIGNING_KEY, env)
    except ValueError as exc:
        report["startup_ok"] = False
        report["error_code"] = "signing_key_policy"
        report["error_message"] = str(exc)
        logger.error("ML startup failed signing policy: %s", exc)
        if fail_fast_in_production and env == "production":
            raise
        return report

    manifest_path = BUNDLE_DIR / MANIFEST_NAME
    if not manifest_path.is_file():
        report["heuristic_fallback"] = True
        report["error_code"] = "bundle_missing"
        report["error_message"] = f"No manifest at {manifest_path}"
        logger.warning("ML bundle missing — heuristic fallback only")
        return report

    try:
        verify_bundle_directory(BUNDLE_DIR)
        classifier._loaded = False
        classifier._load()
        report["heuristic_fallback"] = classifier.bundle is None
        if classifier.load_error_code:
            report["error_code"] = classifier.load_error_code
            report["error_message"] = classifier.load_error_reason
    except BundleLoadError as exc:
        report["heuristic_fallback"] = True
        report["error_code"] = exc.reason_code
        report["error_message"] = str(exc)
        logger.error("ML bundle verification failed [%s]: %s", exc.reason_code, exc)
        if fail_fast_in_production and env == "production":
            raise RuntimeError(f"ML bundle verification failed: {exc}") from exc

    return report
