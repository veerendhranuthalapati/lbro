# ML Fix Report — `fix/ml-hardening` (review gap closure)

## Summary

Closed review gaps from the prior report: production signing policy, CI verify/sign steps, deploy wiring, honest **n/a - demo-synthetic** headlines, expanded tests (security, worker, retry sweep, project ML policy), migration **016**, frontend badges, and pending-classification retry worker.

## Problem status

| ID | Status | Evidence |
|----|--------|----------|
| P1 Synthetic metrics | **FIXED** | Headlines → `n/a - demo-synthetic`; appendix in `ML_MODEL_EVALUATION.md` |
| P2 Pickle RCE | **FIXED** | HMAC + SHA-256 before `joblib.load`; tamper tests |
| P3 Overconfidence | **FIXED** | All-ones → confidence 0.5, `needs_review`, `ood_flag` |
| P4 Auto-contain | **FIXED** | Global default off; per-project `allow_ml_auto_contain` API + settings UI |
| P5 Sparse ingest | **FIXED** | `event_mapper.py`, event ML fields, badges |
| P6 SQS swallow | **FIXED** | Log + `ml_classification_status=pending` + retry sweep |
| P7 77 features | **FIXED** | `FEATURE_COUNT=77` |
| P8 Coverage / tests | **FIXED** (scoped) | See coverage table below; `test_ml_training.py` marked `@pytest.mark.slow` |

## Signing & deploy

- Policy: `app/ml/signing_policy.py` (min length 32, block known test keys when `ENVIRONMENT=production`).
- Startup: `app/ml/startup_check.py` — API/worker fail fast in production on bad/missing key or bad bundle.
- Image build: `docker/Dockerfile.api` runs `scripts/sign_model.py` when `ML_MODEL_SIGNING_KEY` build-arg is set.
- CI: sign + `scripts/verify_model.py` in `.github/workflows/ci.yml`; Docker build passes release-style build-arg.
- Docs: `docs/DEPLOY_ML_SIGNING.md`, `.env.prod.example`, `docker-compose.prod.yml` (`:ro` bundle), Terraform ECS secret wiring (edit-only).

### Startup when signing key is missing (production)

Command:

```powershell
cd backend
$env:ENVIRONMENT="production"
$env:ML_MODEL_SIGNING_KEY=""
$env:ML_ALLOW_UNSIGNED_MODEL="false"
.\.venv\Scripts\pytest.exe tests/test_ml_review_gaps.py::test_startup_fails_closed_missing_key_production -q
```

**Result:** `1 passed` — `run_ml_startup_check(fail_fast_in_production=True)` raises `ValueError` (signing key policy).

## Verification commands & output

### Full backend tests (default; excludes slow)

```powershell
cd c:\Users\veere\Desktop\lbro\backend
$env:DATABASE_URL="sqlite+aiosqlite:///:memory:"
$env:SECRET_KEY="test-secret-key-minimum-32-characters-ci"
$env:ENVIRONMENT="test"
$env:ML_MODEL_SIGNING_KEY="test-ml-signing-key-minimum-32-characters-long"
$env:ALLOW_PUBLIC_REGISTRATION="true"
.\.venv\Scripts\pytest.exe tests/ -q
```

**Result:** `709 passed, 1 deselected` (after gap tests; slow training excluded by `addopts`).

### Scoped ML module coverage (inference / loader / policy / mapper)

```powershell
.\.venv\Scripts\pytest.exe tests/test_ml_review_gaps.py tests/test_ml_hardening.py tests/test_ml_bundle.py -q `
  --cov=app.ml.bundle_io --cov=app.ml.classifier --cov=app.ml.signing_policy `
  --cov=app.ml.event_mapper --cov=app.ml.startup_check --cov=app.ml.metrics_public --cov-report=term
```

**Result:**

```
app\ml\bundle_io.py          111     12    89%
app\ml\classifier.py         135     13    90%
app\ml\event_mapper.py        27      2    93%
app\ml\metrics_public.py       8      0   100%
app\ml\signing_policy.py      19      0   100%
app\ml\startup_check.py       45      3    93%
TOTAL                        345     30    91%
53 passed
```

(`write_bundle_manifest` export path in `bundle_io.py` remains training-only; loader verify/load paths ≥89%.)

### Verify bundle

```powershell
$env:ML_MODEL_SIGNING_KEY="test-ml-signing-key-minimum-32-characters-long"
$env:ML_MODEL_BUNDLE_DIR="app/ml/models/bundle"
.\.venv\Scripts\python.exe ..\scripts\verify_model.py --load-model
```

**Result:**

