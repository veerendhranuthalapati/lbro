# LBRO — Law-aware Breach Response Orchestrator

LBRO is a production-ready security incident response platform that combines ML-powered attack classification, regulatory compliance automation (GDPR / HIPAA / DPDPA), immutable evidence management, and real-time infrastructure monitoring into a single deployable system.

---

## Quick Start (Local — Docker Compose)

**Prerequisites:** Docker Desktop 24+, Docker Compose v2.

```bash
git clone <repo-url> lbro
cd lbro

# 1. Copy env template
cp .env.example .env
# Edit SECRET_KEY and any SMTP settings you want

# 2. Start everything
docker compose up --build

# 3. Wait ~30s for postgres + localstack to be ready, then seed
docker compose run --rm seed

# 4. Open the UI
open http://localhost:5173   # dev  (or http://localhost:80 after production build)
```

**Default credentials:**
| Email | Password | API Key | Role |
|---|---|---|---|
| admin@lbro.local | Admin123! | `lbro-dev-api-key-change-in-production` | Admin |
| analyst@lbro.local | Analyst123! | `lbro-dev-analyst-key` | Analyst |

> **Warning:** Change all secrets before exposing to any network.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser                                                        │
│  React 18 + Vite + TailwindCSS + Zustand + React Query         │
└──────────────┬──────────────────────────────────────────────────┘
               │ HTTPS  X-API-Key
               ▼
