# LBRO — EC2 Production Deployment

## Prerequisites

- EC2 instance (recommended: t3.medium or larger, Amazon Linux 2023 / Ubuntu 22.04)
- Docker + Docker Compose v2 installed
- IAM role attached to the instance with permissions for S3 and SQS
- S3 buckets and SQS queues already created
- Port 80 open in the security group (or 443 if using HTTPS termination on the host)

---

## First-Time Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/lbro.git
cd lbro
```

### 2. Create the environment file

```bash
cp .env.prod.example .env
```

Edit `.env` and fill in every value. At minimum:

| Variable | How to generate |
|---|---|
| `POSTGRES_PASSWORD` | `openssl rand -base64 32` |
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `CORS_ORIGINS` | Your domain, e.g. `https://lbro.example.com` |
| `SQS_*_URL` | From the AWS Console → SQS → Queue URL |

### 3. Build images

This builds the API image (tagged `lbro-api:prod`) and the frontend image.
The worker reuses `lbro-api:prod` — no duplicate build.

```bash
docker compose -f docker-compose.prod.yml build
```

### 4. Run database migrations

Run once before the first start, and again after any schema change:

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
```

### 5. Start all services

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 6. Verify

```bash
# All containers should be Up
docker compose -f docker-compose.prod.yml ps

# API health
curl http://localhost:8000/health

# Frontend health (via nginx)
curl http://localhost:80/health
```

---

## Routine Operations

### Deploy a new version

```bash
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose -f docker-compose.prod.yml up -d
```

Docker Compose replaces only containers whose image changed, so postgres is left untouched.

### View logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# One service
docker compose -f docker-compose.prod.yml logs -f api
```

### Restart a single service

```bash
docker compose -f docker-compose.prod.yml restart api
```

### Stop everything

```bash
docker compose -f docker-compose.prod.yml down
```

---

## Rollback

### Roll back to the previous image

```bash
# Re-tag the previous image (if you saved it)
docker tag lbro-api:prev lbro-api:prod
docker compose -f docker-compose.prod.yml up -d
```

### Roll back the database schema

```bash
# Revert one migration
docker compose -f docker-compose.prod.yml run --rm api alembic downgrade -1

# Revert to a specific revision
docker compose -f docker-compose.prod.yml run --rm api alembic downgrade <revision>

# List revision history
docker compose -f docker-compose.prod.yml run --rm api alembic history
```

---

## Docker Optimisation Summary

### What changed vs. dev

| Change | Estimated saving |
|---|---|
| Worker reuses `lbro-api:prod` (no rebuild) | ~3–4 min build time; ~400 MB image pull eliminated |
| `.dockerignore` excludes `__pycache__`, tests, `.venv`, `.git`, `node_modules` | ~50–200 MB smaller build context sent to daemon |
| No LocalStack container in prod | ~300 MB image not pulled |
| No live source volume mounts | Code baked in; no host-path dependency |
| `python:3.12-slim` + multi-stage build (already in place) | Runtime image ~200 MB vs ~1 GB for full python |

### Architecture

```
EC2 host
└── Docker network: lbro-prod-network
    ├── postgres:16-alpine      (persistent data volume)
    ├── lbro-api:prod           (FastAPI, uvicorn, 2 workers)
    │   └── ml_models volume
    ├── lbro-api:prod [worker]  (same image, CMD override → SQS consumer)
    │   └── ml_models volume    (shared read access to ML models)
    └── frontend (nginx:1.27-alpine)
        └── proxies /api/* → api:8000
            exposes :80 to the host
```

---

## Notes

- **HTTPS**: Put an ALB, CloudFront, or Caddy reverse proxy in front of port 80 for TLS termination. The nginx config already sets `Strict-Transport-Security` and `upgrade-insecure-requests`.
- **IAM role vs. access keys**: On EC2, attach an IAM role to the instance and leave `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` unset in `.env`. The AWS SDK resolves credentials from the instance metadata service automatically.
- **ML models**: The `ml_models` named volume persists across container restarts. If you need to seed it, copy model files in with `docker cp` or mount from S3 on startup.
- **Secrets management**: For higher security, replace plain `.env` with AWS Secrets Manager or SSM Parameter Store and pull values at container start.
