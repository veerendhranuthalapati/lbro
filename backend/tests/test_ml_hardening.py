"""ML hardening tests — bundle security, inference contract, worker policy."""
from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import numpy as np
import pytest
from httpx import AsyncClient

from app.config import settings
from app.ml.bundle_io import BundleLoadError, load_verified_bundle, verify_bundle_directory
from app.ml.classifier import AttackClassifier
from app.ml.event_mapper import extract_network_features
from app.ml.features import CICIDS2017_FEATURES
from app.ml.model_registry import has_verified_evaluation, model_artifact_exists
from app.ml.preprocessing import feature_count

BUNDLE_DIR = Path(settings.ML_MODEL_BUNDLE_DIR)


def test_feature_count_is_77():
    assert feature_count() == 77
    assert len(CICIDS2017_FEATURES) == 77


def test_event_mapper_aliases():
    payload = {"dst_port": 443, "flow_features": {"syn_count": 10, "flow_packets_per_sec": 50}}
    feats = extract_network_features(payload)
    assert feats["destination_port"] == 443
    assert feats["syn_flag_count"] == 10


def test_all_ones_vector_not_overconfident():
    clf = AttackClassifier()
    dense = {f: 1.0 for f in CICIDS2017_FEATURES}
    dense["destination_port"] = 443
    result = clf.predict_result(dense)
    assert result.confidence <= settings.ML_HEURISTIC_MAX_CONFIDENCE + 1e-9
    assert result.needs_review is True
    assert result.ood_flag is True


def test_sparse_payload_insufficient_features():
    clf = AttackClassifier()
    result = clf.predict_result({"destination_port": 443})
    assert result.source in ("heuristic", "insufficient_features")
    assert result.needs_review is True


def test_bundle_loads_in_tests():
    assert model_artifact_exists()
    bundle = load_verified_bundle(BUNDLE_DIR)
    assert bundle.version
    assert bundle.status == "demo-synthetic"


def test_tampered_model_rejected(tmp_path):
    bundle = load_verified_bundle(BUNDLE_DIR)
    joblib.dump(bundle.model, tmp_path / "model.joblib")
    (tmp_path / "preprocessing.json").write_text((BUNDLE_DIR / "preprocessing.json").read_text())
    (tmp_path / "classes.json").write_text((BUNDLE_DIR / "classes.json").read_text())
    (tmp_path / "manifest.json").write_text((BUNDLE_DIR / "manifest.json").read_text())
    (tmp_path / "manifest.sig").write_text((BUNDLE_DIR / "manifest.sig").read_text())
    with open(tmp_path / "model.joblib", "ab") as f:
        f.write(b"tamper")
    with pytest.raises(BundleLoadError) as exc:
        verify_bundle_directory(tmp_path)
    assert exc.value.reason_code == "hash_mismatch"


def test_registry_has_verified_metrics():
    assert has_verified_evaluation() is False


@pytest.mark.asyncio
async def test_ml_status_endpoint(client: AsyncClient, auth_headers: dict):
    from app.ml.classifier import classifier

    classifier._loaded = False
    classifier._bundle = None
    classifier._load_error_code = None
    classifier._load_error_reason = None
    classifier._load()

    resp = await client.get("/api/v1/ml/status", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "demo-synthetic"
    assert body["signature_verified"] is True
    assert "thresholds" in body


@pytest.mark.asyncio
async def test_auto_contain_default_off():
    from app.config import settings as s

    assert s.ML_AUTO_CONTAIN_ENABLED is False


def test_classifier_fail_closed_on_bundle_error(monkeypatch):
    from app.ml import classifier as clf_mod
    from app.ml.bundle_io import BundleLoadError

    def _fail(*_args, **_kwargs):
        raise BundleLoadError("signature_invalid", "test failure")

    monkeypatch.setattr(clf_mod, "load_verified_bundle", _fail)
    c = clf_mod.AttackClassifier()
    c._loaded = False
    feats = {name: 100.0 for name in CICIDS2017_FEATURES[:40]}
    result = c.predict_result(feats)
    assert result.source in ("heuristic", "insufficient_features")
    assert result.needs_review is True
