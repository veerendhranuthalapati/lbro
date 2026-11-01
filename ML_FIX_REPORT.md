# ML Fix Report — `fix/ml-hardening`

## Summary

End-to-end ML hardening: signed bundle loading (fail-closed), honest inference contract, synthetic demo training pipeline, containment policy default-off with audit logs, event feature mapper, migration **015**, tests, and frontend source badges. **Real CICIDS2017 CSV data was not in the repo** — shipped bundle status is **`demo-synthetic`**.

## Problem status

| ID | Status | Evidence |
|----|--------|----------|
| P1 Synthetic metrics | **FIXED** (labelled) | `ML_MODEL_EVALUATION.md`, bundle `manifest.status=demo-synthetic`, training `pipeline.py` |
| P2 Pickle RCE | **FIXED** | HMAC + SHA-256 before `joblib.load` (`bundle_io.py:133-148`), tamper test `test_ml_hardening.py` |
| P3 Overconfidence | **FIXED** | All-ones → `confidence=0.5`, `needs_review=True`, `ood_flag=True` (command below) |
| P4 Auto-contain | **FIXED** | `ML_AUTO_CONTAIN_ENABLED=false` (`config.py`), recommendation workflow `incident_worker.py` |
| P5 Sparse ingest | **FIXED** | `event_mapper.py`, `events.py`, `source` on `SecurityEvent` |
| P6 SQS swallow | **FIXED** | `incident_service.py` logs + `ml_classification_status=pending` |
| P7 label_encoder / 77 vs 78 | **FIXED** | Removed `label_encoder.pkl`; **`FEATURE_COUNT=77`** in `features.py`; docs updated |
| P8 Coverage / tests | **PARTIAL** | `pyproject.toml` omit removed for classifier/registry; **663 passed** full suite; ML package line coverage **~52–85%** depending on scope — training covered by `test_ml_training.py` (slow); inference paths heavily tested |

## Verification commands & output

### Full backend tests

```powershell
cd c:\Users\veere\Desktop\lbro\backend
$env:DATABASE_URL="sqlite+aiosqlite:///:memory:"
$env:SECRET_KEY="test-secret-key-minimum-32-characters-ci"
$env:ENVIRONMENT="test"
$env:ML_MODEL_SIGNING_KEY="test-ml-signing-key-minimum-32-characters-long"
$env:ALLOW_PUBLIC_REGISTRATION="true"
.\.venv\Scripts\pytest.exe tests/ -q
```

**Result:** `663 passed, 1 warning in 859.05s`

### P3 all-ones (after fix)

```powershell
.\.venv\Scripts\python.exe -c "from app.ml.classifier import get_classifier; from app.ml.features import CICIDS2017_FEATURES; c=get_classifier(); d={f:1.0 for f in CICIDS2017_FEATURES}; d['destination_port']=443; r=c.predict_result(d); print(r.source, r.confidence, r.needs_review, r.ood_flag, r.reasons)"
```

**Result:** `model 0.5 True True ['mostly_uniform_feature_vector', ...]`

### Verify bundle

```powershell
python ..\scripts\verify_model.py --load-model
```

**Result:** `Manifest and file hashes OK` / `status=demo-synthetic verified=True`

### Alembic

```powershell
.\.venv\Scripts\alembic.exe heads
```

**Result:** `015_ml_provenance (head)`

### Frontend

```powershell
cd ..\frontend
npm run type-check   # pass
npm run test -- --run  # 50 passed
```

## Headline metrics (synthetic fast train)

| Metric | Realistic block | Optimistic stratified |
|--------|-----------------|------------------------|
| Macro F1 | 0.9103 | 0.9940 |
| Accuracy | 0.98 | 0.9979 |
| Log loss | 0.1224 | 0.0121 |
| ECE | 0.0082 | 0.0080 |

## New env vars

`ML_MODEL_BUNDLE_DIR`, `ML_MODEL_SIGNING_KEY`, `ML_ALLOW_UNSIGNED_MODEL`, `ML_REVIEW_THRESHOLD`, `ML_MIN_FEATURE_COVERAGE`, `ML_HEURISTIC_MAX_CONFIDENCE`, `ML_OOD_MAX_OUTLIER_FRACTION`, `ML_AUTO_CONTAIN_ENABLED`, `ML_AUTO_CONTAIN_THRESHOLD`

## Migration 015

Adds `security_events.ml_source`, `ml_feature_coverage`, `ml_needs_review`; `incidents.ml_classification_status`; `projects.allow_ml_auto_contain` (default false).

## Decisions

- Rare labels merged per `training/labels.py`; test support warning at 30 samples.
- Headline metric = realistic block split.
- Auto-contain requires global flag + project opt-in + strict model checks.
- Feature count **77** (actual list length in `features.py`).

## Not run

- Docker compose / image build
- Postgres migration apply (SQLite tests use `create_all`)
- Full non-`--fast` training (~50k synthetic rows)
- Ruff (not installed in venv)
- Terraform

## Paper / README claims now unsupported

- Any **99.7% accuracy** or **v2.0.0-nb-tuned** GaussianNB production claims
- **78 features** (use **77**)
- **Real CICIDS2017-trained** production model until CSVs are added and bundle retrained with `status=production`

## Runbooks (short)

**Model missing/compromised:** API/worker fall back to heuristic; check `GET /api/v1/ml/status`; redeploy bundle from trusted build; run `verify_model.py`.

**Rotate signing key:** Set new `ML_MODEL_SIGNING_KEY`, `python scripts/sign_model.py`, redeploy API+worker with same key.

## Files touched (high level)

`backend/app/ml/*`, `backend/app/ml/models/bundle/*`, `backend/app/ml/training/*`, `scripts/sign_model.py`, `scripts/verify_model.py`, `scripts/train_models_cli.py`, `backend/app/workers/incident_worker.py`, `backend/app/routers/events.py`, `backend/app/routers/ml.py`, `backend/app/services/incident_service.py`, migration `015`, tests `test_ml_*`, `frontend/src/pages/LiveEventsPage.tsx`, docs, `ml_evaluation/*`.
