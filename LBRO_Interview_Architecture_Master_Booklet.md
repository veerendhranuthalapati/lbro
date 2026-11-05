# LBRO Interview & Architecture Master Booklet

> **Document type:** Engineering / interview preparation — repository-first analysis
> **Source of truth priority:** Implementation > Tests > Config > Infrastructure > Documentation > README
> **Generated from:** Actual LBRO codebase at `c:\Users\veere\Desktop\lbro`
> **Test counts (verified):** Backend 654 pytest tests (37 files); Frontend 50 Vitest tests (5 files)

---

# 1. Executive Summary — What Is LBRO?

LBRO (Legal Breach Response Operations) is a **multi-tenant security incident response platform** built as a full-stack web application. It ingests security events from external applications via project-scoped API keys, classifies them using ML (GaussianNB on CICIDS2017-style features) with a heuristic fallback, auto-creates incidents for high-severity events, preserves evidence with SHA-256 integrity and chain-of-custody, tracks regulatory compliance obligations (GDPR, HIPAA, DPDPA), and provides role-based dashboards for analysts and administrators.

**Problem:** Security teams need a unified workflow from raw security telemetry → classified incident → evidence preservation → regulatory notification deadlines — not just a log viewer.

**Solution:** LBRO connects external apps via SDK/API keys, processes events synchronously in the API (with async SQS workers for incident re-classification and notification dispatch), enforces strict project isolation, and surfaces compliance deadlines derived from real incident metadata.

**Users:** Security analysts, incident responders, compliance officers, project administrators, platform super-admins.

**Source:** `README.md`, `backend/app/main.py`, `backend/app/routers/events.py`

> **DOCUMENTATION/IMPLEMENTATION MISMATCH:** README architecture diagrams show event ingestion via SQS→Worker. **Actual implementation:** events are processed **synchronously** in `backend/app/routers/events.py`. SQS is used for incident ML re-classification and notification sending only.

---

# 2. System Architecture

## 2.1 High-Level Diagram

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                     LBRO PLATFORM                        │
                    │                                                          │
  Browser/User      │   React Frontend (Vite/TS) ──► Nginx ──► FastAPI API    │
       │            │         │ JWT Bearer              │                     │
       └────────────┼─────────┘                         │                     │
                    │                                    ▼                     │
  External App      │                          Auth / RBAC / Project Scope     │
  (SDK/API key)     │                                    │                     │
       │            │                                    ▼                     │
       └────────────┼──► POST /api/v1/events ──► PostgreSQL ◄── Alembic       │
                    │         (sync ML classify)         │                     │
                    │                                    │                     │
                    │   SQS ◄── enqueue ── Worker ──► ML classify / notify    │
                    │   (incidents + notifications)                          │
                    └─────────────────────────────────────────────────────────┘
```

## 2.2 Component Responsibilities

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| Frontend | SPA dashboard, incident/evidence/compliance UI | `frontend/src/` |
| Backend API | REST API, auth, RBAC, event ingestion | `backend/app/main.py`, `routers/` |
| PostgreSQL | All persistent data including evidence bytes | `backend/app/models/`, migrations |
| Worker | SQS poll: incident ML + notification dispatch | `backend/app/workers/main.py` |
| ML Classifier | GaussianNB + heuristic fallback | `backend/app/ml/classifier.py` |
| Terraform | AWS IaC template (ECS/RDS/SQS/S3) | `terraform/main.tf` |
| Docker | Local/prod container orchestration | `docker-compose.yml`, `docker-compose.prod.yml` |

**Source:** `docker-compose.yml`, `backend/app/workers/main.py`, `terraform/main.tf`

---

# 3. Technology Stack — Why Each Choice

| Technology | Purpose | Why Chosen | Alternative | Trade-off |
|------------|---------|------------|-------------|-----------|
| Python 3.11+ | Backend runtime | ML ecosystem, FastAPI async | Node.js, Go | GIL limits CPU-bound ML in async |
| FastAPI | HTTP API | Async, Pydantic validation, OpenAPI | Flask, Django | Less batteries-included than Django |
| React 18 + TS | Frontend SPA | Component model, type safety | Vue, Svelte | Build complexity |
| PostgreSQL 16 | Primary DB | ACID, JSON, BYTEA for evidence | MongoDB | BYTEA evidence is expensive at scale |
| SQLAlchemy 2 + Alembic | ORM + migrations | Type-safe models, versioned schema | raw SQL | ORM learning curve |
| scikit-learn | ML inference | Tabular RF/NB, pickle deploy | PyTorch | Not for unstructured data |
| Docker | Packaging | Reproducible dev/prod | bare metal | Image size overhead |
| AWS SQS | Async job queue | Managed, DLQ support | Kafka, Redis | Not used for raw event ingest |
| Terraform | IaC | Declarative AWS provisioning | CloudFormation | State management complexity |
| pytest / Vitest | Testing | Backend/frontend unit+integration | unittest | — |
| bcrypt (Passlib) | Password hash | Industry standard | argon2 | — |
| HMAC-SHA256 | API key hash | Fast lookup by prefix + verify | bcrypt per key | Requires SECRET_KEY secrecy |
| JWT HS256 | Session tokens | Stateless auth, refresh flow | server sessions | Revocation needs JTI blacklist |

**Source:** `backend/requirements.txt`, `frontend/package.json`, `backend/app/core/security.py`, `backend/app/core/api_keys.py`

---

# 4. Request Lifecycle — Security Event Flow

## 4.1 End-to-End Pipeline

```
External Application
  → SDK or HTTP POST /api/v1/events
  → Bearer proj_<api_key> authentication
  → get_project_from_api_key() resolves project_id (NEVER from body)
  → Pydantic validation (event_type, severity, features)
  → SecurityEvent INSERT (processing_status=pending)
  → _classify_event() — ML or heuristic
  → Auto-incident if severity critical/high
  → processing_status=processed
  → SSE publish to /events/stream subscribers
  → Dashboard reflects new incident/event
```

## 4.2 Stage Details

**Authentication:** `backend/app/dependencies.py::get_project_from_api_key()` — prefix lookup on `projects.api_key_prefix`, HMAC verify via `backend/app/core/api_keys.py::verify_api_key()`.

**Security contract:** `backend/app/routers/events.py` lines 6–8 — project_id from API key only.

**ML classification:** `_classify_event()` calls `LBROClassifier.predict()` if ≥10 non-zero features; else severity→attack mapping table.

**Failure behavior:** Invalid API key → 401; invalid event_type → 422; DB error → 500 with rollback.

**Source:** `backend/app/routers/events.py`, `backend/app/ml/classifier.py`

> **NOTE:** SQS is NOT in the event ingestion path. Worker handles queued incidents (`incident_worker.py`) and notifications (`notification_worker.py`).

---

# 5. User Workflow

```
Register (email/password) → JWT access + refresh tokens
  → Onboarding / Welcome page
  → Create Project → owner becomes implicit admin via ProjectMember backfill
  → Project dashboard → Generate/regenerate API key (one-time reveal)
  → Download SDK stub → Connect external app
  → Events arrive → Incidents created → Evidence uploaded
  → Compliance obligations generated → Reports exported
  → Switch projects via ProjectSwitcher (frontend)
  → Invite members (admin) → Accept invitation → ProjectMember created
