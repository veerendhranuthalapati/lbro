# LBRO — Law-aware Breach Response Orchestrator

> From alert to contained-and-documented in under five minutes.

LBRO is a cloud-native automated incident response platform that detects security breaches, executes containment actions, packages forensic evidence with full chain-of-custody, and generates jurisdiction-compliant regulatory notifications — all orchestrated through a FastAPI backend deployed on AWS.

---

## Architecture Overview

```
Internet → ALB → ECS Fargate (FastAPI) → SQS → Worker Tasks
                      ↓                              ↓
                   RDS Postgres              S3 Evidence Buckets
                      ↓                              ↓
              Secrets Manager              CloudWatch / X-Ray
```

## Compliance Coverage
| Regulation | Notification Window | Template Auto-Selected |
|------------|--------------------|-----------------------|
| GDPR       | 72 hours           | ✅                     |
| HIPAA      | 60 days            | ✅                     |
| DPDPA (IN) | ASAP / reasonable  | ✅                     |

## Quick Start

### Prerequisites
- AWS CLI configured
- Terraform >= 1.6
- Docker
- Python 3.12+
- Node 20+

### Infrastructure Deployment

```bash
# Bootstrap state backend (once)
cd terraform/environments/dev
terraform init
terraform apply -target=module.s3_state

# Full deploy
terraform apply
```

### Local Development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install && npm run dev
```

### Run Tests

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=html
```

## Repository Layout

```
lbro/
├── terraform/
│   ├── modules/          # Reusable infrastructure modules
│   │   ├── vpc/          # Network foundation
│   │   ├── ecs/          # Fargate cluster + services
│   │   ├── rds/          # Postgres with encryption
│   │   ├── sqs/          # Incident queues + DLQs
│   │   ├── s3/           # Evidence buckets + forensics
│   │   ├── secrets/      # Secrets Manager integration
│   │   ├── iam/          # Least-privilege roles
│   │   └── monitoring/   # CloudWatch + alarms + dashboards
│   └── environments/
│       ├── dev/          # Dev environment root
│       └── prod/         # Prod environment root
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── core/         # Config, security, logging
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── services/     # Business logic
│   │   └── schemas/      # Pydantic schemas
│   └── tests/
├── frontend/             # React dashboard
├── docker/               # Dockerfiles
└── .github/workflows/    # CI/CD pipelines
```

## Core Design Principles

1. **Infrastructure as Code — everything in Terraform.** No clickops. Every resource is reproducible.
2. **Least privilege by default.** Every ECS task has a scoped IAM role. No wildcard policies.
3. **Defense in depth.** Private subnets, security groups, encryption at rest + in transit.
4. **Observable by default.** Structured JSON logs, X-Ray tracing, CloudWatch dashboards ship on day one.
5. **Chain-of-custody integrity.** S3 Object Lock (WORM) on evidence buckets. No human can modify evidence post-upload.
