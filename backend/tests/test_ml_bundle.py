"""Additional coverage for bundle verification edge cases."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ml.bundle_io import BundleLoadError, verify_bundle_directory
from app.ml.preprocessing import sanitize_feature_dict, compute_ood_fraction


def test_sanitize_rejects_bad_types():
    cleaned, reasons = sanitize_feature_dict({"destination_port": "not-a-number", "flow_duration": float("nan")})
    assert "invalid_type:destination_port" in reasons
    assert "non_finite:flow_duration" in reasons


def test_ood_fraction_empty():
    frac, flag = compute_ood_fraction({}, {"destination_port": 0}, {"destination_port": 100})
    assert frac == 0.0 and flag is False


def test_verify_missing_manifest(tmp_path: Path):
    with pytest.raises(BundleLoadError) as exc:
        verify_bundle_directory(tmp_path)
    assert exc.value.reason_code == "manifest_missing"


def test_verify_hash_mismatch(tmp_path: Path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ML_ALLOW_UNSIGNED_MODEL", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    (tmp_path / "manifest.json").write_text(json.dumps({"file_hashes": {"x": "00" * 32}}), encoding="utf-8")
    with pytest.raises(BundleLoadError) as exc:
        verify_bundle_directory(tmp_path)
    assert exc.value.reason_code == "file_missing"
