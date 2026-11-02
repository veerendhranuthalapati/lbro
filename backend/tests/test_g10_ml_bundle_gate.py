"""G10: ML bundle tamper / production signing policy — evidence tests (bundle COPY only)."""
from __future__ import annotations

import json
import shutil

from pathlib import Path

import pytest

from app.config import settings
from app.ml.bundle_io import BundleLoadError, compute_manifest_hmac, verify_bundle_directory
from app.ml.signing_policy import validate_signing_key_for_environment

BUNDLE_DIR = Path(settings.ML_MODEL_BUNDLE_DIR)


def test_g10_flip_model_byte_rejects_copy(tmp_path):
    """Flip one byte in model.joblib copy — loader must refuse."""
    dst = tmp_path / "bundle"
    shutil.copytree(BUNDLE_DIR, dst)
    model_path = dst / "model.joblib"
    data = bytearray(model_path.read_bytes())
    data[10] ^= 0xFF
    model_path.write_bytes(bytes(data))
    key = settings.ML_MODEL_SIGNING_KEY or "test-ml-signing-key-minimum-32-characters-long"
    manifest_bytes = (dst / "manifest.json").read_bytes()
    (dst / "manifest.sig").write_text(compute_manifest_hmac(manifest_bytes, key), encoding="utf-8")
    with pytest.raises(BundleLoadError):
        verify_bundle_directory(dst)


def test_g10_production_rejects_test_signing_key():
    with pytest.raises(ValueError, match="test"):
        validate_signing_key_for_environment(
            "test-ml-signing-key-minimum-32-characters-long",
            "production",
        )


def test_g10_production_startup_refuses_missing_key(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ML_MODEL_SIGNING_KEY", None)
    with pytest.raises(ValueError):
        validate_signing_key_for_environment(None, "production")


def test_g10_wrong_key_rejects_signature(tmp_path, monkeypatch):
    dst = tmp_path / "bundle"
    shutil.copytree(BUNDLE_DIR, dst)
    manifest_bytes = (dst / "manifest.json").read_bytes()
    (dst / "manifest.sig").write_text(
        compute_manifest_hmac(manifest_bytes, "wrong-key-that-is-long-enough-32chars"),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "ML_MODEL_SIGNING_KEY", "test-ml-signing-key-minimum-32-characters-long")
    with pytest.raises(BundleLoadError):
        verify_bundle_directory(dst)


def test_g10_missing_signature_file_rejects(tmp_path, monkeypatch):
    dst = tmp_path / "bundle"
    shutil.copytree(BUNDLE_DIR, dst)
    (dst / "manifest.sig").unlink()
    monkeypatch.setattr(settings, "ML_MODEL_SIGNING_KEY", "test-ml-signing-key-minimum-32-characters-long")
    with pytest.raises(BundleLoadError):
        verify_bundle_directory(dst)


def test_g10_heuristic_fallback_when_bundle_unloaded():
    from app.ml.classifier import AttackClassifier
    from app.ml.features import CICIDS2017_FEATURES

    clf = AttackClassifier()
    clf._loaded = True
    clf._bundle = None
    clf._load_error_code = "signature_invalid"
    r = clf.predict_result({name: 1.0 for name in CICIDS2017_FEATURES[:50]})
    assert r.source == "heuristic"
    assert clf.status_snapshot()["heuristic_fallback_active"] is True