┌─────────────────────────────────────┐
│  nginx (port 80)                   │
│  /api/* → FastAPI   /* → SPA        │
└───────────┬─────────────────────────┘
            │
┌───────────▼─────────────────────────┐     ┌──────────────────────┐
│  FastAPI (port 8000)               │────▶│  PostgreSQL 16        │
│  • Auth (X-API-Key + JWT)          │     │  (via asyncpg)        │
│  • RBAC (4 roles, 25+ perms)       │     └──────────────────────┘
│  • Incidents / Evidence / Audit    │
│  • Compliance / Notifications      │     ┌──────────────────────┐
│  • Rate limiting (sliding window)  │────▶│  S3 / LocalStack      │
│  • Security headers                │     │  Evidence vault (WORM)│
└───────────┬─────────────────────────┘     └──────────────────────┘
            │ SQS enqueue
┌───────────▼─────────────────────────┐     ┌──────────────────────┐
│  Worker (SQS long-poll)            │────▶│  SQS / LocalStack     │
│  • ML classification               │     │  Incidents queue      │
│  • Notification retry              │     │  Notifications queue  │
│  • Auto-containment (critical)     │     │  DLQ (14-day retain)  │
└─────────────────────────────────────┘     └──────────────────────┘
```

**AWS Production:**
- ECS Fargate (API, Worker, Frontend services with autoscaling)
- RDS PostgreSQL 16 Multi-AZ
- S3 with Object Lock (WORM compliance mode in production)
- SQS with DLQ and redrive policy
- CloudWatch Alarms → SNS email alerts
- Secrets Manager for all credentials
- VPC with public/private subnets, NAT gateways, VPC flow logs

---

## Repository Layout

```
lbro/
├── backend/
│   ├── app/
│   │   ├── core/          # security, RBAC, exceptions
│   │   ├── middleware/    # rate limiting, security headers
│   │   ├── ml/            # CICIDS2017 classifier, model registry
│   │   ├── migrations/    # Alembic versions
│   │   ├── models/        # SQLAlchemy models
│   │   ├── routers/       # FastAPI route handlers
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   └── workers/       # SQS consumers
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/           # Axios client + typed API modules
│   │   ├── components/    # Reusable UI components
│   │   ├── layouts/       # AppLayout, ProtectedRoute
│   │   ├── pages/         # Route-level page components
│   │   ├── store/         # Zustand auth store
│   │   └── types/         # TypeScript interfaces
│   ├── nginx.conf
│   └── Dockerfile
├── docker/
│   ├── Dockerfile.api
│   └── Dockerfile.worker
├── terraform/
│   ├── modules/
│   │   ├── networking/    # VPC, subnets, NAT, flow logs
│   │   ├── rds/           # PostgreSQL with encryption
│   │   ├── s3/            # Evidence, reports, ML models buckets
│   │   ├── sqs/           # Queues + DLQ
│   │   ├── ecs/           # Fargate cluster, ALB, autoscaling
│   │   ├── iam/           # Execution + task roles
│   │   └── monitoring/    # CloudWatch alarms + dashboard
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── .github/
│   └── workflows/
│       ├── ci.yml         # Lint, test, build, security scan
│       └── deploy.yml     # Push to ECR, update ECS
├── scripts/
│   ├── localstack-init.sh
│   └── seed.py
├── docker-compose.yml
└── .env.example
```

---

## API Reference

Base URL: `http://localhost:8000/api/v1`  
Auth: `X-API-Key: <key>` header  
Docs: `http://localhost:8000/docs`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Exchange API key for session |
| POST | `/auth/register` | Create user (admin only) |
| POST | `/auth/api-key/rotate` | Rotate your API key |
| GET | `/incidents` | List incidents (paginated) |
| POST | `/incidents` | Create + auto-classify incident |
| GET | `/incidents/{id}` | Incident detail + timeline |
| PATCH | `/incidents/{id}` | Update incident |
| POST | `/incidents/{id}/status` | Transition status (state machine) |
| POST | `/incidents/{id}/reopen` | Reopen closed incident |
| POST | `/incidents/{id}/evidence` | Upload evidence file |
| GET | `/incidents/{id}/evidence` | List evidence |
| GET | `/evidence/{id}/download-url` | Pre-signed S3 download URL |
| POST | `/evidence/{id}/verify` | SHA-256 integrity check |
| GET | `/notifications` | List regulatory notifications |
| POST | `/notifications/{id}/approve` | Approve for sending |
| POST | `/notifications/{id}/dispatch` | Auto-approve + send |
| GET | `/compliance/dashboard` | Compliance score + deadlines |
| GET | `/ml/stats` | ML model stats + attack distribution |
| GET | `/audit-logs` | Audit log (admin only) |
| GET | `/health` | Liveness probe |
| GET | `/health/ready` | Readiness probe (checks DB + SQS) |

---

## ML Classification

The backend uses a scikit-learn pipeline trained on the **CICIDS2017** dataset:
- **78 network flow features** (packet rates, byte counts, IAT, flag counts, etc.)
- **15 attack classes**: DoS Hulk, PortScan, DDoS, GoldenEye, FTP/SSH Patator, slowloris, Slowhttptest, Bot, Web Attack (XSS/SQLi/BruteForce), Infiltration, Heartbleed, BENIGN
- **Heuristic fallback** when no trained model file is present (port-based + packet rate rules)
- **Confidence thresholds**: incidents below 65% confidence are flagged for analyst review
- **Explainability**: top 10 feature importances returned with every prediction

To train a real model:
```bash
# Place your CICIDS2017 CSVs in backend/data/cicids2017/
docker compose run --rm api python -m app.ml.train
```

---

## Compliance Automation

When an incident is created with `jurisdictions` set, LBRO automatically:

1. Generates compliance obligations (e.g. "notify DPA within 72h" for GDPR)
2. Creates regulatory notification drafts with correct authority + deadline
3. Sends compliance dashboard scores updated in real-time
4. Tracks overdue notifications with retry logic (max 3 retries via SQS)

| Regulation | Deadline | Authority |
|---|---|---|
| GDPR | 72 hours | Lead Supervisory Authority |
| HIPAA | 60 days (60 × 24h) | HHS Office for Civil Rights |
| DPDPA | 72 hours | Data Protection Board of India |

---

## AWS Deployment

### Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform 1.6+
- ECR repositories created for `lbro-api`, `lbro-worker`, `lbro-frontend`

### Steps

```bash
# 1. Build + push images to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

docker build -f docker/Dockerfile.api  -t <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-api:latest .
docker build -f docker/Dockerfile.worker -t <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-worker:latest .
docker build -f frontend/Dockerfile      -t <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-frontend:latest frontend/

docker push <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-api:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-worker:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-frontend:latest

# 2. Initialize Terraform (create S3 bucket + DynamoDB table for state first)
cd terraform
terraform init \
  -backend-config="bucket=your-tfstate-bucket" \
  -backend-config="key=lbro/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=lbro-tfstate-lock"

# 3. Plan + apply
terraform plan \
  -var="environment=staging" \
  -var="api_image=<account>.dkr.ecr.us-east-1.amazonaws.com/lbro-api:latest" \
  -var="worker_image=<account>.dkr.ecr.us-east-1.amazonaws.com/lbro-worker:latest" \
  -var="frontend_image=<account>.dkr.ecr.us-east-1.amazonaws.com/lbro-frontend:latest" \
  -var="app_secret_key=$(openssl rand -hex 32)" \
  -var="alert_email=ops@yourcompany.com"

terraform apply -auto-approve

# 4. Run migrations
aws ecs run-task \
  --cluster lbro-staging-cluster \
  --task-definition lbro-staging-api \
  --launch-type FARGATE \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
```

---

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run locally (with docker-compose postgres + localstack running)
DATABASE_URL=postgresql+asyncpg://lbro:lbro@localhost:5432/lbro \
SECRET_KEY=dev-secret-key-change-in-production \
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # Vite dev server on :5173 with proxy to :8000
npm run type-check # TypeScript validation
npm run lint       # ESLint
npm run build      # Production build
```

### Tests

```bash
# Backend unit + integration tests (uses SQLite in-memory)
cd backend && pytest tests/ -v

# Validate Terraform
cd terraform && terraform init -backend=false && terraform validate
```

---

## Security Notes

- API keys are stored in memory only in the browser (never localStorage). Session expiry is stored in sessionStorage without the key itself.
- All API keys are hashed with bcrypt before database storage.
- Evidence files are immutable once uploaded (S3 Object Lock in production, `is_immutable=True` DB flag always).
- Every evidence access is recorded in the chain of custody.
- Rate limiting: 100 req/min per IP (sliding window, Redis-less in-memory implementation).
- Security headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy on every response.
- JWT tokens expire in 1 hour; refresh tokens in 7 days.
- Account lockout after 5 failed login attempts (15-minute cooldown).
