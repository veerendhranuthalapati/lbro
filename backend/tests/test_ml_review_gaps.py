"""Review-gap tests: security, policy, worker queue, startup, inputs."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from httpx import AsyncClient

from pathlib import Path

from app.config import settings
from app.ml.bundle_io import BundleLoadError, load_verified_bundle, verify_bundle_directory
from app.ml.classifier import AttackClassifier
from app.ml.contract import ClassificationResult
from app.ml.features import ATTACK_CLASSES, CICIDS2017_FEATURES
from app.ml.signing_policy import KNOWN_TEST_SIGNING_KEYS, validate_signing_key_for_environment
from app.ml.startup_check import run_ml_startup_check
from app.workers.incident_worker import classify_incident, process_incident_message

BUNDLE_DIR = Path(settings.ML_MODEL_BUNDLE_DIR)


class _WorkerDbCtx:
    """Bind worker AsyncSessionLocal to the pytest `db` session (same in-memory DB)."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        if exc:
            await self._session.rollback()
        else:
            await self._session.commit()


def _worker_session_maker(session):
    class _Maker:
        def __call__(self):
            return _WorkerDbCtx(session)

    return _Maker()


# ── Signing policy ───────────────────────────────────────────────────────────


def test_reject_test_signing_key_in_production():
    key = next(iter(KNOWN_TEST_SIGNING_KEYS))
    with pytest.raises(ValueError, match="test/dev key"):
        validate_signing_key_for_environment(key, "production")


def test_reject_short_signing_key_in_production():
    with pytest.raises(ValueError, match="at least"):
        validate_signing_key_for_environment("short", "production")


def test_startup_fails_closed_missing_key_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ML_MODEL_SIGNING_KEY", None)
    monkeypatch.setattr(settings, "ML_ALLOW_UNSIGNED_MODEL", False)
    with pytest.raises(ValueError):
        run_ml_startup_check(fail_fast_in_production=True)


def test_startup_ok_in_test_environment():
    report = run_ml_startup_check(fail_fast_in_production=False)
    assert report["startup_ok"] is True
    assert report["environment"] == "test"


def test_startup_missing_manifest(tmp_path, monkeypatch):
    from app.ml.classifier import classifier

    monkeypatch.setattr("app.ml.startup_check.BUNDLE_DIR", tmp_path)
    try:
        report = run_ml_startup_check(fail_fast_in_production=False)
        assert report["error_code"] == "bundle_missing"
        assert report["heuristic_fallback"] is True
    finally:
        classifier._loaded = False
        classifier._bundle = None
        classifier._load_error_code = None
        classifier._load_error_reason = None
        classifier._load()


def test_signing_policy_short_key_in_dev():
    with pytest.raises(ValueError, match="at least"):
        validate_signing_key_for_environment("short", "development")


def test_metrics_public_non_demo_summary():
    from app.ml.metrics_public import sanitize_metrics_summary_for_public

    assert sanitize_metrics_summary_for_public(None) == {}
    manifest = {
        "status": "verified",
        "metrics_summary": {"realistic": {"macro_f1": 0.91}, "headline_evaluation": "verified"},
    }
    out = sanitize_metrics_summary_for_public(manifest)
    assert out["realistic"]["macro_f1"] == 0.91


def test_signing_policy_prod_allows_unsigned_when_flag(monkeypatch):
    monkeypatch.setenv("ML_ALLOW_UNSIGNED_MODEL", "true")
    validate_signing_key_for_environment(None, "production")


# ── Bundle security ────────────────────────────────────────────────────────


def test_tampered_manifest_json_rejected(tmp_path):
    bundle = tmp_path / "b"
    bundle.mkdir()
    for name in ("model.joblib", "preprocessing.json", "classes.json"):
        (bundle / name).write_bytes(b"x")
    manifest = {
        "file_hashes": {"model.joblib": "00" * 32},
        "library_versions": {"scikit-learn": "1.7.2"},
        "status": "demo-synthetic",
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BundleLoadError) as exc:
        verify_bundle_directory(bundle)
    assert exc.value.reason_code in ("hash_mismatch", "file_missing")