```

**Multi-project:** Users can belong to multiple projects via `project_members`. `accessible_project_ids()` in `backend/app/core/project_access.py` returns union of owned + member projects.

**Super Admin:** Platform role `super_admin` bypasses project restrictions (audit-logged). Routes under `/api/v1/platform/`.

**Source:** `frontend/src/routes/AppRouter.tsx`, `backend/app/core/project_access.py`, `backend/app/services/invitation_service.py`, `docs/MULTI_PROJECT.md`

---

# 6. Authentication Deep Dive

## 6.1 Registration & Login

- **Register:** `POST /api/v1/auth/register` — email, username, password. Role defaults to `viewer` (P0 fix: was `admin`). Gated by `ALLOW_PUBLIC_REGISTRATION` (`True` in docker-compose, `False` recommended for prod).
- **Login:** `POST /api/v1/auth/login` — **email + password** (NOT API key exchange despite README claim).
- **Password hashing:** bcrypt via Passlib — `backend/app/core/security.py`
- **Lockout:** 5 failed attempts, 15-minute lock — `MAX_LOGIN_ATTEMPTS`, `LOCKOUT_DURATION_MINUTES` in `config.py`

## 6.2 JWT Structure

**Access token claims:** `sub` (user id), `exp`, `type: "access"`, `jti`, `role`, `email`, `permissions`

**Refresh token claims:** `sub`, `exp`, `type: "refresh"` (no jti)

**Expiry:** Access 30 min (`ACCESS_TOKEN_EXPIRE_MINUTES=30`). README claims 1 hour — **MISMATCH**.

**Algorithm:** HS256 with `SECRET_KEY`

## 6.3 Logout & Revocation

`POST /api/v1/auth/logout` inserts `jti` into `revoked_tokens` table. `get_current_user()` checks blacklist before accepting token.

**Source:** `backend/app/routers/auth.py`, `backend/app/models/revoked_token.py`, `backend/app/services/auth_service.py`, migration `005_revoked_tokens.py`

## 6.4 Frontend Token Storage

Access token in module memory (XSS-resistant vs localStorage). Refresh token in sessionStorage. Axios interceptor refreshes proactively.

**Source:** `frontend/src/store/authStore.ts`

---

# 7. RBAC & Multi-Tenancy (Critical Section)

## 7.1 Two-Level Role Model

**Platform level:** `super_admin` — all permissions + platform permissions

**Project level:** `admin` > `analyst` > `viewer`

**Permissions:** 32 enumerated in `backend/app/core/rbac.py::Permission` — mapped via `ROLE_PERMISSIONS` dict. Never compare role strings directly; use `has_permission()`.

## 7.2 Authorization Decision Flow

```
Request arrives
  → Authenticated? (JWT or X-API-Key)
  → Resource requires project scope?
      → resolve_project_scope() or assert_project_access()
      → Is user owner, ProjectMember, or privileged (platform admin/super_admin)?
      → Does role rank meet required permission?
  → Allow or 403 + audit log
```

## 7.3 Project Isolation Example

**User A:** Owner of Project Alpha; Member (analyst) of Project Beta
**User B:** Owner of Project Gamma only

User A sees incidents/events/evidence for Alpha + Beta only. User B sees Gamma only. Neither can access the other's resources by manipulating UUIDs in URLs — queries JOIN through `project_id` filters.

**IDOR prevention:** `IncidentService._ownership_scope()` includes `ProjectMember` rows. Evidence queries join through `Incident.project_id`. Compliance `mark_met()` requires project ownership check.

**Source:** `backend/app/core/project_access.py`, `backend/app/services/incident_service.py`, `backend/tests/test_project_isolation.py`

## 7.4 API Key Project Resolution

Project API keys (`proj_*`) resolve project at auth time. Submitting a different `project_id` in the body is ignored. This prevents horizontal privilege escalation.

**Source:** `backend/app/dependencies.py::get_project_from_api_key()`, `backend/app/services/project_service.py::resolve_by_api_key()`

---

# 8. Database Deep Dive

## 8.1 ER Diagram (Core Tables)

```
users ──────┬──── owns ──── projects ──── project_members ──── users
            │                    │
            │                    ├── security_events ──► incidents
            │                    │                           │
            │                    │                           ├── evidence ── chain_of_custody
            │                    │                           ├── compliance_records
            │                    │                           ├── notifications
            │                    │                           └── investigation_notes
            │                    │
            │                    ├── compliance_obligations
            │                    └── compliance_assessments
            │
            ├── audit_logs
            └── revoked_tokens (jti blacklist)