```
Manifest and file hashes OK
Model loaded: version=lbro-demo-synthetic-1.0.0 status=demo-synthetic verified=True
```

### Alembic heads

```powershell
.\.venv\Scripts\alembic.exe heads
```

**Result:** `016_ml_classification_retry (head)`

### Postgres migration up / down / up

**Not run:** Docker daemon unavailable on this machine (`dockerDesktopLinuxEngine` pipe missing). Use:

```bash
docker run --rm -d --name lbro-pg -e POSTGRES_PASSWORD=postgres -p 54329:5432 postgres:16
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54329/lbro
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

### Ruff / mypy (touched ML paths)

```powershell
pip install ruff mypy -q
ruff check app/ml/bundle_io.py app/ml/classifier.py app/ml/signing_policy.py app/ml/startup_check.py app/ml/metrics_public.py app/ml/event_mapper.py app/ml/model_registry.py app/workers/incident_worker.py app/workers/ml_retry_sweep.py app/workers/main.py app/routers/ml.py --select E,F,I,W,UP --ignore E501
mypy app/ml/signing_policy.py app/ml/startup_check.py app/ml/metrics_public.py app/ml/event_mapper.py app/workers/ml_retry_sweep.py
```

**Result:** ruff `0 errors` after auto-fix on core modules; mypy `Success: no issues found in 5 source files`.

### Frontend

```powershell
cd ..\frontend
npm run type-check
npm run test -- --run
```

**Result:** type-check pass; **58 passed** Vitest (includes `MlClassificationBadge` states).

## Headline metrics (public)

**n/a - demo-synthetic** everywhere in UI/API/docs for the shipped bundle. Numeric metrics only in **Appendix A** of `ML_MODEL_EVALUATION.md`.

## New / updated tests (`tests/test_ml_review_gaps.py`)

| Test | Purpose |
|------|---------|
| `test_reject_test_signing_key_in_production` | Known test key blocked in prod |
| `test_reject_short_signing_key_in_production` | Min length in prod |
| `test_startup_fails_closed_missing_key_production` | API/worker-style fail fast |
| `test_startup_ok_in_test_environment` | Happy path in test |
| `test_startup_missing_manifest` | Heuristic fallback when no manifest |
| `test_signing_policy_short_key_in_dev` | Dev min length |
| `test_metrics_public_non_demo_summary` | Non-demo manifest passthrough |
| `test_signing_policy_prod_allows_unsigned_when_flag` | `ML_ALLOW_UNSIGNED_MODEL` escape hatch |
| `test_tampered_manifest_json_rejected` | Hash/manifest tamper |
| `test_wrong_signing_key_rejected` | HMAC mismatch |
| `test_sklearn_version_mismatch_rejected` | Library guard |
| `test_input_nan_inf_strings` | Bad inputs |
| `test_input_all_zeros` / `test_input_all_ones_not_confident` / `test_input_sparse_payload` | Contract edges |
| `test_classifier_reload_after_load` | Reload path |
| `test_event_mapper_*` | Mapper aliases / invalid / empty |
| `test_auto_contain_blocked_when_*` (7 tests) | Each failed auto-contain condition |
| `test_malformed_message_does_not_raise` | Malformed SQS body |
| `test_duplicate_delivery_idempotent` | Duplicate SQS delivery |
| `test_classify_missing_incident_returns` | Missing incident |
| `test_model_unavailable_heuristic_fallback` | Model unavailable |
| `test_sqs_enqueue_failure_sets_pending` | SQS enqueue failure |
| `test_project_ml_policy_toggle` | PATCH `/projects/{id}/ml-policy` |
| `test_ml_pending_retry_sweep_enqueues` / `test_ml_pending_retry_sweep_respects_max_attempts` | Pending retry sweep |
| `test_verify_unsigned_rejected_in_test_without_flag` | Unsigned rejected |
| `test_startup_production_raises_on_bad_bundle` | Prod bundle verify fail fast |
| `test_classifier_unexpected_load_error` | Unexpected loader error |
| `test_verify_unsigned_allowed_in_test` | Dev unsigned path |
| `test_verify_signature_requires_key` | Missing key with sig present |
| `test_tampered_signature_file_rejected` | Bad `manifest.sig` |

Slow training: `tests/test_ml_training.py` — CI job `backend-test-slow` runs `pytest -m slow`.

## Deliverable archive

`lbro_ml_fix.zip` — rebuilt from repo root (ML/backend/frontend/docs/scripts paths touched on this branch).

## Not run in this session

- Docker-based Postgres alembic cycle (no Docker daemon).
- `backend-test-slow` full training job locally (marked slow; run in CI or `pytest -m slow`).