def test_wrong_signing_key_rejected(tmp_path, monkeypatch):
    """Copy real bundle files but sign with a different key."""
    from app.ml.bundle_io import compute_manifest_hmac, MANIFEST_NAME, SIGNATURE_NAME

    src = BUNDLE_DIR
    dst = tmp_path / "bundle"
    dst.mkdir()
    for f in ("model.joblib", "preprocessing.json", "classes.json", "manifest.json"):
        (dst / f).write_bytes((src / f).read_bytes())
    manifest_bytes = (dst / MANIFEST_NAME).read_bytes()
    (dst / SIGNATURE_NAME).write_text(compute_manifest_hmac(manifest_bytes, "wrong-key-minimum-32-characters-long"))
    monkeypatch.setattr(settings, "ML_ALLOW_UNSIGNED_MODEL", False)
    monkeypatch.setattr(settings, "ML_MODEL_SIGNING_KEY", "test-ml-signing-key-minimum-32-characters-long")
    with pytest.raises(BundleLoadError) as exc:
        verify_bundle_directory(dst)
    assert exc.value.reason_code == "signature_invalid"


def test_sklearn_version_mismatch_rejected(monkeypatch):
    from app.ml import bundle_io

    real = bundle_io._check_library_compatibility

    def boom(manifest):
        manifest = dict(manifest)
        manifest["library_versions"] = {"scikit-learn": "0.0.1"}
        real(manifest)

    monkeypatch.setattr(bundle_io, "_check_library_compatibility", boom)
    with pytest.raises(BundleLoadError):
        load_verified_bundle(BUNDLE_DIR)


# ── Input contract ───────────────────────────────────────────────────────────


@pytest.fixture
def clf() -> AttackClassifier:
    c = AttackClassifier()
    c._loaded = False
    return c


def test_input_nan_inf_strings(clf: AttackClassifier):
    r = clf.predict_result({"destination_port": float("nan"), "flow_duration": "bad", "syn_flag_count": -5})
    assert r.needs_review is True


def test_input_all_zeros(clf: AttackClassifier):
    r = clf.predict_result({name: 0.0 for name in CICIDS2017_FEATURES[:40]})
    assert r.source in ("heuristic", "insufficient_features")


def test_input_all_ones_not_confident(clf: AttackClassifier):
    dense = {f: 1.0 for f in CICIDS2017_FEATURES}
    dense["destination_port"] = 443
    r = clf.predict_result(dense)
    assert r.confidence <= settings.ML_HEURISTIC_MAX_CONFIDENCE + 1e-9
    assert r.needs_review is True


def test_input_sparse_payload(clf: AttackClassifier):
    r = clf.predict_result({"destination_port": 443})
    assert r.source in ("heuristic", "insufficient_features")


def test_classifier_reload_after_load(clf: AttackClassifier):
    clf.predict_result({"destination_port": 443})
    clf.reload()
    assert clf.bundle is not None


def test_event_mapper_nested_flow_features():
    from app.ml.event_mapper import extract_network_features

    feats = extract_network_features({"flow_features": {"ack_count": 3.0, "flow_duration": 1.0}})
    assert feats["ack_flag_count"] == 3.0
    assert feats["flow_duration"] == 1.0


def test_event_mapper_skips_invalid_values():
    from app.ml.event_mapper import extract_network_features

    assert extract_network_features({"destination_port": "not-a-number"}) == {}


# ── Auto-containment policy (one failing condition each) ───────────────────


def _model_result(**overrides) -> ClassificationResult:
    base = ClassificationResult(
        attack_category="DoS Hulk",
        is_attack=True,
        severity="critical",
        confidence=0.99,
        top_k=[],
        source="model",
        model_version="v1",
        feature_coverage=1.0,
        ood_score=0.0,
        ood_flag=False,
        needs_review=False,
        reasons=[],
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.mark.asyncio
async def test_auto_contain_blocked_when_global_flag_off():
    from app.workers import incident_worker as iw

    incident = MagicMock()
    incident.id = uuid.uuid4()
    incident.project_id = uuid.uuid4()
    incident.status = "triaging"
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(allow_ml_auto_contain=True))
    with patch.object(settings, "ML_AUTO_CONTAIN_ENABLED", False):
        await iw._handle_containment_policy(db, incident, _model_result())
    assert incident.status == "triaging"


