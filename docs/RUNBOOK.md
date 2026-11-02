# Runbook (operations)

## Health

- **Liveness:** `GET /health` — always 200 when process up.
- **Readiness:** `GET /health/ready` — 200 when DB check passes; 503 if DB unreachable. Queue reported as `not_configured` when `SQS_INCIDENT_QUEUE_URL` empty.

Docker Compose API service healthcheck uses `/health/ready`.

## Start/stop (local)

```powershell
docker compose up -d
docker compose logs -f api
docker compose down -v   # destroys local DB volume
```

## Key rotation

- **JWT:** set new `SECRET_KEY`, restart API — invalidates existing access tokens.
- **ML bundle:** set new `ML_MODEL_SIGNING_KEY`, run `scripts/sign_model.py`, redeploy API and workers together.

## Tests must not dirty git

Pytest copies ML bundle to `..\lbro-run-scratch\ml-bundle-copy` and signs the copy only.

## Auth rate limits

Login: 10 requests/minute/IP on `/api/v1/auth/login`. Load tests need pacing or API restart.
