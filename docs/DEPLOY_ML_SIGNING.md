# ML bundle signing — deploy runbook

## Overview

Production images must **not** ship with the public pytest signing key. The bundle under `backend/app/ml/models/bundle/` is committed **without** a valid production `manifest.sig`; signing happens at **image build** or **release** time using `ML_MODEL_SIGNING_KEY`.

## Key policy

- Minimum length **32** characters (`app/ml/signing_policy.py`).
- Known test/dev keys are **rejected** when `ENVIRONMENT=production`.
- API and worker call `run_ml_startup_check()` at startup: in production, a missing key (with unsigned bundles disallowed) prevents boot.

## Local / CI verify

```powershell
cd backend
$env:ML_MODEL_SIGNING_KEY="test-ml-signing-key-minimum-32-characters-long"
$env:ML_MODEL_BUNDLE_DIR="app/ml/models/bundle"
python ..\scripts\sign_model.py --bundle-dir app/ml/models/bundle
python ..\scripts\verify_model.py --load-model
```

## Docker Compose (prod example)

Set in `.env.prod` (see `.env.prod.example`):

- `ML_MODEL_SIGNING_KEY` — release secret (not the test key)
- `ML_MODEL_BUNDLE_DIR=/app/app/ml/models/bundle`

`docker-compose.prod.yml` mounts the bundle **read-only** (`:ro`) and passes the signing key into API/worker containers.

## API image build

```bash
docker build -f docker/Dockerfile.api \
  --build-arg ML_MODEL_SIGNING_KEY="$ML_MODEL_SIGNING_KEY" \
  -t lbro-api:release .
```

When the build-arg is non-empty, `scripts/sign_model.py` runs inside the image and writes `manifest.sig` before the image is published.

## ECS / Terraform

Terraform defines `ml_model_signing_key` in Secrets Manager and injects `ML_MODEL_SIGNING_KEY` into API and worker task definitions (edit-only in repo; apply in your environment).

## Rotation

1. Generate a new key (≥32 chars, not in `KNOWN_TEST_SIGNING_KEYS`).
2. Re-sign: `python scripts/sign_model.py --bundle-dir <bundle>`.
3. Deploy API + worker together with the new secret.
4. Run `python scripts/verify_model.py --load-model` in the release pipeline (see `.github/workflows/ci.yml`).