@pytest.mark.asyncio
async def test_auto_contain_blocked_when_source_heuristic():
    from app.workers import incident_worker as iw

    incident = MagicMock(status="triaging", id=uuid.uuid4(), project_id=uuid.uuid4())
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(allow_ml_auto_contain=True))
    with patch.object(settings, "ML_AUTO_CONTAIN_ENABLED", True):
        await iw._handle_containment_policy(db, incident, _model_result(source="heuristic", needs_review=True))
    assert incident.status == "triaging"


@pytest.mark.asyncio
async def test_auto_contain_blocked_when_ood_flag():
    from app.workers import incident_worker as iw

    incident = MagicMock(status="triaging", id=uuid.uuid4(), project_id=uuid.uuid4())
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(allow_ml_auto_contain=True))
    with patch.object(settings, "ML_AUTO_CONTAIN_ENABLED", True):
        await iw._handle_containment_policy(db, incident, _model_result(ood_flag=True))
    assert incident.status == "triaging"


@pytest.mark.asyncio
async def test_auto_contain_blocked_when_low_confidence():
    from app.workers import incident_worker as iw

    incident = MagicMock(status="triaging", id=uuid.uuid4(), project_id=uuid.uuid4())
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(allow_ml_auto_contain=True))
    with patch.object(settings, "ML_AUTO_CONTAIN_ENABLED", True):
        await iw._handle_containment_policy(
            db, incident, _model_result(confidence=0.5, needs_review=True)
        )
    assert incident.status == "triaging"


@pytest.mark.asyncio
async def test_auto_contain_blocked_when_benign():
    from app.workers import incident_worker as iw

    incident = MagicMock(status="triaging", id=uuid.uuid4(), project_id=uuid.uuid4())
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(allow_ml_auto_contain=True))
    with patch.object(settings, "ML_AUTO_CONTAIN_ENABLED", True):
        await iw._handle_containment_policy(
            db, incident, _model_result(attack_category="BENIGN", severity="info")
        )
    assert incident.status == "triaging"


@pytest.mark.asyncio
async def test_auto_contain_blocked_when_project_not_opted_in():
    from app.workers import incident_worker as iw

    incident = MagicMock(status="triaging", id=uuid.uuid4(), project_id=uuid.uuid4())
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(allow_ml_auto_contain=False))
    with patch.object(settings, "ML_AUTO_CONTAIN_ENABLED", True):
        await iw._handle_containment_policy(db, incident, _model_result())
    assert incident.status == "triaging"


@pytest.mark.asyncio
async def test_auto_contain_blocked_when_not_critical_severity():
    from app.workers import incident_worker as iw

    incident = MagicMock(status="triaging", id=uuid.uuid4(), project_id=uuid.uuid4())
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(allow_ml_auto_contain=True))
    with patch.object(settings, "ML_AUTO_CONTAIN_ENABLED", True):
        await iw._handle_containment_policy(db, incident, _model_result(severity="high"))
    assert incident.status == "triaging"


# ── Worker / queue ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_malformed_message_does_not_raise():
    await process_incident_message("not-a-dict")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_duplicate_delivery_idempotent(db, monkeypatch):
    from app.models.incident import Incident, IncidentAction

    monkeypatch.setattr(
        "app.workers.incident_worker.AsyncSessionLocal",
        _worker_session_maker(db),
    )
    inc = Incident(
        title="Dup test incident title here",
        severity="high",
        status="new",
        ml_classification_status="completed",
        network_features={"destination_port": 443},
    )
    db.add(inc)
    await db.flush()
    db.add(
        IncidentAction(
            incident_id=inc.id,
            action_type="ml_classification",
            description="first",
            automated=True,
        )
    )
    await db.flush()
    iid = inc.id

    with patch("app.workers.incident_worker.classifier") as mock_clf:
        mock_clf.predict_result.return_value = _model_result()
        await classify_incident(iid)
        assert mock_clf.predict_result.call_count == 0


