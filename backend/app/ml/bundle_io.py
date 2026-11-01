"""Signed model bundle verification and safe deserialization."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn import __version__ as sklearn_version

from app.config import settings

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
SIGNATURE_NAME = "manifest.sig"
MODEL_NAME = "model.joblib"
PREPROCESSING_NAME = "preprocessing.json"
CLASSES_NAME = "classes.json"


class BundleLoadError(Exception):
    """Raised when bundle authenticity or integrity checks fail."""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


@dataclass
class LoadedBundle:
    """In-memory representation of a verified production bundle."""

    version: str
    status: str
    model: Any
    classes: list[str]
    medians: dict[str, float]
    low_bounds: dict[str, float]
    high_bounds: dict[str, float]
    feature_order: list[str]
    metrics_summary: dict[str, Any]
    manifest: dict[str, Any]
    signature_verified: bool


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_manifest_hmac(manifest_bytes: bytes, signing_key: str) -> str:
    return hmac.new(signing_key.encode("utf-8"), manifest_bytes, hashlib.sha256).hexdigest()


def verify_manifest_signature(manifest_path: Path, sig_path: Path, signing_key: str) -> bool:
    manifest_bytes = manifest_path.read_bytes()
    expected = compute_manifest_hmac(manifest_bytes, signing_key)
    actual = sig_path.read_text(encoding="utf-8").strip()
    return hmac.compare_digest(expected.encode("utf-8"), actual.encode("utf-8"))


def _check_library_compatibility(manifest: dict[str, Any]) -> None:
    """Ensure runtime sklearn major.minor matches the bundle manifest."""
    libs = manifest.get("library_versions") or {}
    recorded_sklearn = libs.get("scikit-learn")
    if recorded_sklearn:
        major_minor = ".".join(recorded_sklearn.split(".")[:2])
        runtime_major_minor = ".".join(sklearn_version.split(".")[:2])
        if major_minor != runtime_major_minor:
            raise BundleLoadError(
                "sklearn_version_mismatch",
                f"Bundle trained with scikit-learn {recorded_sklearn}, runtime {sklearn_version}",
            )


def verify_bundle_directory(bundle_dir: Path) -> dict[str, Any]:
    """Verify file hashes and optional HMAC signature without deserializing the model."""
    if not bundle_dir.is_dir():
        raise BundleLoadError("bundle_missing", f"Bundle directory not found: {bundle_dir}")

    manifest_path = bundle_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise BundleLoadError("manifest_missing", "manifest.json missing from bundle")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    file_hashes = manifest.get("file_hashes") or {}

    for rel_name, expected_hash in file_hashes.items():
        file_path = bundle_dir / rel_name
        if not file_path.is_file():
            raise BundleLoadError("file_missing", f"Bundle file missing: {rel_name}")
        actual = _sha256_file(file_path)
        if not hmac.compare_digest(actual, expected_hash):
            raise BundleLoadError("hash_mismatch", f"SHA-256 mismatch for {rel_name}")

    sig_path = bundle_dir / SIGNATURE_NAME
    env = settings.ENVIRONMENT.lower()
    allow_unsigned = settings.ML_ALLOW_UNSIGNED_MODEL and env in ("dev", "development", "test")

    if sig_path.is_file():
        key = settings.ML_MODEL_SIGNING_KEY
        if not key:
            raise BundleLoadError("signing_key_missing", "ML_MODEL_SIGNING_KEY required to verify signature")
        if not verify_manifest_signature(manifest_path, sig_path, key):
            raise BundleLoadError("signature_invalid", "manifest.sig HMAC verification failed")
        manifest["_signature_verified"] = True
    elif env == "production" and not allow_unsigned:
        raise BundleLoadError("signature_missing", "manifest.sig required in production")
    elif not allow_unsigned:
        raise BundleLoadError(
            "signature_missing",
            "Unsigned bundle rejected (set ML_ALLOW_UNSIGNED_MODEL in dev/test only)",
        )
    else:
        logger.warning("Loading UNSIGNED ML bundle from %s — never do this in production", bundle_dir)
        manifest["_signature_verified"] = False

    _check_library_compatibility(manifest)
    return manifest


def load_verified_bundle(bundle_dir: Path | None = None) -> LoadedBundle:
    """
    Fail-closed loader: verify manifest, then joblib-load the model.

    Pickle/joblib deserialization is acceptable here ONLY because hashes and HMAC
    were verified immediately before load.
    """
    directory = Path(bundle_dir or settings.ML_MODEL_BUNDLE_DIR)
    manifest = verify_bundle_directory(directory)

    preprocessing = json.loads((directory / PREPROCESSING_NAME).read_text(encoding="utf-8"))
    classes_data = json.loads((directory / CLASSES_NAME).read_text(encoding="utf-8"))
    classes: list[str] = list(classes_data["classes"])

    model_path = directory / MODEL_NAME
    model = joblib.load(model_path)

    return LoadedBundle(
        version=str(manifest.get("version", "unknown")),
        status=str(manifest.get("status", "unknown")),
        model=model,
        classes=classes,
        medians={k: float(v) for k, v in (preprocessing.get("medians") or {}).items()},
        low_bounds={k: float(v) for k, v in (preprocessing.get("ood_low") or {}).items()},
        high_bounds={k: float(v) for k, v in (preprocessing.get("ood_high") or {}).items()},
        feature_order=list(preprocessing.get("feature_order") or []),
        metrics_summary=dict(manifest.get("metrics_summary") or {}),
        manifest=manifest,
        signature_verified=bool(manifest.get("_signature_verified")),
    )


def write_bundle_manifest(
    bundle_dir: Path,
    *,
    version: str,
    status: str,
    git_commit: str,
    dataset_hashes: dict[str, str],
    metrics_summary: dict[str, Any],
    signing_key: str | None = None,
) -> None:
    """Write manifest.json, file hashes, and optional manifest.sig after all artifacts exist."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    artifact_names = [MODEL_NAME, PREPROCESSING_NAME, CLASSES_NAME]
    file_hashes = {name: _sha256_file(bundle_dir / name) for name in artifact_names}

    manifest: dict[str, Any] = {
        "version": version,
        "created_at": datetime.now(UTC).isoformat(),
        "git_commit": git_commit,
        "status": status,
        "training_data_hashes": dataset_hashes,
        "library_versions": {
            "python": platform.python_version(),
            "scikit-learn": sklearn_version,
            "numpy": np.__version__,
        },
        "metrics_summary": metrics_summary,
        "file_hashes": file_hashes,
    }
    manifest_path = bundle_dir / MANIFEST_NAME
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    manifest_path.write_bytes(manifest_bytes)

    if signing_key:
        sig = compute_manifest_hmac(manifest_bytes, signing_key)
        (bundle_dir / SIGNATURE_NAME).write_text(sig, encoding="utf-8")
