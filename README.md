# LBRO — Law-aware Breach Response Orchestrator

LBRO is a security incident response platform that combines **ML-powered network attack classification**, **regulatory compliance workflows** (GDPR, HIPAA, DPDPA, and extensible rule packs), **immutable evidence handling**, **multi-project RBAC**, and **infrastructure monitoring** in one deployable stack.

This document is the primary on-ramp for developers and operators. For the threat-to-obligation inference feature, also read [docs/COMPLIANCE_INFERENCE.md](docs/COMPLIANCE_INFERENCE.md), [docs/adr/ADR-001-threat-to-obligation.md](docs/adr/ADR-001-threat-to-obligation.md), and [FEATURE_REPORT.md](FEATURE_REPORT.md) on branch `feature/threat-to-obligation`.

> **Legal disclaimer:** LBRO provides **decision support** for breach response. It is **not legal advice**. Inferred obligations, deadlines, and technique mappings require **human analyst review** and **counsel review** of the knowledge base before operational reliance. API responses, PDF reports, and UI surfaces include a `disclaimer` field where inference is used.

---

## Table of contents

1. [What LBRO does](#what-lbro-does)
2. [Security design](#security-design)  
   [Results (synthetic data only)](#results-synthetic-data-only)
3. [End-to-end data flows](#end-to-end-data-flows)
3. [Quick start (Docker Compose)](#quick-start-docker-compose)
4. [Local development (Windows PowerShell)](#local-development-windows-powershell)
5. [Architecture](#architecture)
6. [Multi-project tenancy and RBAC](#multi-project-tenancy-and-rbac)
7. [Incidents and ML classification](#incidents-and-ml-classification)
8. [Compliance: manual path vs inference path](#compliance-manual-path-vs-inference-path)
9. [Data map (asset inventory)](#data-map-asset-inventory)
10. [Threat-to-obligation inference pipeline](#threat-to-obligation-inference-pipeline)
11. [Notifications (human-in-the-loop)](#notifications-human-in-the-loop)
12. [Evidence, audit, and reports](#evidence-audit-and-reports)
13. [Repository layout](#repository-layout)
14. [API reference](#api-reference)
15. [Environment variables](#environment-variables)
16. [Database migrations (Alembic)](#database-migrations-alembic)
17. [Seed data and demo flags](#seed-data-and-demo-flags)
18. [Testing and quality gates](#testing-and-quality-gates)
19. [Documentation index](#documentation-index)
20. [AWS deployment](#aws-deployment)
21. [Security notes](#security-notes)
22. [MITRE ATT&CK attribution](#mitre-attck-attribution)
23. [Known limitations](#known-limitations)

---

## What LBRO does

| Capability | Description |
|------------|-------------|
| **Incident lifecycle** | Create, assign, contain, resolve, and reopen incidents with a state machine and timeline (`IncidentAction`). |
| **Security events** | Ingest events that can spawn or enrich incidents; worker processes SQS messages for async ML and side effects. |
| **ML classification** | Maps CICIDS2017-style flow features to **15 attack labels** (including `BENIGN`); signed model bundle, review thresholds, heuristic fallback. |
| **Compliance records** | Tracks regulatory obligations per incident (deadlines, status). |
| **Regulatory notifications** | Draft → approve → dispatch workflow; **nothing inferred is sent automatically**. |
| **Evidence vault** | Upload to S3 (LocalStack locally); chain of custody; integrity verification. |
| **Data map** | Project-scoped asset inventory with data categories and **per-jurisdiction record counts** (metadata only, no real PII). |
| **Exposure inference** | Attack class → MITRE techniques → categories at risk → residency → rule packs → **suggested** obligations with trace JSON. |
| **Projects** | Tenant boundary; members have project roles; `compliance_inference_mode` per project. |
| **Platform admin** | `super_admin` can operate across projects; bypasses are audit-logged. |

---

## Security design

The controls below are implemented in code and covered by tests. Each row names the test file that exercises it.

| Control | How it works | Tested in |
|---------|--------------|-----------|
| **Signed ML model bundle** | HMAC-SHA256 manifest signature plus per-file SHA-256 hashes, checked before the model is loaded. Unsigned bundles are rejected outside dev and test. | `tests/test_ml_review_gaps.py` (`test_tampered_manifest_json_rejected`, `test_wrong_signing_key_rejected`); `tests/test_ml_hardening.py` (`test_tampered_model_rejected`) |
| **Auto-containment off by default** | `ML_AUTO_CONTAIN_ENABLED=false`. Auto-containment needs the global flag, a per-project opt-in, critical severity, high confidence, and a non-heuristic, non-OOD result. | `tests/test_ml_hardening.py` (`test_auto_contain_default_off`); `tests/test_ml_review_gaps.py` (seven `test_auto_contain_blocked_when_*` cases) |
| **Account lockout** | 5 consecutive failed logins lock the account for 15 minutes. | `tests/test_auth_extended.py` (`test_account_lockout_after_five_failures`); `tests/test_login_timing.py` |
| **Token revocation on logout** | Each JWT has a `jti` that is stored in `revoked_tokens` on logout. Revoked tokens are rejected on later requests. | `tests/test_auth_extended.py` (`test_logout_revokes_token`); `tests/integration/test_auth.py` (`test_revoked_token_rejected_on_me_endpoint`, needs PostgreSQL) |
| **Hashed API keys** | Project and user API keys are bcrypt-hashed in the database and never stored in plain text. | `tests/test_api_key_security.py` (`test_api_key_hash_verify_roundtrip`) |
| **Project isolation and RBAC** | Users only see projects they belong to. Roles are checked on every protected route. | `tests/test_project_isolation.py`; `tests/test_rbac.py` |

Known gaps are listed under [Known limitations](#known-limitations). MFA is not implemented, and rate limiting is in-memory.

---

## Results (synthetic data only)

The shipped model is trained on **synthetic data** that imitates CICIDS2017. It is not evaluated on real traffic, and the numbers below should not be used for compliance or marketing claims. The model is a HistGradientBoosting classifier with isotonic calibration, evaluated on a held-out realistic split of 450 rows. Full details are in [ML_MODEL_EVALUATION.md](ML_MODEL_EVALUATION.md).

| Metric (realistic split, 450 rows) | Value |
|-------------------------------------|-------|
| Accuracy | 98.0% |
| Macro F1 | 0.910 |
| Weighted F1 | 0.979 |
| Attack labels at F1 = 1.00 | 9 of 15 |
| Weakest labels | Web Attack XSS (F1 0.33, 5 test rows), SQL injection (F1 0.60) |

Evaluation on real CICIDS2017 data is not yet done. See [Known limitations](#known-limitations).

---

## End-to-end data flows

### Flow A — Incident created with manual jurisdictions (legacy, still supported)

```text
Analyst POST /incidents
  → Incident row (optional affected_jurisdictions, personal_data_involved, health_data_involved)
  → If jurisdictions or flags set:
       ComplianceService.generate_obligations()  ← REGULATION_RULES hours in compliance_service.py
       NotificationService.generate_for_incident() ← settings.GDPR/HIPAA/DPDPA_NOTIFICATION_HOURS
  → SQS may enqueue worker for ML classification (separate path)
```

Manual deadlines use **Python constants** (`REGULATION_RULES` and `config.py` notification hours). They are **not** read from `laws.json`.

### Flow B — Threat-to-obligation inference (suggested obligations)

```text
ML ClassificationResult (attack_category, confidence, source, needs_review, ood_flag)
  → attack_to_technique.json (curated MITRE links; BENIGN → no techniques)
  → technique_to_data.json (impact types, data categories, exposure assumptions)
  → Linked assets (confirmed + suggested) × asset_residency (jurisdiction + record_count)
  → laws.json rule evaluation (citations, verification_status, legal_review_status)
  → IncidentExposureAssessment (trace + warnings + disclaimer)
  → ComplianceRecord rows with source=inferred, analyst_decision=pending
  → Analyst accept/dismiss (required reason) — still no auto-dispatch
```

Recomputation runs after ML classification (worker), asset link changes, and on `POST /incidents/{id}/exposure`. Identical inputs produce identical `inputs_hash` (deterministic engine).

```mermaid
flowchart TB
  subgraph ingest [Ingest]
    EV[Security event / manual incident]
    ML[ML classifier or heuristic]
  end
  subgraph kb [Knowledge base - JSON validated at startup]
    ATK[attack_to_technique.json]
    TEC[technique_to_data.json]
    CAT[data_categories.json]
    LAW[laws.json]
  end
  subgraph map [Data map]
    AS[assets]
    AR[asset_residency]
    IA[incident_assets]
  end
  subgraph out [Outputs]
    ASM[incident_exposure_assessments]
    CR[compliance_records - inferred]
    HUMAN[Analyst accept / dismiss]
    NOTIF[notifications - manual approve only]
  end
  EV --> ML
  ML --> ATK --> TEC
  TEC --> map
  map --> LAW
  LAW --> ASM --> CR --> HUMAN
  HUMAN -.-> NOTIF
```

---

## Quick start (Docker Compose)

**Prerequisites:** Docker Desktop 24+, Docker Compose v2.

```bash
git clone <repo-url> lbro
cd lbro

cp .env.example .env
# Edit SECRET_KEY and any SMTP settings

docker compose up --build

# After postgres + localstack are healthy (~30s):
docker compose run --rm seed

# UI: http://localhost:5173 (Vite dev) or http://localhost:80 (production nginx build)
# API docs: http://localhost:8000/docs
```

**Default credentials (change before any network exposure):**

| Email | Password | API key (dev) | Role |
|-------|----------|---------------|------|
| admin@lbro.local | Admin123! | `lbro-dev-api-key-change-in-production` | Admin |
| analyst@lbro.local | Analyst123! | `lbro-dev-analyst-key` | Analyst |

Optional fictional **data map** seed (not for production):

```bash
LBRO_SEED_DEMO_ASSETS=1 docker compose run --rm seed
```

Requires a project with slug `demo-compliance` (see [Seed data](#seed-data-and-demo-flags)).

---

## Local development (Windows PowerShell)

Use the repo’s backend virtual environment and Docker for Postgres + LocalStack.

```powershell
cd c:\path\to\lbro

Copy-Item .env.example .env
# Set SECRET_KEY (32+ chars), DATABASE_URL, ML_MODEL_SIGNING_KEY for tests

docker compose up -d postgres localstack

cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:DATABASE_URL = "postgresql+asyncpg://lbro:lbro@localhost:5432/lbro"
$env:SECRET_KEY = "dev-secret-key-change-in-production-min-32-chars"
$env:ENVIRONMENT = "development"
$env:ML_MODEL_SIGNING_KEY = "test-ml-signing-key-minimum-32-characters-long"
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Frontend (separate terminal):

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173 → proxies API to :8000
npm run type-check
npm run lint
npm run test -- --run
```

Backend tests (SQLite in-memory; no Postgres required for default suite):

```powershell
cd backend
$env:DATABASE_URL = "sqlite+aiosqlite:///:memory:"
$env:SECRET_KEY = "test-secret-key-minimum-32-characters-ci"
$env:ENVIRONMENT = "test"
$env:ML_MODEL_SIGNING_KEY = "test-ml-signing-key-minimum-32-characters-long"
$env:ALLOW_PUBLIC_REGISTRATION = "true"
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│  Browser — React 18, Vite, Tailwind, Zustand, React Query       │
│  Routes: incidents, data map, compliance, infrastructure, …    │
└──────────────┬──────────────────────────────────────────────────┘
               │ HTTPS / JWT (users), Bearer proj_* (ingest)
               ▼
┌─────────────────────────────────────┐
│  nginx (:80)  /api/* → FastAPI      │
└───────────┬─────────────────────────┘
            ▼
┌─────────────────────────────────────┐     ┌──────────────────────┐
│  FastAPI (:8000)                    │────▶│  PostgreSQL 16       │
│  Auth, RBAC, rate limit, headers     │     │  asyncpg + Alembic   │
│  Routers: incidents, assets,        │     └──────────────────────┘
│  exposure, knowledge, compliance,   │
│  notifications, ml, reports, …      │     ┌──────────────────────┐
└───────────┬─────────────────────────┘────▶│  S3 / LocalStack     │
            │ SQS enqueue                   │  Evidence, reports   │
            ▼                               └──────────────────────┘
┌─────────────────────────────────────┐     ┌──────────────────────┐
│  Worker (SQS long poll)             │────▶│  SQS queues + DLQ    │
│  ML classify, exposure recompute,   │     └──────────────────────┘
│  notification retry, auto-contain   │
│  (global flag + strict gates)       │
└─────────────────────────────────────┘
```

**Startup validation:** The API loads and validates the compliance knowledge bundle (`app/compliance/knowledge/*.json`) on startup. Invalid JSON or broken cross-references **fail fast** with a clear error.

**AWS production (summary):** ECS Fargate (API, worker, frontend), RDS PostgreSQL 16, S3 Object Lock for evidence, SQS + DLQ, CloudWatch, Secrets Manager, VPC — see [terraform/README.md](terraform/README.md) and [AWS deployment](#aws-deployment).

---

## Multi-project tenancy and RBAC

### Two-level roles

1. **Platform:** `super_admin` — all permissions, cross-project read/manage where defined.
2. **Project:** `admin` > `analyst` > `viewer` — scoped via project membership.

Permission checks use `Permission` enums in `app/core/rbac.py`, not raw role strings. Cross-project IDOR attempts return **404** (not 403) for incident/asset routes using `project_access` helpers.

### Permissions relevant to compliance inference

| Permission | Typical roles | Purpose |
|------------|---------------|---------|
| `VIEW_ASSETS` | viewer+ | Data Map page, read assets |
| `MANAGE_ASSETS` | analyst+, admin | Create/update/delete assets, import/export |
| `CONFIRM_EXPOSURE` | analyst+, admin | Confirm/reject suggested incident–asset links, set exposure fraction |
| `VIEW_COMPLIANCE` | viewer+ | Compliance dashboard and obligation lists |
| `MANAGE_COMPLIANCE` | analyst+, admin | Manage compliance records |
| `APPROVE_NOTIFICATION` | analyst+, admin | Approve notification drafts |
| `DISPATCH_NOTIFICATION` | analyst+, admin | Send approved notifications |

Project **compliance inference mode** (`GET/PATCH /api/v1/projects/{id}/compliance-inference`) requires project **admin**; changes are audit-logged.

---

## Incidents and ML classification

### Attack labels

The classifier outputs one of **15** `ATTACK_CLASSES` (see `app/ml/features.py`):

`BENIGN`, `DoS Hulk`, `PortScan`, `DDoS`, `DoS GoldenEye`, `FTP-Patator`, `SSH-Patator`, `DoS slowloris`, `DoS Slowhttptest`, `Bot`, `Web Attack - Brute Force`, `Web Attack - XSS`, `Infiltration`, `Web Attack - Sql Injection`, `Heartbleed`.

### Features

**77** network flow features in canonical CICIDS2017 order (`FEATURE_COUNT` in `features.py`). Event ingestion maps payloads through `app/ml/event_mapper.py` into this vector.

### Classification contract

Each result includes:

- `source` — `model` vs heuristic paths
- `confidence` — float
- `needs_review` — analyst queue when confidence or policy triggers
- `ood_flag` — out-of-distribution signal when enabled

Thresholds (defaults in `config.py`):

| Setting | Default | Role |
|---------|---------|------|
| `ML_CONFIDENCE_THRESHOLD` | 0.75 | High-confidence band |
| `ML_REVIEW_THRESHOLD` | 0.75 | Below → review / provisional inference |
| `ML_REVIEW_QUEUE_THRESHOLD` | 0.60 | Queue for analyst review |
| `ML_HEURISTIC_MAX_CONFIDENCE` | 0.50 | Cap for heuristic source |

Production bundles require **`ML_MODEL_SIGNING_KEY`** (HMAC manifest signing in `app/ml/bundle_io.py`). Unsigned bundles are rejected unless explicitly allowed in dev/test.

### Training

```bash
# Place CICIDS2017 CSVs under backend/data/cicids2017/
docker compose run --rm api python -m app.ml.train
```

See [docs/ML_MODEL_CARD.md](docs/ML_MODEL_CARD.md) for model card details.

---

## Compliance: manual path vs inference path

Both paths can coexist. The project’s `compliance_inference_mode` controls whether the engine runs.

| Mode | Engine | Manual `affected_jurisdictions` |
|------|--------|----------------------------------|
| `manual` | Off | Only source of rule matching for inference-style assessment |
| `hybrid` (default) | On | Union with engine suggestions |
| `inferred` | On | Engine-primary; manual still allowed as additions |

### Manual path (on incident create)

When `affected_jurisdictions` **or** `personal_data_involved` **or** `health_data_involved` is set (`app/routers/incidents.py`):

1. **`ComplianceService.generate_obligations`** — inserts `ComplianceRecord` rows from `REGULATION_RULES` (GDPR / HIPAA / DPDPA) using fixed hour offsets from `compliance_service.py`.
2. **`NotificationService.generate_for_incident`** — creates **pending** notification drafts using `settings.GDPR_NOTIFICATION_HOURS` (72), `HIPAA_NOTIFICATION_HOURS` (1440 = 60×24), `DPDPA_NOTIFICATION_HOURS` (72).

| Regulation | Default hours (config) | Typical authority (templates) |
|------------|------------------------|-------------------------------|
| GDPR | 72 | Supervisory authority |
| HIPAA | 1440 (60 days) | HHS OCR |
| DPDPA | 72 | Data Protection Board (India) |

These values are **simplified** operational defaults for the legacy path. They are **duplicated** from the richer rule packs in `laws.json` used by inference.

### Inference path

Uses **`laws.json` only** for deadlines and conditions on suggested obligations. Rules include citations, `verification_status`, and `legal_review_status` (all packs start **`unreviewed`** until counsel reviews).

Accepting an inferred obligation **does not** automatically create or dispatch a notification draft today; analysts still use the existing notification approve/dispatch flow for sent communications.

---

## Data map (asset inventory)

### Purpose

Represent **where data lives** (assets), **what categories** they hold, and **how many data-subject records** sit in each jurisdiction — **counts and metadata only**, never real personal data in seed/demo content.

### Core entities

| Entity | Description |
|--------|-------------|
| `assets` | Name, type, classification, `data_categories[]`, identifiers (hostname, IP/CIDR, ARN, etc.), project scope |
| `asset_residency` | Per asset: jurisdiction code (ISO alpha-2, `EU`/`EEA`, sub-national e.g. `US-CA`), `record_count`, `count_basis` (exact / estimated / unknown) |
| `incident_assets` | Link incident ↔ asset; `link_source` manual or auto_match; `status` suggested / confirmed / rejected; `exposure_fraction` 0–1 |

### Auto-matching

`app/compliance/matching.py` normalizes identifiers from incidents, security events, and ML flow fields. **High** confidence: exact hostname/FQDN, ARN. **Medium**: CIDR containment (IPv4/IPv6 via `ipaddress`). **Low**: name substring — **never auto-confirmed**; stays `suggested` until analyst confirms.

### UI

- **`/data-map`** — table, filters, create/edit, import dry-run, export (CSV formula injection guarded on export).
- **Incident → Exposure & Obligations tab** — linked assets, techniques, jurisdictions with lower/upper bounds, obligations, warnings, trace, disclaimer.

---

## Threat-to-obligation inference pipeline

Implementation: pure functions in `app/compliance/engine/pipeline.py`; persistence in `app/services/exposure_service.py`.

### Knowledge files (`backend/app/compliance/knowledge/`)

| File | Role |
|------|------|
| `data_categories.json` | Controlled vocabulary (`personal_identifiers`, `health_data`, …) with `is_personal_data` / `is_special_category` |
| `attack_to_technique.json` | Maps each `ATTACK_CLASS` to MITRE Enterprise techniques (pinned **v20.0**); `BENIGN` unmapped |
| `technique_to_data.json` | Per technique: impact types, categories at risk, `exposure_assumption`, `confirms_exfiltration` |
| `laws.json` | Rule packs: `applies_when`, obligations, deadlines, citations, verification flags |

Each file carries `schema_version`, `content_version`, `last_reviewed`, and `sources`. Loader: `app/compliance/knowledge/loader.py`.

Verify ATT&CK IDs after editing mappings:

```powershell
cd backend
.\.venv\Scripts\python.exe ..\scripts\verify_attack_mapping.py
```

### Engine behaviour (summary)

1. **Attack → techniques** with `likely` / `possible` and rationale.
2. **Techniques → categories**; availability-only attacks → **no breach-notification trigger** by confidentiality (e.g. DoS), with explicit explanation.
3. **Assets** — intersect categories; exfiltration classes may expose full asset category set.
4. **Jurisdictions** — per jurisdiction: `lower_bound`, `upper_bound`, `point_estimate`, `deduplication_unknown: true` when summing across assets (never fake-exact totals).
5. **Rules** — evaluate all packs; unsupported residency codes → `unsupported_jurisdiction` warning with count.
6. **Provisional gating** — heuristic/OOD/low confidence/weak matches → assessment `provisional`; obligations still listed but flagged.
7. **Trace** — ordered JSON steps for UI and PDF.

### API (inference-related)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/knowledge/versions` | Knowledge `content_version` values |
| GET | `/api/v1/knowledge/attack-mapping` | Read-only mapping for UI |
| GET/POST/PATCH/DELETE | `/api/v1/assets` | CRUD, filters, pagination |
| POST | `/api/v1/assets/import` | CSV/JSON; dry-run supported |
| GET | `/api/v1/assets/export/csv` | Export |
| POST | `/api/v1/assets/{id}/exposure-simulation` | What-if by attack class (no incident) |
| GET/POST/PATCH | `/api/v1/incidents/{id}/assets` | List, link, confirm/reject |
| GET/POST | `/api/v1/incidents/{id}/exposure` | Latest assessment / recompute |
| GET | `/api/v1/incidents/{id}/obligations` | Manual + inferred |
| POST | `/api/v1/incidents/{id}/obligations/{id}/accept` | Requires reason; audit |
| POST | `/api/v1/incidents/{id}/obligations/{id}/dismiss` | Requires reason; audit |
| GET/PATCH | `/api/v1/projects/{id}/compliance-inference` | Mode selector (admin) |

Interactive OpenAPI: `http://localhost:8000/docs`.

---

## Notifications (human-in-the-loop)

State machine: **pending → approved → sent** (or failed / cancelled).

- **`POST /notifications/{id}/approve`** — analyst approval.
- **`POST /notifications/{id}/dispatch`** — approve + send (SMTP when configured) + SQS retry semantics.

**Safety:** Tests assert **inferred** compliance rows cannot be dispatched without explicit human approval on the notification workflow. Inference creates **suggestions**, not outbound email.

---

## Evidence, audit, and reports

- **Evidence:** upload to project-scoped storage; SHA-256 verification; download via pre-signed URLs; access logged.
- **Audit log:** mutations (assets, inference mode, obligation decisions, etc.) write `AuditLog` with actor and project.
- **Reports:** compliance PDF includes an **Exposure and Obligations** section when assessment data exists; user-controlled text is XML-escaped for PDF generation.

---

## Repository layout

```text
lbro/
├── backend/
│   ├── app/
│   │   ├── compliance/          # Knowledge JSON, loader, matching, engine/
│   │   ├── core/                # security, rbac, project_access, exceptions
│   │   ├── middleware/          # rate limiting, security headers
│   │   ├── ml/                  # classifier, features, event_mapper, bundle signing
│   │   ├── migrations/          # Alembic (head: 017_threat_to_obligation on feature branch)
│   │   ├── models/              # SQLAlchemy ORM
│   │   ├── routers/             # FastAPI routes (assets, exposure, knowledge, …)
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── services/            # compliance, notification, exposure, incident, …
│   │   └── workers/             # SQS consumers, ML retry sweep
│   ├── tests/                   # pytest (SQLite default; Postgres migration job in CI)
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── api/client.ts        # Typed API including assets & exposure
│       ├── pages/DataMapPage.tsx
│       └── components/incidents/tabs/ExposureTab.tsx
├── docs/
│   ├── adr/ADR-001-threat-to-obligation.md
│   ├── COMPLIANCE_INFERENCE.md
│   ├── PAPER_NOTES_threat_to_obligation.md
│   └── ML_MODEL_CARD.md
├── scripts/
│   ├── seed.py
│   └── verify_attack_mapping.py
├── terraform/                   # AWS modules (canonical prod path)
├── docker-compose.yml
├── .env.example
├── FEATURE_REPORT.md            # Feature branch deliverable report
└── README.md                      # This file
```

---

## API reference

**Base URL:** `http://localhost:8000/api/v1`  
**Auth:** JWT bearer token from `POST /auth/login` (email and password) for users; `Bearer proj_*` project keys for event ingestion  
**OpenAPI:** `/docs` and `/redoc`

### Auth and users

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Email and password for JWT access and refresh tokens |
| POST | `/auth/register` | Register (when `ALLOW_PUBLIC_REGISTRATION=true`) |
| POST | `/auth/api-key/rotate` | Rotate API key |

### Incidents and events

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/incidents` | List / create |
| GET/PATCH | `/incidents/{id}` | Detail / update (`affected_jurisdictions` = manual override) |
| POST | `/incidents/{id}/status` | State transitions |
| POST | `/events` | Ingest security events (may trigger ML worker) |

### Evidence

| Method | Path | Description |
|--------|------|-------------|
| POST | `/incidents/{id}/evidence` | Upload |
| GET | `/incidents/{id}/evidence` | List |
| GET | `/evidence/{id}/download-url` | Pre-signed URL |
| POST | `/evidence/{id}/verify` | Integrity check |

### Compliance and notifications

| Method | Path | Description |
|--------|------|-------------|
| GET | `/compliance/dashboard` | Scores and deadlines |
| GET | `/notifications` | List drafts |
| POST | `/notifications/{id}/approve` | Approve |
| POST | `/notifications/{id}/dispatch` | Approve and send |

### ML and infrastructure

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ml/stats` | Model stats and distribution |
| GET | `/infrastructure/sqs-history` | Queue depth time series (admin/analyst dashboard) |
| GET | `/health`, `/health/ready` | Liveness / readiness |

### Projects

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/projects` | List / create |
| GET/PATCH | `/projects/{id}/compliance-inference` | Inference mode |

See [Threat-to-obligation inference pipeline](#threat-to-obligation-inference-pipeline) for assets, exposure, and knowledge routes.

---

## Environment variables

Copy [.env.example](.env.example) to `.env`. Critical variables:

| Variable | Purpose |
|----------|---------|
| `ENVIRONMENT` | `development` \| `staging` \| `production` — controls SECRET_KEY and ML signing strictness |
| `SECRET_KEY` | JWT signing; **required** in production (min 32 chars) |
| `DATABASE_URL` | PostgreSQL async URL (`postgresql+asyncpg://…`) |
| `AWS_ENDPOINT_URL` | `http://localhost:4566` for LocalStack |
| `SQS_*_QUEUE_URL` | Incident and notification queues |
| `ML_MODEL_BUNDLE_DIR` | Signed sklearn bundle directory |
| `ML_MODEL_SIGNING_KEY` | HMAC key for bundle manifest (required in production) |
| `ML_REVIEW_THRESHOLD` | Inference + review gating (default 0.75) |
| `ML_AUTO_CONTAIN_ENABLED` | Default **false** — auto-contain only when explicitly enabled and gates pass |
| `GDPR_NOTIFICATION_HOURS` | Legacy notification drafts (default 72) |
| `HIPAA_NOTIFICATION_HOURS` | Legacy (default 1440) |
| `DPDPA_NOTIFICATION_HOURS` | Legacy (default 72) |
| `ALLOW_PUBLIC_REGISTRATION` | Default false in production |
| `DEMO_ENDPOINTS_ENABLED` | Demo routes; off in production |
| `LBRO_SEED_DEMO_ASSETS` | Set `1`/`true` to seed fictional data map in `scripts/seed.py` |
| `VITE_API_URL` | Frontend API base |

Full list with defaults: `backend/app/config.py` and `.env.example`.

---

## Database migrations (Alembic)

```powershell
cd backend
$env:DATABASE_URL = "postgresql+asyncpg://lbro:lbro@localhost:5432/lbro"
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe downgrade -1   # test downgrade on throwaway DB only
```

On branch `feature/threat-to-obligation`, head revision includes data map and exposure tables (**`017_threat_to_obligation`**). CI runs upgrade → downgrade → upgrade against PostgreSQL 16 (service container).

---

## Seed data and demo flags

`scripts/seed.py` creates default users, sample projects, and incidents. It is **idempotent** where possible.

| Flag | Effect |
|------|--------|
| `LBRO_SEED_DEMO_ASSETS=1` | Adds **fictional** assets (e.g. `auth.demo.local`, `cust-db.demo.local`) to project slug `demo-compliance` |

Demo assets label categories and residency counts for inference demos only. **Do not** enable in production unless you explicitly intend to load demo inventory.

---

## Testing and quality gates

| Layer | Command |
|-------|---------|
| Backend | `pytest tests/ -q` (763 passed, 1 skipped in the session 3 run, before the legacy worker tests were removed; 1 integration file deselected on SQLite) |
| Frontend typecheck | `npm run type-check` |
| Frontend unit | `npm run test -- --run` |
| ATT&CK mapping | `python scripts/verify_attack_mapping.py` |
| Compliance coverage | `pytest tests/test_compliance_*.py tests/test_asset_matching.py tests/test_assets_api.py tests/test_exposure_safety.py --cov=app/compliance` |
| Terraform validate | `cd terraform && terraform init -backend=false && terraform validate` |

CI (`.github/workflows/ci.yml`): lint subsets, backend tests, frontend build, optional Postgres migration job.

---

## Documentation index

| Document | Contents |
|----------|----------|
| [docs/COMPLIANCE_INFERENCE.md](docs/COMPLIANCE_INFERENCE.md) | Modes, provisional rules, trace, adding rules |
| [docs/adr/ADR-001-threat-to-obligation.md](docs/adr/ADR-001-threat-to-obligation.md) | Architecture decision, risks, human control |
| [docs/ML_MODEL_CARD.md](docs/ML_MODEL_CARD.md) | ML model card |
| [docs/PAPER_NOTES_threat_to_obligation.md](docs/PAPER_NOTES_threat_to_obligation.md) | Paper-safe claims (no unverified accuracy claims) |
| [FEATURE_REPORT.md](FEATURE_REPORT.md) | Feature branch test counts, inventory, demo transcript |
| [terraform/README.md](terraform/README.md) | AWS topology |

---

## AWS deployment

### Prerequisites

- AWS CLI configured
- Terraform 1.6+
- ECR repositories: `lbro-api`, `lbro-worker`, `lbro-frontend`

### Build and push images

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

docker build -f docker/Dockerfile.api  -t <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-api:latest .
docker build -f docker/Dockerfile.worker -t <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-worker:latest .
docker build -f frontend/Dockerfile      -t <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-frontend:latest frontend/

docker push <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-api:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-worker:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/lbro-frontend:latest
```

### Terraform apply

```bash
cd terraform
terraform init \
  -backend-config="bucket=your-tfstate-bucket" \
  -backend-config="key=lbro/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=lbro-tfstate-lock"

terraform plan \
  -var="environment=staging" \
  -var="api_image=<account>.dkr.ecr.us-east-1.amazonaws.com/lbro-api:latest" \
  -var="worker_image=<account>.dkr.ecr.us-east-1.amazonaws.com/lbro-worker:latest" \
  -var="frontend_image=<account>.dkr.ecr.us-east-1.amazonaws.com/lbro-frontend:latest" \
  -var="app_secret_key=$(openssl rand -hex 32)" \
  -var="alert_email=ops@yourcompany.com"

terraform apply -auto-approve
```

### Run migrations on ECS

```bash
aws ecs run-task \
  --cluster lbro-staging-cluster \
  --task-definition lbro-staging-api \
  --launch-type FARGATE \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
```

Set production secrets (`SECRET_KEY`, `ML_MODEL_SIGNING_KEY`, DB credentials) via Secrets Manager / task definitions — never commit `.env`.

---

## Security notes

- API keys are **bcrypt-hashed** in the database; browser stores keys in memory for the session, not localStorage.
- Access tokens default to **30 minutes**; refresh tokens **7 days** (`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`).
- Account lockout: **5** failed logins → **15** minute cooldown (`MAX_LOGIN_ATTEMPTS`, `LOCKOUT_DURATION_MINUTES`).
- Rate limiting: **60** requests/minute per IP with burst **20** (in-memory sliding window unless Redis is wired).
- Security headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy.
- Evidence immutability: DB flag + S3 Object Lock in production; chain of custody on access.
- **Super admin** bypass of project scope is logged to audit.
- CSV export escapes formula injection characters on asset export.

---

## MITRE ATT&CK attribution

Curated mappings in `attack_to_technique.json` are verified against **MITRE ATT&CK Enterprise** (pinned version in knowledge metadata, e.g. v20.0) via `scripts/verify_attack_mapping.py`. MITRE terms of use apply; attribution appears in docs and on exposure UI surfaces.

---

## Known limitations

- **ML is trained on synthetic data.** Real CICIDS2017 training and evaluation are not done yet.
- **Multi-replica:** the SSE event bus and rate limiter are in-memory and only work correctly on one API replica.
- **MFA** is not implemented. The schema has fields only.
- **Containment** is a placeholder. Real EC2 or SSM isolation is not implemented.

- **`laws.json` rules** ship with `legal_review_status: unreviewed` — counsel must review before reliance.
- **Technique mapping is curated**, not learned from data; do not treat it as ground truth.
- **Legacy vs inference deadlines** — two sources of truth until fully unified (see ADR-001).
- **Accept inferred obligation** updates compliance records; **notification draft creation** from accept is not fully wired — use manual notification workflow as needed.
- **Record counts** across multiple assets report upper/lower bounds with `deduplication_unknown`; never assume exact totals without analyst confirmation.
- **PostgreSQL migration** downgrade/upgrade proof runs in CI; run locally with Docker Postgres 16 if you need on-machine verification.

---

**Questions or contributions:** open an issue or follow internal release process on your fork. For inference changes, always run knowledge validation tests and `verify_attack_mapping.py` before deploy.

---

## License

All rights reserved. See [LICENSE](LICENSE). This is a placeholder until the owner chooses a license.