project_invitations ──► projects
```

## 8.2 Key Tables

| Table | Purpose | Security Notes |
|-------|---------|----------------|
| `users` | Identity, platform role, legacy user API key hash | Password bcrypt; lockout fields |
| `projects` | Tenant boundary | `api_key_hash` + `api_key_prefix` (HMAC) |
| `project_members` | Multi-user project access | role: admin/analyst/viewer |
| `project_invitations` | Pending invites | token HMAC-hashed, 7-day TTL |
| `security_events` | Raw ingested events | Scoped by project_id |
| `incidents` | Classified security incidents | project_id FK, ML metadata |
| `evidence` | File bytes + metadata | `file_data` BYTEA, `sha256_hash`, immutable |
| `chain_of_custody` | Access audit trail | hash_at_time on each action |
| `compliance_records` | Per-incident regulatory obligations | Derived from incident jurisdictions |
| `revoked_tokens` | JWT JTI blacklist | PK on jti |

**Migrations:** 14 versions, head `014_project_invitations`. Source: `backend/app/migrations/versions/`

## 8.3 Design Decisions

**Why PostgreSQL?** ACID transactions for incident+evidence+compliance consistency; FK constraints enforce referential integrity; BYTEA for evidence (current impl).

**Why project_membership table?** Enables multi-user projects without duplicating project data; supports invitations and role granularity.

**Why hash API keys?** Migration `012_hash_api_keys.py` — DB dump no longer exposes plaintext keys. Lookup: prefix index → HMAC verify loop.

**Why one-time API key reveal?** Key shown only at generation/rotation; only hash stored.

**Source:** `backend/app/models/`, `backend/app/migrations/versions/012_hash_api_keys.py`, `LBRO_Engineering_Audit.md`

---

# 9. API Design — Key Endpoints

| Method | Route | Auth | Purpose |
|--------|-------|------|---------|
| POST | `/auth/register` | Public* | User registration |
| POST | `/auth/login` | Public | Email/password → JWT |
| POST | `/auth/refresh` | Refresh token | New access token |
| POST | `/auth/logout` | JWT | Revoke JTI |
| GET | `/auth/me` | JWT | Current user profile |
| POST | `/events` | Project API key | Ingest security event |
| POST | `/events/batch` | Project API key | Batch ingest (max 100) |
| GET | `/events/stream` | Project API key | SSE live stream |
| GET/POST | `/incidents` | JWT + project scope | List/create incidents |
| POST | `/incidents/{id}/evidence` | JWT + permission | Upload evidence |
| GET | `/evidence/{id}/download` | JWT + project scope | Download file |
| POST | `/evidence/{id}/verify` | JWT | SHA-256 integrity check |
| GET | `/compliance/dashboard` | JWT + project | Compliance metrics |
| POST | `/compliance/obligations` | JWT + admin | Manage obligations |
| GET | `/projects` | JWT | List accessible projects |
| POST | `/projects/{id}/invitations` | JWT + admin | Invite member |
| POST | `/invitations/accept` | JWT | Accept invitation |
| GET | `/dashboard/summary` | JWT + project | Dashboard metrics |
| GET | `/reports/weekly` | JWT + project | Weekly report JSON/PDF |
| GET | `/platform/*` | super_admin | Platform administration |
| GET | `/health` | Public | Health check |

*When `ALLOW_PUBLIC_REGISTRATION=True`

**Source:** `backend/app/main.py` router registration, individual routers in `backend/app/routers/`

---

# 10. Event Ingestion & SDK

## 10.1 External Connection

1. Create project in UI
2. Generate API key (`proj_...`) — shown once
3. Configure SDK or curl with `Authorization: Bearer proj_...`
4. POST JSON event payload to `/api/v1/events`

## 10.2 Security Design

**Project from key, not body:** Prevents attacker from sending events to another tenant's project.

**Rate limiting:** 60 req/min default (`RATE_LIMIT_PER_MINUTE=60`). README says 100 — **MISMATCH**.

## 10.3 SDK Status

**SDK directory:** `sdk/` contains Go and Java **stubs/examples** — minimal reference clients, not a mature published package.

**Source:** `sdk/`, `backend/app/routers/projects.py` (SDK download endpoint)

---

# 11. ML Pipeline

## 11.1 Model Details

**Active version:** `v2.0.0-nb-tuned` (GaussianNB) per `backend/app/ml/models/registry.json`

**Features:** 77 CICIDS2017 network flow features (`backend/app/ml/features.py`). README claims 78 — **MISMATCH**.

**Classes:** 15 attack categories including BENIGN, DDoS, PortScan, Web Attack variants.

**Artifacts:** `cicids2017_classifier.pkl`, `scaler.pkl` — paths configured in `config.py`. **No .pkl files committed to repo** — heuristic fallback active unless deployed with model files.

## 11.2 Inference Flow

```
Features extracted from event payload
  → If ≥10 non-zero features AND model loaded → GaussianNB predict + scaler
  → Else → heuristic rules (pkt_rate, syn_flags, ports) OR severity→attack map
  → confidence compared to ML_CONFIDENCE_THRESHOLD (0.75)
  → needs_review=True if below threshold
```

## 11.3 Why GaussianNB / Random Forest Class?

**Repository evidence:** Registry specifies GaussianNB (Naive Bayes), not Random Forest. README may reference RF from earlier iteration.

**Reasons for tabular classical ML on LBRO:**
- Interpretable feature→class mapping for interviews
- Fast CPU inference, no GPU
- Robust on small tabular datasets (CICIDS2017)
- Simple pickle deployment

**Alternatives considered (engineering rationale):**

| Algorithm | Pros | Cons for LBRO |
|-----------|------|---------------|
| Logistic Regression | Simple, fast | Linear decision boundaries |
| Decision Tree | Interpretable | Overfits |
| Random Forest | Robust ensemble | Heavier than NB |
| XGBoost | High accuracy | Tuning complexity |
| Neural Network | Flexible | Overkill for 77 tabular features; needs GPU at scale |

## 11.4 Fallback When ML Unavailable

`LBROClassifier` returns heuristic classification with `model_version="heuristic-fallback"`, confidence 0.65, `needs_review=True`. System remains operational.

**Worker re-classification:** Incidents enqueued to SQS for async ML re-run via `incident_worker.py`.

**Source:** `backend/app/ml/classifier.py`, `backend/app/workers/incident_worker.py`, `backend/app/config.py`

---

# 12. Evidence Vault

## 12.1 Storage Implementation

**CURRENT IMPLEMENTATION:** Evidence files stored in PostgreSQL `evidence.file_data` (BYTEA, deferred load). Migration `006_evidence_postgres_storage.py`.

**NOT IMPLEMENTED at runtime:** S3 Object Lock / presigned URL download despite README and Terraform S3 bucket definitions.

**Download:** Backend serves `/api/v1/evidence/{id}/download` — `evidence_service.get_download_url()`.

## 12.2 Integrity & Chain of Custody

**SHA-256:** Computed at upload via `compute_sha256()` — stored in `sha256_hash`. Verify endpoint recomputes and compares.

**Chain of custody:** `ChainOfCustody` record on upload, download, and verify — captures `performed_by`, `hash_at_time`, `ip_address`, `action`.

**Immutability:** `is_immutable=True` default; delete blocked for immutable evidence.

**Project isolation:** Evidence queries JOIN through `Incident.project_id` when scoped.

**Source:** `backend/app/services/evidence_service.py`, `backend/app/models/evidence.py`, `backend/app/routers/evidence.py`

---

# 13. Compliance Engine

## 13.1 Implemented Regulations

| Framework | Deadline | Trigger Conditions |
|-----------|----------|-------------------|
| GDPR | 72 hours | Jurisdiction EU/EEA/UK + personal_data_involved |
| HIPAA | 60 days | US jurisdiction OR health_data_involved |
| DPDPA | 72 hours | IN jurisdiction + personal_data_involved |

**Source:** `REGULATION_RULES` in `backend/app/services/compliance_service.py`

## 13.2 Percentage Calculation — No Fabrication

`compliance_percentage(met, total)` in `backend/app/core/metrics.py`:
- Returns `round(met/total*100, 2)` only when `total > 0`
- Returns `None` when no obligations exist (not 100% fake score)

Dashboard aggregates per-regulation and overall from actual `ComplianceRecord.is_met` counts.

## 13.3 Status Scenarios

- **No data:** Percentage `None` or 0 obligations shown
- **Partial:** Real ratio of met/total
- **Overdue:** Deadlines compared to `datetime.now(UTC)` in dashboard queries

**Template vs Implemented:** Obligation *text* is rule-based template; *records* are persisted per incident. Automated regulatory filing is **NOT IMPLEMENTED**.

---

# 14. Evidence + Compliance + ML Relationship

```
Security Event (ingest)
  → ML/heuristic classification
  → Incident (if high/critical severity)
  → Compliance obligations auto-generated from incident jurisdictions + data flags
  → Evidence attached to incident (SHA-256 + custody chain)
  → Notifications created with regulatory deadlines
  → Weekly/compliance PDF reports aggregate project-scoped data
```

This pipeline makes LBRO an **incident response workflow**, not merely a log dashboard.

**Source:** `backend/app/routers/events.py`, `backend/app/services/compliance_service.py`, `backend/app/services/notification_service.py`

---

# 15. Security Architecture

| Threat | Control | Implementation | Test |
|--------|---------|----------------|------|
| Stolen password | bcrypt + lockout | `security.py`, `auth_service.py` | `test_auth.py` |
| Stolen JWT | Short expiry + JTI revoke | `revoked_tokens`, logout | auth tests |
| API key leak | HMAC hash at rest, prefix lookup | `api_keys.py`, migration 012 | `test_api_keys.py` |
| IDOR | project_id scoping on all queries | `project_access.py`, services | `test_project_isolation.py` |
| Privilege escalation | viewer default on register | `auth_service.py` | certification spot-check |
| XSS token theft | Memory-only access token | `authStore.ts` | frontend audit |
| CSRF | JWT in header not cookie | API design | — |
| Rate abuse | SlowAPI 60/min | `main.py` middleware | — |
| Demo abuse | `DEMO_ENDPOINTS_ENABLED` gate | `routers/demo.py` | — |
| Malicious upload | File signature inspection | `evidence_service.py` | evidence tests |
| Host header attack | TrustedHostMiddleware | `main.py`, nginx config | DEPLOYMENT.md |

**MFA:** DB columns exist — **NOT IMPLEMENTED** (no endpoints).

**Source:** `LBRO_PRODUCTION_CERTIFICATION.md`, `LBRO_Engineering_Audit.md`, `backend/tests/`

---

# 16. Security Incidents & Remediation History

All items from audit documents. Issues marked **Previously identified and remediated** where fixed in current code.

| Issue | Danger | Detection | Fix | Status |
|-------|--------|-----------|-----|--------|
| Self-register as admin | Instant privilege escalation | Production audit P0 | Default role `viewer` | REMEDIATED |
| Broken login/refresh/logout | Auth non-functional | P0 audit | Complete rewrite | REMEDIATED |
| Cross-project IDOR on incidents | Data leakage | P1 audit | project_id filters in services | REMEDIATED |
| Evidence IDOR | Download other tenant files | P1 audit | JOIN through incident.project_id | REMEDIATED |
| API keys plaintext in DB | DB dump exposes keys | Engineering audit | HMAC hash migration 012 | REMEDIATED |
| bytes.lower() on evidence | Content inspection broken | P1 audit | Binary-safe comparison | REMEDIATED |
| Reports NameError | Reports crash | P0 audit | project_id param added | REMEDIATED |
| Global dashboard metrics | Cross-tenant stats leak | Security review | Project-scoped queries | REMEDIATED |
| Demo endpoints exposed | Unauthorized seeding | Config review | DEMO_ENDPOINTS_ENABLED gate | REMEDIATED |
| ML scaler not loaded | Wrong predictions | P1 audit | Load scaler.pkl in _load() | REMEDIATED |
| TrustedHost / nginx Host | 400 Invalid host header | EC2 deployment | nginx proxy Host fix | REMEDIATED (local) |

**Lesson:** Always scope queries by `project_id` at the service layer, not just the router.

**Source:** `LBRO_PRODUCTION_CERTIFICATION.md`, `LBRO_Engineering_Audit.md`, `LBRO_v1_Production_Audit_Report.md`, `docs/DEPLOYMENT.md`

---

# 17. DevOps & Docker

## 17.1 Docker Compose Services (Local)

| Service | Image | Role |
|---------|-------|------|
| postgres | postgres:16-alpine | Database |
| localstack | localstack:3.4 | S3/SQS/Secrets emulation |
| migrate | Dockerfile.api | Alembic one-shot |
| api | Dockerfile.api | FastAPI on :8000 |
| worker | Dockerfile.worker | SQS consumer |
| frontend | frontend/Dockerfile | Nginx + React on :3000 |
| seed | Dockerfile.api | Demo data one-shot |

## 17.2 Production

`docker-compose.prod.yml` — EC2 deployment documented in `docs/DEPLOYMENT.md`. Non-root containers, multi-stage builds.

**Why separate worker?** Decouples long-running SQS poll + notification retry from API request threads.

**Source:** `docker-compose.yml`, `docker/Dockerfile.api`, `docker/Dockerfile.worker`

---

# 18. AWS & Terraform

## 18.1 Terraform-Defined Resources (IaC Template)

**Canonical root:** `terraform/main.tf` — modules: networking, sqs, s3, iam, ecs, rds, monitoring

| AWS Service | LBRO Usage |
|-------------|------------|
| ECS Fargate | API, worker, frontend services |
| RDS PostgreSQL | Managed database |
| SQS | Incidents + notifications queues + DLQ |
| S3 | Evidence, reports, ML models buckets (Object Lock in prod module) |
| Secrets Manager | App secrets, DB credentials |
| ALB | Load balancing |
| CloudWatch | Logs + alarms → SNS |
| IAM | Task roles for S3/SQS/Secrets |
| VPC | Network isolation |

**UNVERIFIED as live production:** Terraform defines target architecture; actual deployment may be EC2 + Docker Compose per `docs/DEPLOYMENT.md`.

**Alternate stacks:** `terraform/environments/dev|prod/` include WAF, EventBridge, backup modules not in canonical root.

**Source:** `terraform/`, `docs/DEPLOYMENT.md`

---

# 19. CI/CD

**`.github/workflows/ci.yml`:** On push/PR — ruff lint, pytest with coverage, Docker build, frontend lint/typecheck/build, terraform validate, Trivy filesystem scan, Bandit SAST.

**`.github/workflows/deploy.yml`:** On main/tags — build/push ECR, deploy ECS staging/production.

**Source:** `.github/workflows/`

---

# 20. Engineering Trade-Offs

| Decision | LBRO Choice | Rationale | Cost |
|----------|-------------|-----------|------|
| Event processing | Sync in API | Simpler demo path, immediate incident | API latency under load |
| Evidence storage | PostgreSQL BYTEA | Simplicity, transactional integrity | DB size, backup cost |
| Auth | JWT + refresh | SPA-friendly | Revocation complexity (JTI table) |
| API keys | HMAC not bcrypt | Fast prefix-index lookup | SECRET_KEY compromise = all keys |
| ML | GaussianNB pickle | Lightweight tabular | No online retraining |
| Multi-tenancy | Project table + members | Clear isolation boundary | No org-level hierarchy yet |

---

# 21. Challenges Faced (From Audit History)

1. **Authentication broken at runtime** — truncated methods → full rewrite + 654 tests
2. **Project isolation IDOR** — service-layer project_id JOINs + 11+ isolation tests
3. **API key plaintext** — migration 012 HMAC hashing
4. **Evidence content inspection** — bytes.lower() bug → binary-safe checks
5. **Docker host header on EC2** — nginx Host header + ALLOWED_HOSTS config
6. **ML model not in repo** — heuristic fallback ensures uptime
7. **Compliance report scoping** — all sub-queries through project filter helper

---

# 22. Testing Strategy

**Backend (654 tests, 37 files):** Unit, integration, RBAC, project isolation, invitations, auth, evidence, ML, worker.

**Frontend (50 tests, 5 files):** Component and store tests via Vitest.

**Security-focused tests:** `test_project_isolation.py`, `test_project_invitations.py`, `test_api_keys.py`, `test_auth.py`

**CI:** SQLite in-memory for pytest speed — `backend/tests/conftest.py`

**Historical vs current:** Earlier audits cite ~428 tests; current verified count is **654**.

---

# 23. Performance & Scalability

**Current bottlenecks:**
- Synchronous ML in API event handler (CPU-bound in async loop)
- Evidence BYTEA in PostgreSQL (large file impact)
- Single-worker SQS poll (configurable replica count in ECS module)

**Scale path college → SaaS:**
1. Move event ML to worker queue (already partial for incidents)
2. Evidence → S3 with metadata in PG (Terraform ready, runtime not)
3. Read replicas for dashboard queries
4. Horizontal API scaling behind ALB (ECS module supports)
5. Rate limit tuning per tenant tier

---

# 24. Failure Scenarios

| Failure | Behavior |
|---------|----------|
| PostgreSQL down | API 503, health check fails |
| SQS unavailable | Incident enqueue fails; events still sync-process |
| Worker crash | Messages return to queue after visibility timeout |
| ML model missing | Heuristic fallback, needs_review flagged |
| Invalid API key | 401 Unauthorized |
| Expired JWT | 401, frontend refresh attempt |
| Unauthorized project | 403 Forbidden + audit log |
| Evidence upload fail | 413/400 with validation error |
| AWS unavailable | Local docker still works; prod deploy fails |

---

# 25. Presentation Guide (10–15 min)

| Slide | Show | Say | Key Point |
|-------|------|-----|-----------|
| 1 Problem | Breach timeline graphic | Teams juggle logs, evidence, compliance manually | LBRO unifies the workflow |
| 2 Solution | LBRO dashboard | Multi-tenant incident platform with ML + compliance | Not just a SIEM |
| 3 Architecture | Diagram §2.1 | React→FastAPI→PostgreSQL; SDK→events | Sync ingest, async worker |
| 4 User flow | Register→project→API key | Self-service tenant setup | Project isolation |
| 5 Event ingest | curl/SDK example | API key resolves project, never body | Security by design |
| 6 ML | ML Insights page | GaussianNB + heuristic fallback | Honest about fallback |
| 7 Incidents | Incident detail | Auto-create on high severity | Classification metadata |
| 8 Evidence | Upload + verify | SHA-256 + chain of custody in PostgreSQL | Integrity provable |
| 9 Compliance | Compliance dashboard | GDPR/HIPAA/DPDPA from real incident data | No fake percentages |
| 10 RBAC | Members/roles UI | admin/analyst/viewer + super_admin | IDOR tests prove isolation |
| 11 Deploy | Docker compose / EC2 | Containers + optional AWS Terraform | IaC ready |
| 12 Security | Audit summary | P0/P1 all remediated | 654 tests |
| 13 Demo | Live event → incident | Send event via API key | End-to-end proof |
| 14 Challenges | IDOR, API keys | Service-layer scoping lessons | Real engineering stories |
| 15 Future | S3 evidence, MFA, email | Labeled NOT IMPLEMENTED | Honest roadmap |

---

# 26. Live Demo Script

1. **Register** — "Public registration creates a viewer-role account; production disables this."
2. **Create project** — "Each project is an isolation boundary with its own API key."
3. **Generate API key** — "Shown once; stored as HMAC hash — migration 012 remediated plaintext storage."
4. **Send event** — `curl -H "Authorization: Bearer proj_..." -d '{"event_type":"port_scan","severity":"high",...}'`
5. **Show incident** — "High severity auto-created incident with ML or heuristic classification."
6. **Upload evidence** — "SHA-256 computed; chain of custody entry created."
7. **Compliance** — "Obligations generated from jurisdictions on the incident."
8. **Invite user** — "Admin sends invitation; email match required on accept."
9. **Switch project** — "User A cannot see User B's project data — isolation test proven."

---

# 27. Interview Questions & Answers (50+)

## Architecture

**Q1: What is LBRO?**
- **Short:** Multi-tenant security incident response platform with ML classification, evidence vault, and compliance tracking.
- **Detail:** FastAPI backend, React frontend, PostgreSQL, project-scoped API keys for event ingestion, RBAC with project isolation.
- **Follow-up:** How is it different from a SIEM? — Workflow-focused (incident→evidence→compliance), not log aggregation at scale.
- **Best point:** Project isolation enforced at service layer with dedicated tests.

**Q2: Why FastAPI?**
- **Short:** Async Python, automatic OpenAPI, Pydantic validation.
- **Detail:** Matches ML ecosystem; dependency injection for auth/RBAC clean.
- **Follow-up:** Sync ML in async handler? — Known limitation; worker offload for incidents.
- **Best point:** Type-safe request/response schemas reduce bugs.

**Q3: Why PostgreSQL?**
- **Short:** ACID, relational integrity, BYTEA for current evidence storage.
- **Detail:** FK constraints enforce project→incident→evidence chain; Alembic migrations version schema.
- **Follow-up:** Why not MongoDB? — Compliance and custody need transactional consistency.
- **Best point:** 14 migrations show evolving schema with backward compatibility.

**Q4: Why Docker?**
- **Short:** Reproducible dev/prod parity across api/worker/frontend/postgres.
- **Detail:** Multi-stage Dockerfiles, non-root user, compose orchestration.
- **Best point:** Separate worker container for SQS polling.

**Q5: Why SQS?**
- **Short:** Managed async queue for incident re-classification and notifications.
- **Detail:** DLQ in Terraform module; not used for raw event ingest (sync by design).
- **Follow-up:** Why not Kafka? — Simpler ops for current scale; Terraform template uses SQS.
- **Best point:** Decouples notification retries from API.

## Security & RBAC

**Q6: How does RBAC work?**
- **Short:** Platform super_admin + project admin/analyst/viewer with 32 permissions.
- **Detail:** `ROLE_PERMISSIONS` map in `rbac.py`; `require_permission()` dependency.
- **Best point:** Never compare role strings; use permission checks.

**Q7: How do you prevent IDOR?**
- **Short:** Every query scoped by accessible project_ids from membership + ownership.
- **Detail:** `assert_project_access()`, `_ownership_scope()` JOIN ProjectMember.
- **Best point:** 11+ dedicated isolation tests.

**Q8: Why hash API keys?**
- **Short:** DB compromise doesn't expose usable keys.
- **Detail:** Prefix index + HMAC-SHA256 verify with SECRET_KEY.
- **Best point:** Migration 012 remediated plaintext (audit finding).

**Q9: Why JWT?**
- **Short:** Stateless SPA auth with refresh token rotation.
- **Detail:** JTI blacklist on logout; 30-min access expiry.
- **Best point:** Access token in memory, not localStorage.

**Q10: What happens if someone modifies project_id in request?**
- **Short:** Ignored for event ingest; JWT routes resolve scope server-side.
- **Detail:** Events use API key project resolution only.
- **Best point:** Security contract documented in events.py header.

## Database

**Q11: What tables store evidence?**
- **Short:** `evidence` (file_data BYTEA, sha256_hash) + `chain_of_custody`.
- **Detail:** Legacy s3_key nullable; runtime uses PostgreSQL.
- **Best point:** Verify endpoint recomputes SHA-256.

**Q12: Why project_members instead of user.project_id?**
- **Short:** Multi-user, multi-project membership with per-project roles.
- **Detail:** Supports invitations, role changes, owner + member coexistence.
- **Best point:** Backfill migration 013 for existing owners.

## ML

**Q13: Why GaussianNB?**
- **Short:** Lightweight tabular classifier for CICIDS2017 features.
- **Detail:** registry.json specifies v2.0.0-nb-tuned; pickle deployment.
- **Follow-up:** Why not deep learning? — 77 tabular features; no GPU requirement.
- **Best point:** Heuristic fallback when model file absent.

**Q14: What happens if ML is down?**
- **Short:** Heuristic rules + severity mapping; needs_review=True.
- **Detail:** confidence 0.65, model_version="heuristic-fallback".
- **Best point:** System stays operational — tested path.

**Q15: ML confidence threshold?**
- **Short:** 0.75 in config.py (not 65% as README claims).
- **Detail:** Below threshold flags needs_review on classification result.
- **Best point:** Honest documentation mismatch acknowledgment.

## Cloud & DevOps

**Q16: What AWS services does LBRO use?**
- **Short:** ECS, RDS, SQS, S3, Secrets Manager, CloudWatch (Terraform template).
- **Detail:** Actual prod may be EC2 Docker per DEPLOYMENT.md — UNVERIFIED ECS live.
- **Best point:** IaC ready even if not deployed.

**Q17: How is CI/CD structured?**
- **Short:** GitHub Actions: lint, 654 pytest, Trivy, Bandit, Docker build, terraform validate.
- **Detail:** deploy.yml pushes ECR and updates ECS on main/tags.
- **Best point:** Security scans in CI pipeline.

## System Design

**Q18: How would you scale to millions of events?**
- **Short:** Queue-based ingest, worker pool, evidence to S3, read replicas.
- **Detail:** Current sync API is demo-scale; Terraform ECS autoscaling defined.
- **Best point:** Know current bottleneck (sync ML in API).

**Q19: What is your bottleneck today?**
- **Short:** Synchronous event processing + PostgreSQL evidence bytes.
- **Detail:** ML inference CPU-bound in async event loop.
- **Best point:** Concrete, not hypothetical.

**Q20: How would you improve v3?**
- **Short:** S3 evidence, MFA, email invitations, async event queue, online ML retraining.
- **Detail:** Label each as NOT IMPLEMENTED vs planned.
- **Best point:** Prioritize evidence offload and async ingest.

*(Questions Q21–Q50 below.)*

**Q21: How does chain of custody work technically?**
- **Short:** Every evidence access creates a ChainOfCustody row with action, user, hash_at_time, IP.
- **Detail:** `evidence_service.py` writes custody on upload, download, verify.
- **Best point:** hash_at_time captures integrity snapshot at each access.

**Q22: How are passwords stored?**
- **Short:** bcrypt via Passlib CryptContext.
- **Detail:** Never stored plaintext; lockout after 5 failures.
- **Best point:** P0 audit fixed admin self-registration separately.

**Q23: How do invitations work?**
- **Short:** Admin creates invite with email+role; token hashed; 7-day expiry; accept creates ProjectMember.
- **Detail:** `invitation_tokens.py` HMAC; email must match on accept.
- **Best point:** Email sending NOT IMPLEMENTED unless SMTP configured.

**Q24: What is Super Admin?**
- **Short:** Platform role bypassing project restrictions for platform management.
- **Detail:** Routes under `/platform/`; every bypass audit-logged per rbac.py comments.
- **Best point:** Distinct from project admin.

**Q25: What happens when a user belongs to multiple projects?**
- **Short:** `accessible_project_ids()` returns union; frontend ProjectSwitcher filters UI.
- **Detail:** Each API call passes project_id query param or uses membership scope.
- **Best point:** Isolation tests cover multi-membership.

**Q26: How does the worker differ from the API?**
- **Short:** Worker polls SQS for incident ML re-classification and notification dispatch.
- **Detail:** `workers/main.py` — separate Docker container, no HTTP.
- **Best point:** Decouples retries from user-facing latency.

**Q27: What does the frontend auth interceptor do?**
- **Short:** Attaches Bearer token; refreshes on 401 using sessionStorage refresh token.
- **Detail:** Access token in module memory per authStore.ts security decision.
- **Best point:** XSS-resistant token storage trade-off.

**Q28: How are batch events handled?**
- **Short:** POST /events/batch accepts up to 100 events per request.
- **Detail:** Same auth and project resolution as single event.
- **Best point:** Each event processed through same pipeline.

**Q29: What is SSE /events/stream?**
- **Short:** Server-Sent Events for live event feed per project API key.
- **Detail:** In-process bus publish after event processed.
- **Best point:** Real-time dashboard updates without polling.

**Q30: How does notification retry work?**
- **Short:** Worker retries up to 3 times via SQS; retry_count on notification model.
- **Detail:** `notification_worker.py` handles approved notifications.
- **Best point:** Email transport requires SMTP — otherwise logged only.

**Q31: How are weekly reports generated?**
- **Short:** Aggregates project-scoped incidents, compliance, evidence counts.
- **Detail:** JSON and PDF variants; project_id param required (P0 fix).
- **Best point:** All sub-queries use project filter helper.

**Q32: What is the demo endpoint?**
- **Short:** POST /demo/generate seeds sample data when DEMO_ENDPOINTS_ENABLED=True.
- **Detail:** Gated in production; fixed confidence_score field name bug.
- **Best point:** Must be disabled in production deployments.

**Q33: Why Alembic migrations?**
- **Short:** Versioned, reversible schema changes across 14 migrations.
- **Detail:** docker-compose migrate service runs upgrade head on startup.
- **Best point:** 012_hash_api_keys shows security-driven migration.

**Q34: How does SQLAlchemy async work here?**
- **Short:** AsyncSession with asyncpg driver for non-blocking DB I/O.
- **Detail:** FastAPI Depends(get_db) yields session per request.
- **Best point:** Sync ML in async handler is the exception, not the rule.

**Q35: How does frontend enforce permissions?**
- **Short:** ProtectedRoute + permission checks on admin pages.
- **Detail:** Permissions from JWT claims; RoleBadge component shows role.
- **Best point:** Backend always re-validates — frontend is UX only.

**Q36: How is API key rotation implemented?**
- **Short:** POST regenerate-key generates new proj_* key; old hash replaced.
- **Detail:** One-time reveal in response; only hash persisted.
- **Best point:** ROTATE_API_KEYS permission required.

**Q37: What are legacy user API keys (lbro_*)?**
- **Short:** Per-user keys on users table; X-API-Key header auth alternative to JWT.
- **Detail:** Also HMAC-hashed after migration 012.
- **Best point:** Project keys preferred for event ingest.

**Q38: How are investigation notes scoped?**
- **Short:** Notes belong to incident; incident belongs to project.
- **Detail:** Author ownership check added after note IDOR finding.
- **Best point:** Migration 011 added notes table.

**Q39: What is audit logging?**
- **Short:** audit_logs table captures user actions with resource_type, path, details.
- **Detail:** project_id column added migration 010; Super Admin bypass logged.
- **Best point:** Compliance and forensics support.

**Q40: Is there a readiness probe?**
- **Short:** Only GET /health exists — NOT /health/ready.
- **Detail:** README and comments reference readiness — DOCUMENTATION MISMATCH.
- **Best point:** Health returns simple status from main.py.

**Q41: What is LocalStack used for?**
- **Short:** Emulates S3, SQS, Secrets Manager in local docker-compose.
- **Detail:** scripts/localstack-init.sh creates queues/buckets.
- **Best point:** Dev parity without AWS credentials.

**Q42: How does Terraform state work?**
- **Short:** UNVERIFIED remote state config — local terraform/ directory is template.
- **Detail:** ci.yml runs terraform validate only.
- **Best point:** IaC exists; live state not in repo.

**Q43: Can evidence be deleted?**
- **Short:** Only if is_immutable=False; default is immutable.
- **Detail:** DELETE requires evidence:delete permission + project scope.
- **Best point:** Immutability supports forensic integrity story.

**Q44: How is file upload validated?**
- **Short:** Size limits, content inspection with binary-safe signature checks.
- **Detail:** Fixed bytes.lower() bug — now byte comparison.
- **Best point:** P1 audit remediation.

**Q45: What password rules apply?**
- **Short:** Pydantic validators on RegisterRequest — minimum length, complexity.
- **Detail:** Server-side enforcement; not just frontend.
- **Best point:** Input validation domain score 9/10 in certification.

**Q46: How does rate limiting work?**
- **Short:** SlowAPI middleware — 60 requests/minute per IP default.
- **Detail:** Configurable via RATE_LIMIT_PER_MINUTE.
- **Best point:** README claims 100 — cite config.py instead.

**Q47: How is CORS configured?**
- **Short:** CORSMiddleware with CORS_ORIGINS from environment.
- **Detail:** Must match frontend domain in production.
- **Best point:** EC2 deployment sets CORS_ORIGINS to public IP.

**Q48: What was the hardest bug?**
- **Short:** P0 auth handler truncation — login/refresh/logout broken at runtime.
- **Detail:** Complete rewrite of auth_service.py and auth router.
- **Best point:** Shows value of integration tests over import-only checks.

**Q49: How would an attacker access another project?**
- **Short:** Attempt IDOR via incident/evidence UUID — blocked by project_id JOIN.
- **Detail:** test_project_isolation.py simulates cross-tenant access.
- **Best point:** Service-layer enforcement, not router-only checks.

**Q50: How do you prove isolation works?**
- **Short:** Run pytest test_project_isolation.py and test_project_invitations.py.
- **Detail:** 654 total tests; CI runs on every push.
- **Best point:** Offer to walk through assert_project_access() code.

---

# 28. Hard Interview Questions — Design Challenges

**Q: Isn't this just a SIEM?**
A: LBRO focuses on incident response workflow (classify→incident→evidence→compliance deadline), not petabyte log storage or correlation rules at scale. It complements SIEM, not replaces Splunk/Elastic.

**Q: Why not Kafka instead of SQS?**
A: Current scale and team ops favor managed SQS with DLQ. Kafka adds operational burden without current throughput need. Terraform could swap queue layer.

**Q: Why PostgreSQL for evidence?**
A: Current implementation prioritizes simplicity and transactional integrity. README/Terraform mention S3 — runtime uses BYTEA. We'd migrate evidence to S3 before enterprise scale.

**Q: Isn't storing files in PostgreSQL expensive?**
A: Yes at scale — acknowledged trade-off. BYTEA deferred loading mitigates read cost; S3 is documented future path.

**Q: Why not deep learning?**
A: 77 numeric tabular features from CICIDS2017; GaussianNB/RF sufficient, interpretable, CPU-only. No labeled dataset at production volumes for neural net advantage.

**Q: How do you prevent API key theft?**
A: HTTPS, hashed at rest, prefix-only index, rate limiting, project-scoped permissions. Leaked key only accesses one project — rotate via regenerate-key.

**Q: Can a user access another project?**
A: Not if authorization helpers applied — proven by isolation tests. Privileged platform admin is intentional bypass, audit-logged.

**Q: What happens if ML is down?**
A: Heuristic fallback — events still ingest, incidents still create, flagged needs_review.

**Q: How do you know compliance percentages are real?**
A: `compliance_percentage()` returns None when zero obligations; otherwise met/total from persisted records only.

**Q: What would you change before enterprise deployment?**
A: S3 evidence, MFA, email notifications, async event queue, secrets rotation, ECS/Fargate prod, WAF, penetration re-test, remove demo endpoints.

---

# 29. Elevator Pitches

## 30 Seconds
"LBRO is a multi-tenant security incident response platform. External apps send security events via project API keys; we classify them with ML, auto-create incidents, preserve evidence with SHA-256 chain of custody, and track GDPR, HIPAA, and DPDPA compliance deadlines — all with strict project isolation and role-based access."

## 1 Minute
"LBRO solves the gap between detecting a security event and meeting regulatory breach notification requirements. Built with FastAPI and React, it lets teams create isolated projects, connect applications through API keys, and ingest events that are classified by a GaussianNB model — with a heuristic fallback if the model isn't deployed. High-severity events become incidents automatically. Analysts upload evidence stored with integrity hashes and chain of custody, while the compliance engine generates real obligations from incident metadata. RBAC enforces admin, analyst, and viewer roles per project, and our test suite includes dedicated IDOR prevention tests. We remediated all P0/P1 security findings from our production audit, including API key hashing and cross-project access bugs."

## 3 Minutes
*(Expand 1-minute version with architecture diagram walkthrough, sync vs async paths, PostgreSQL evidence honesty, Terraform AWS template vs EC2 deployment reality, 654 backend tests, invitation system, Super Admin platform layer, and v3 roadmap: S3 evidence, MFA, async ingest.)*

---

# 30. Personal Contribution

**UNVERIFIED from repository authorship alone.**

Use this template in interviews:
- "I contributed to [specific module] — e.g., project invitations in `invitation_service.py` / frontend members UI."
- "I fixed [specific bug] — e.g., nginx Host header for EC2 deployment per DEPLOYMENT.md."
- "I wrote tests in [test file] — e.g., `test_project_invitations.py` (8 tests)."
- "My focus area was [backend/frontend/DevOps/ML/security audit remediation]."

Fill in only what you actually implemented.

---

# 31. Glossary

| Term | Definition |
|------|------------|
| RBAC | Role-Based Access Control — permissions mapped to roles |
| IDOR | Insecure Direct Object Reference — accessing resources by guessing IDs |
| JWT | JSON Web Token — signed claims for stateless auth |
| JTI | JWT ID — unique token identifier for revocation |
| HMAC | Hash-based Message Authentication Code — API key storage |
| SHA-256 | Cryptographic hash for evidence integrity |
| SQS | AWS Simple Queue Service — async job queue |
| RDS | AWS Relational Database Service — managed PostgreSQL |
| ECS/Fargate | AWS container orchestration — serverless containers |
| ORM | Object-Relational Mapping — SQLAlchemy models |
| Alembic | Database migration tool for SQLAlchemy |
| Multi-tenancy | Multiple isolated customers/projects on one deployment |
| Chain of custody | Audit trail of evidence access and integrity snapshots |
| SIEM | Security Information and Event Management — log aggregation |
| IOC | Indicator of Compromise — forensic artifact |
| BYTEA | PostgreSQL binary column type — current evidence storage |

---

# 32. Final Cheat Sheet

## Architecture in One Line
React SPA + FastAPI + PostgreSQL + optional SQS worker + ML classifier (GaussianNB/heuristic).

## Tech Stack
Python, FastAPI, React, TypeScript, PostgreSQL, SQLAlchemy, Alembic, Docker, AWS (Terraform template), scikit-learn, pytest, Vitest.

## Security Essentials
- bcrypt passwords
- JWT + JTI revoke
- HMAC API keys (proj_*)
- project_id from key not body
- RBAC 32 permissions
- IDOR tests pass

## ML Essentials
- 77 features, 15 classes
- v2.0.0-nb-tuned GaussianNB
- Threshold 0.75
- Heuristic fallback if no pickle

## Evidence
- PostgreSQL file_data (NOT S3 runtime)
- SHA-256 + chain_of_custody
- Immutable default

## Compliance
- GDPR 72h, HIPAA 60d, DPDPA 72h
- Real met/total percentages only

## Key APIs
POST /events (API key), POST /auth/login (JWT), GET /projects, POST /projects/{id}/invitations

## Test Counts
654 backend, 50 frontend (current verified)

## Major Problems Solved
Admin self-registration, IDOR, plaintext API keys, broken auth handlers, evidence inspection bug

## Documentation Mismatches to Mention Proactively
README: S3 evidence, API-key login, 78 features, 65% threshold, SQS event ingest — all differ from code

## NOT IMPLEMENTED
MFA endpoints, email invitation sending (unless SMTP configured), S3 evidence at runtime, live ML retraining

## 10 Things You Must Remember
1. LBRO = incident response workflow, not SIEM
2. Events processed synchronously in API
3. project_id from API key ONLY for ingest
4. Evidence in PostgreSQL BYTEA today
5. ML fallback always available
6. 654 tests including IDOR suite
7. API keys HMAC-hashed (migration 012)
8. Compliance % from real records only
9. super_admin bypasses project scope (audited)
10. README ≠ implementation — cite code first

---

# 33. Source Reference Index

| Topic | Primary Source |
|-------|----------------|
| Event ingestion | `backend/app/routers/events.py` |
| Project access | `backend/app/core/project_access.py` |
| RBAC | `backend/app/core/rbac.py` |
| API keys | `backend/app/core/api_keys.py` |
| Auth | `backend/app/services/auth_service.py` |
| Evidence | `backend/app/services/evidence_service.py` |
| Compliance | `backend/app/services/compliance_service.py` |
| ML | `backend/app/ml/classifier.py` |
| Worker | `backend/app/workers/main.py` |
| Models | `backend/app/models/` |
| Migrations | `backend/app/migrations/versions/` |
| Frontend routes | `frontend/src/routes/AppRouter.tsx` |
| Docker | `docker-compose.yml`, `docker-compose.prod.yml` |
| Terraform | `terraform/main.tf` |
| CI | `.github/workflows/ci.yml` |
| Deployment | `docs/DEPLOYMENT.md` |
| Multi-project | `docs/MULTI_PROJECT.md` |
| Audits | `LBRO_PRODUCTION_CERTIFICATION.md`, `LBRO_Engineering_Audit.md` |

---

# 34. Appendix A — Complete Migration History

| Rev | File | What Changed |
|-----|------|--------------|
| 001 | 001_initial_schema.py | users, incidents, evidence, notifications base schema |
| 002 | 002_rbac_roles.py | Expanded role enum |
| 003 | 003_simplify_roles.py | admin/analyst/viewer simplification |
| 004 | 004_sanitize_legacy_roles.py | Data cleanup for role migration |
| 005 | 005_revoked_tokens.py | JWT JTI blacklist table |
| 006 | 006_evidence_postgres_storage.py | evidence.file_data BYTEA column |
| 007 | 007_projects.py | projects table, project_id on incidents |
| 008 | 008_compliance_persistence.py | compliance_obligations, compliance_assessments |
| 009 | 009_add_missing_indexes.py | Performance indexes on FKs |
| 010 | 010_platform_layer.py | project_members, security_events, super_admin |
| 011 | 011_investigation_notes.py | investigation_notes table |
| 012 | 012_hash_api_keys.py | HMAC hash for API keys at rest |
| 013 | 013_backfill_project_members.py | Owner membership backfill |
| 014 | 014_project_invitations.py | project_invitations table |

**Source:** `backend/app/migrations/versions/`

---

# 35. Appendix B — Frontend Pages & Routes

| Route | Page Component | Purpose |
|-------|----------------|---------|
| /login | LoginPage | Email/password authentication |
| /register | RegisterPage | User registration |
| /dashboard | DashboardPage | Project-scoped metrics summary |
| /incidents | IncidentsPage | Incident list and filters |
| /incidents/:id | IncidentDetailPage | Single incident with timeline, notes |
| /incidents/new | CreateIncidentPage | Manual incident creation |
| /evidence | EvidencePage | Evidence list across incidents |
| /compliance | CompliancePage | Compliance dashboard |
| /compliance/audit | ComplianceAuditPage | Obligation audit view |
| /projects | ProjectsPage | Project list and creation |
| /projects/:id | ProjectOverviewPage | Single project dashboard |
| /projects/:id/settings | ProjectSettingsPage | Members, invitations, API key |
| /projects/:id/integrations | IntegrationsPage | SDK download, connection guide |
| /projects/:id/events | LiveEventsPage | Live event stream view |
| /ml | MLInsightsPage | ML model stats and classifications |
| /notifications | NotificationsPage | Regulatory notification management |
| /users | UsersPage | User management (admin) |
| /audit | AuditLogsPage | Audit trail viewer |
| /platform | PlatformDashboard | Super Admin platform view |

**Source:** `frontend/src/routes/AppRouter.tsx`

---

# 36. Appendix C — Sample Event Ingest Request

```
POST /api/v1/events HTTP/1.1
Host: api.example.com
Authorization: Bearer proj_<your_project_api_key>
Content-Type: application/json

{
  "event_type": "port_scan",
  "severity": "high",
  "source_ip": "203.0.113.50",
  "destination_ip": "10.0.0.5",
  "destination_port": 22,
  "description": "Multiple SYN packets detected",
  "metadata": {
    "pkt_rate": 8500,
    "syn_flags": 420
  }
}
```

**Response (201):** SecurityEvent JSON with id, processing_status=processed, ml_attack_category, incident_id if auto-created.

**Source:** `backend/app/routers/events.py`, `SecurityEventCreate` schema

---

# 37. Appendix D — RBAC Permission Matrix (Summary)

| Permission | Viewer | Analyst | Admin | Super Admin |
|------------|--------|---------|-------|-------------|
| incident:read | Yes | Yes | Yes | Yes |
| incident:create | No | Yes | Yes | Yes |
| incident:update | No | Yes | Yes | Yes |
| evidence:upload | No | Yes | Yes | Yes |
| evidence:download | Yes | Yes | Yes | Yes |
| report:generate | No | No | Yes | Yes |
| user:manage | No | No | Yes | Yes |
| apikey:rotate | No | No | Yes | Yes |
| platform:* | No | No | No | Yes |

**Source:** `backend/app/core/rbac.py::ROLE_PERMISSIONS`

---

# 38. Appendix E — Documentation vs Implementation Conflicts (Complete List)

| Topic | README/Doc Claim | Actual Implementation | Label |
|-------|------------------|----------------------|-------|
| Login method | API key exchange | Email/password JWT | MISMATCH |
| API key hash | bcrypt | HMAC-SHA256 | MISMATCH |
| JWT expiry | 1 hour | 30 minutes | MISMATCH |
| Rate limit | 100/min | 60/min | MISMATCH |
| Evidence storage | S3 Object Lock | PostgreSQL BYTEA | MISMATCH |
| ML features | 78 | 77 | MISMATCH |
| ML threshold | 65% | 75% (0.75) | MISMATCH |
| Event pipeline | SQS async | Sync in API | MISMATCH |
| Readiness probe | /health/ready | /health only | MISMATCH |
| Frontend auth | X-API-Key | Bearer JWT | MISMATCH |
| MFA | Mentioned | DB columns only, no endpoints | NOT IMPLEMENTED |
| Email invitations | Implied | SMTP required, else no send | NOT IMPLEMENTED |
| ECS production | Architecture diagram | EC2 Docker documented | UNVERIFIED |
| ML model in repo | Implied trained model | registry.json only, no .pkl | UNVERIFIED deploy |

**Interview tip:** Proactively cite these — demonstrates codebase-first honesty.

---

# 39. Appendix F — Red-Team Test Scenarios

1. **Cross-project incident read:** User A requests User B incident UUID → expect 403/404
2. **Evidence download IDOR:** Manipulate evidence ID from another project → blocked by JOIN
3. **project_id in event body:** Send different project_id → ignored; key determines project
4. **Self-register as admin:** Fixed — always viewer role
5. **Expired JWT:** 401 after expiry; refresh if valid refresh token
6. **Revoked JWT after logout:** JTI in revoked_tokens → 401
7. **Demo endpoint in prod:** DEMO_ENDPOINTS_ENABLED=False → 404
8. **Compliance mark_met cross-project:** Requires project ownership → 403
9. **Global dashboard without project scope:** Fixed — project_id required
10. **API key prefix brute force:** Prefix index only narrows candidates; HMAC verify required

**Source:** `backend/tests/test_project_isolation.py`, `LBRO_PRODUCTION_CERTIFICATION.md`

---

*End of LBRO Interview & Architecture Master Booklet*