@pytest.mark.asyncio
async def test_classify_missing_incident_returns(db, monkeypatch):
    monkeypatch.setattr(
        "app.workers.incident_worker.AsyncSessionLocal",
        _worker_session_maker(db),
    )
    await classify_incident(uuid.uuid4())


@pytest.mark.asyncio
async def test_model_unavailable_heuristic_fallback(clf: AttackClassifier):
    clf._loaded = True
    clf._bundle = None
    clf._load_error_code = "signature_invalid"
    r = clf.predict_result({name: 1.0 for name in CICIDS2017_FEATURES[:50]})
    assert r.source == "heuristic"


@pytest.mark.asyncio
async def test_sqs_enqueue_failure_sets_pending(client: AsyncClient, auth_headers: dict):
    from app.schemas.incident import IncidentCreate

    with patch("app.services.incident_service.sqs_service.enqueue_incident", side_effect=RuntimeError("sqs down")):
        resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "SQS failure test incident title",
                "severity": "medium",
                "network_features": {"destination_port": 443, "flow_duration": 1.0},
            },
            headers=auth_headers,
        )
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body.get("ml_classification_status") == "pending"


@pytest.mark.asyncio
async def test_project_ml_policy_toggle(client: AsyncClient, auth_headers: dict):
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "ML Policy Proj", "environment": "development"},
        headers=auth_headers,
    )
    pid = proj.json()["id"]
    resp = await client.patch(
        f"/api/v1/projects/{pid}/ml-policy",
        json={"allow_ml_auto_contain": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["allow_ml_auto_contain"] is True


# ── Pending ML classification retry sweep ───────────────────────────────────


@pytest.mark.asyncio
async def test_ml_pending_retry_sweep_enqueues(db, monkeypatch):
    from app.models.incident import Incident
    from app.workers.ml_retry_sweep import sweep_pending_ml_classifications

    monkeypatch.setattr(
        "app.workers.ml_retry_sweep.AsyncSessionLocal",
        _worker_session_maker(db),
    )
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    inc = Incident(
        title="Retry sweep test incident title",
        severity="medium",
        status="new",
        ml_classification_status="pending",
        ml_classification_attempts=1,
        ml_classification_next_retry_at=past,
        network_features={"destination_port": 443},
    )
    db.add(inc)
    await db.flush()

    with patch("app.workers.ml_retry_sweep.sqs_service.enqueue_incident") as mock_enqueue:
        count = await sweep_pending_ml_classifications()
    assert count == 1
    assert mock_enqueue.call_count == 1
    assert inc.ml_classification_attempts == 2


@pytest.mark.asyncio
async def test_ml_pending_retry_sweep_respects_max_attempts(db, monkeypatch):
    from app.models.incident import Incident
    from app.workers.ml_retry_sweep import sweep_pending_ml_classifications

    monkeypatch.setattr(
        "app.workers.ml_retry_sweep.AsyncSessionLocal",
        _worker_session_maker(db),
    )
    inc = Incident(
        title="Retry max attempts test title",
        severity="medium",
        status="new",
        ml_classification_status="pending",
        ml_classification_attempts=settings.ML_PENDING_MAX_ATTEMPTS,
        ml_classification_next_retry_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        network_features={"destination_port": 443},
    )
    db.add(inc)
    await db.flush()

    with patch("app.workers.ml_retry_sweep.sqs_service.enqueue_incident") as mock_enqueue:
        count = await sweep_pending_ml_classifications()
    assert count == 0
    assert mock_enqueue.call_count == 0


def test_verify_unsigned_rejected_in_test_without_flag(tmp_path, monkeypatch):
    from app.config import settings

    src = Path(settings.ML_MODEL_BUNDLE_DIR)
    for name in ("model.joblib", "preprocessing.json", "classes.json", "manifest.json"):
        (tmp_path / name).write_bytes((src / name).read_bytes())
    if (tmp_path / "manifest.sig").exists():
        (tmp_path / "manifest.sig").unlink()
    monkeypatch.setattr(settings, "ML_ALLOW_UNSIGNED_MODEL", False)
    with pytest.raises(BundleLoadError) as exc:
        verify_bundle_directory(tmp_path)
    assert exc.value.reason_code == "signature_missing"


def test_startup_production_raises_on_bad_bundle(tmp_path, monkeypatch):
    from app.ml.classifier import classifier

    src = BUNDLE_DIR
    for name in ("model.joblib", "preprocessing.json", "classes.json", "manifest.json", "manifest.sig"):
        if (src / name).is_file():
            (tmp_path / name).write_bytes((src / name).read_bytes())
    (tmp_path / "manifest.sig").write_text("deadbeef", encoding="utf-8")

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        settings,
        "ML_MODEL_SIGNING_KEY",
        "production-release-signing-key-at-least-32chars",
    )
    monkeypatch.setattr("app.ml.startup_check.BUNDLE_DIR", tmp_path)
    try:
        with pytest.raises(RuntimeError, match="ML bundle verification failed"):
            run_ml_startup_check(fail_fast_in_production=True)
    finally:
        monkeypatch.setattr(settings, "ENVIRONMENT", "test")
        classifier._loaded = False
        classifier._bundle = None
        classifier._load_error_code = None
        classifier._load_error_reason = None
        classifier._load()


def test_classifier_unexpected_load_error(monkeypatch):
    from app.ml import classifier as clf_mod

    def _boom(*_a, **_k):
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(clf_mod, "load_verified_bundle", _boom)
    c = clf_mod.AttackClassifier()
    c._loaded = False
    r = c.predict_result({"destination_port": 443})
    assert r.source in ("heuristic", "insufficient_features")
    assert c.load_error_code == "unexpected_load_error"


def test_verify_unsigned_allowed_in_test(tmp_path, monkeypatch):
    src = BUNDLE_DIR
    for name in ("model.joblib", "preprocessing.json", "classes.json", "manifest.json"):
        (tmp_path / name).write_bytes((src / name).read_bytes())
    if (tmp_path / "manifest.sig").exists():
        (tmp_path / "manifest.sig").unlink()
    monkeypatch.setattr(settings, "ML_ALLOW_UNSIGNED_MODEL", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    manifest = verify_bundle_directory(tmp_path)
    assert manifest.get("_signature_verified") is False


def test_verify_signature_requires_key(tmp_path, monkeypatch):
    src = BUNDLE_DIR
    for name in ("model.joblib", "preprocessing.json", "classes.json", "manifest.json", "manifest.sig"):
        if (src / name).is_file():
            (tmp_path / name).write_bytes((src / name).read_bytes())
    monkeypatch.setattr(settings, "ML_MODEL_SIGNING_KEY", None)
    monkeypatch.setattr(settings, "ML_ALLOW_UNSIGNED_MODEL", False)
    with pytest.raises(BundleLoadError) as exc:
        verify_bundle_directory(tmp_path)
    assert exc.value.reason_code == "signing_key_missing"


def test_tampered_signature_file_rejected(tmp_path, monkeypatch):
    src = BUNDLE_DIR
    for f in ("model.joblib", "preprocessing.json", "classes.json", "manifest.json", "manifest.sig"):
        if (src / f).is_file():
            (tmp_path / f).write_bytes((src / f).read_bytes())
    (tmp_path / "manifest.sig").write_text("deadbeef", encoding="utf-8")
    monkeypatch.setattr(settings, "ML_ALLOW_UNSIGNED_MODEL", False)
    with pytest.raises(BundleLoadError) as exc:
        verify_bundle_directory(tmp_path)
    assert exc.value.reason_code == "signature_invalid"
