# LBRO — Law-aware Breach Response Orchestrator
## Complete Technical Documentation

> **Version:** 2.0.0 · **Last Updated:** July 2026 · **Audience:** Senior Engineers, New Team Members

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [Architecture Overview](#2-architecture-overview)
3. [Folder Structure](#3-folder-structure)
4. [Backend Deep Dive](#4-backend-deep-dive)
5. [Frontend Deep Dive](#5-frontend-deep-dive)
6. [Database Schema](#6-database-schema)
7. [ML Pipeline](#7-ml-pipeline)
8. [Compliance Engine](#8-compliance-engine)
9. [Security Model](#9-security-model)
10. [Deployment](#10-deployment)
11. [API Reference](#11-api-reference)
12. [Frontend ↔ Backend Flows](#12-frontend--backend-flows)
13. [Current Features](#13-current-features)
14. [Future Roadmap](#14-future-roadmap)
15. [Interview Guide](#15-interview-guide)
16. [Known Technical Debt](#16-known-technical-debt)
17. [Developer Handoff](#17-developer-handoff)

---

## 1. Project Vision

### What is LBRO?

LBRO — **Law-aware Breach Response Orchestrator** — is a full-stack security incident management platform built for development teams, startups, and small-to-mid-sized engineering organizations. It detects, classifies, triages, and manages cybersecurity incidents end-to-end, with built-in compliance automation for GDPR, HIPAA, and India's DPDPA.

The name is intentional: it is not just an incident tracker. The *law-aware* component means that when a breach is detected, LBRO automatically calculates which regulations apply, what the legal notification deadlines are, and drafts the regulatory authority notifications — removing the scramble that teams face during a real breach.

### Why It Exists

When a data breach or cyberattack occurs in a small-to-mid organization, teams face a cascading problem:

1. **Detection is manual** — engineers piece together logs, alerts, and SIEMs to understand what happened.
2. **Triage is slow** — without ML-assisted classification, every incident gets the same attention regardless of actual risk.
3. **Compliance is terrifying** — most teams do not know their GDPR 72-hour window is already running the moment they first detect the breach.
4. **Evidence management is ad-hoc** — screenshots in Slack threads, logs emailed around, no chain of custody.
5. **Reporting is an afterthought** — generating a weekly security posture report takes hours of manual work.

LBRO solves all five problems in a single integrated platform.

### Target Audience

LBRO is built for:

- **Engineering teams** (5–200 people) that handle their own security operations but do not have a dedicated CISO or SOC.
- **Startups that handle personal data** and need to demonstrate compliance to enterprise customers, investors, or regulators.
- **Security analysts** who want ML-assisted triage rather than raw log volumes.
- **CTOs and engineering managers** who need a weekly security posture report they can actually read and share with the board.

### Why It Is Different From Enterprise SIEMs

Enterprise SIEMs like Splunk, IBM QRadar, and Microsoft Sentinel are built for security operations centers that have dedicated analysts staring at dashboards all day. They cost $100K+/year, require weeks of configuration, and generate more noise than signal.

LBRO is explicitly developer-first:

| Dimension | Enterprise SIEM | LBRO |
|---|---|---|
| Setup time | Weeks to months | Minutes (Docker Compose) |
| Price | $100K–$1M/year | Open source |
| Target user | SOC analyst | Developer / engineering lead |
| ML approach | Rule-based SIEM correlation | CICIDS2017 Random Forest classifier |
| Compliance | Add-on module, extra cost | Built-in, automatic |
| Reports | Complex configuration | Single click, PDF download |
| API-first | No | Yes — everything is an API |

### The New Product Vision: Developer-First Security Companion

The V2 vision positions LBRO as a **post-deployment security companion** — something developers install alongside their production stack the same way they install Prometheus or Datadog. It:

- Runs as a sidecar or microservice alongside any application.
- Receives security events (failed logins, port scans, anomalous traffic) via API.
- Classifies threats using the embedded ML model, no cloud dependency required.
- Automatically starts a compliance clock the moment personal data exposure is detected.
- Sends a structured weekly report to your inbox with an A–F security grade.
- Provides a plain-English "explain this incident" for engineers who are not security experts.

### The Business Problem

The business problem is regulatory risk at small scale. Post-GDPR and post-DPDPA, even a ten-person startup can face a €20M fine or 4% of global turnover for failing to notify the right authority within 72 hours of a breach. Most small engineering teams have no documented process, no evidence chain, and no idea which authority to notify. LBRO addresses this directly by automating the legal lookup, deadline calculation, and notification drafting — so engineers can focus on containment while LBRO handles the compliance machinery in the background.

---

## 2. Architecture Overview

### System Components

LBRO is composed of six runtime components:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LBRO System                                 │
│                                                                     │
│  ┌─────────────┐     ┌──────────────────────────────────────────┐  │
│  │   Frontend  │────▶│                API Server                │  │
│  │  React/Vite │     │          FastAPI + SQLAlchemy             │  │
│  │  Port 3000  │◀────│              Port 8000                   │  │
│  └─────────────┘     └────────────────────┬─────────────────────┘  │
│                                           │                         │
│                           ┌──────────────▼──────────────┐          │
│                           │         PostgreSQL           │          │
│                           │       Port 5432             │          │
│                           └──────────────┬──────────────┘          │
│                                          │                          │
│  ┌─────────────┐     ┌──────────────────▼──────────────────────┐  │
│  │  LocalStack │◀────│           Background Worker             │  │
│  │  S3 + SQS   │     │    SQS consumer: incidents + notifs     │  │
│  │  Port 4566  │────▶└─────────────────────────────────────────┘  │
│  └─────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown

**Frontend (React + Vite)**
The user interface is a React 18 single-page application built with Vite. It communicates with the backend exclusively via a typed Axios client. In development with mocked data, it uses Mock Service Worker (MSW) to intercept API calls and return realistic responses without requiring a running backend.

**API Server (FastAPI)**
The main application server. It handles all HTTP requests, enforces authentication and RBAC, coordinates service logic, runs the ML classifier on-demand, generates PDF reports, and manages the database. Built with Python 3.12 and FastAPI, using async SQLAlchemy for non-blocking database access.

**Background Worker**
A separate Python process that polls SQS queues for:
- Incident processing jobs (ML classification, containment actions)
- Regulatory notification dispatch jobs (sending emails to DPAs)

The worker uses the same codebase as the API server but runs without HTTP — it is a long-running `asyncio` loop consuming queue messages.

**PostgreSQL 16**
The primary data store. All application state lives here: incidents, users, evidence files (as binary blobs), compliance records, audit logs, notifications. Evidence is stored directly in PostgreSQL as `LargeBinary` rather than requiring S3 — this simplifies the local development path and removes the S3 dependency for core functionality.

**LocalStack**
A local AWS services emulator that runs S3 and SQS in a Docker container. This allows the application to use the same AWS SDK calls in local development as it would in production, without needing real AWS credentials.

**AWS (Production)**
In production, the stack runs on AWS ECS Fargate (serverless containers), with RDS PostgreSQL, S3 for evidence and reports, SQS for async processing, Secrets Manager for credentials, and CloudWatch for monitoring. The full infrastructure is codified in Terraform.

### Architecture Diagram (Production)

```
                        ┌─────────────────┐
                        │   CloudFront    │
                        │    (CDN/WAF)    │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   ALB (HTTPS)   │
                        │  Load Balancer  │
                        └──┬──────────┬───┘
                           │          │
               ┌───────────▼──┐   ┌───▼──────────┐
               │  ECS Fargate │   │  ECS Fargate  │
               │   API Tasks  │   │  Worker Tasks │
               │  (2+ replicas│   │  (1+ replicas)│
               └──────┬───────┘   └───────┬───────┘
                      │                   │
         ┌────────────┼───────────────────┤
         │            │                   │
    ┌────▼────┐  ┌────▼────┐  ┌──────────▼──────────┐
    │  RDS    │  │   SQS   │  │         S3          │
    │Postgres │  │ Queues  │  │  Evidence + Reports  │
    │ (Multi- │  │         │  │                      │
    │   AZ)   │  └─────────┘  └──────────────────────┘
    └─────────┘
```

### Technology Stack Summary

| Layer | Technology | Version | Why |
|---|---|---|---|
| Frontend framework | React | 18 | Industry standard, large ecosystem |
| Frontend build | Vite | 5 | Fast HMR, native ESM, small bundles |
| Frontend state | Zustand | 4 | Minimal boilerplate, no Redux complexity |
| HTTP client | Axios | 1.x | Interceptor support for auth + retry |
| API framework | FastAPI | 0.110+ | Async, automatic OpenAPI, Python typing |
| ORM | SQLAlchemy | 2.x async | Type-safe, async-native, migration support |
| Migrations | Alembic | 1.x | Version-controlled schema migrations |
| Auth | python-jose + passlib | - | JWT (HS256) + bcrypt password hashing |
| ML | scikit-learn | 1.x | Industry standard classifier, CICIDS2017 |
| PDF generation | ReportLab | 4.x | Programmatic PDF, no headless browser needed |
| Database | PostgreSQL | 16 | ACID, JSONB, large binary storage |
| Container | Docker + Compose | - | Reproducible environments |
| Infrastructure | Terraform | 1.6+ | Infrastructure as code, AWS provider |
| Cloud | AWS (ECS, RDS, S3, SQS) | - | Managed services, global availability |
| Logging | structlog | - | Structured JSON logs, request tracing |
| Testing | pytest + pytest-asyncio | - | Async test support |
| CI/CD | GitHub Actions | - | Native to GitHub, free for open source |

---

## 3. Folder Structure

```
lbro/                              ← Repository root
├── .github/
│   └── workflows/
│       ├── ci.yml                 ← CI pipeline (lint, test, build, security scan)
│       └── deploy.yml             ← CD pipeline (push to ECR, deploy to ECS)
├── backend/
│   ├── app/
│   │   ├── main.py                ← FastAPI app entry point; middleware, routers
│   │   ├── config.py              ← Pydantic settings (reads .env)
│   │   ├── database.py            ← Async SQLAlchemy engine + session factory
│   │   ├── dependencies.py        ← FastAPI dependency injectors (auth, RBAC)
│   │   ├── core/
│   │   │   ├── rbac.py            ← Role enum, Permission enum, ROLE_PERMISSIONS map
│   │   │   ├── security.py        ← JWT creation/decode, bcrypt hashing
│   │   │   ├── exceptions.py      ← Custom exception classes + handlers
│   │   │   ├── middleware.py      ← (legacy shim)
│   │   │   ├── rate_limit.py      ← (legacy shim)
│   │   │   ├── logging.py         ← (legacy shim — config moved to main.py)
│   │   │   └── aws_clients.py     ← Boto3 client factories (S3, SQS, Secrets Manager)
│   │   ├── middleware/
│   │   │   ├── rate_limit.py      ← Sliding-window rate limiter (per-IP, per-path)
│   │   │   └── security_headers.py← HTTP security headers (CSP, HSTS, X-Frame-Options)
│   │   ├── models/                ← SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── incident.py        ← Incident + IncidentAction
│   │   │   ├── evidence.py        ← Evidence + ChainOfCustody
│   │   │   ├── compliance.py      ← ComplianceRecord
│   │   │   ├── notification.py    ← Notification + NotificationRecipient
│   │   │   ├── audit.py           ← AuditLog
│   │   │   └── revoked_token.py   ← RevokedToken (JWT revocation table)
│   │   ├── schemas/               ← Pydantic request/response schemas
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── incident.py
│   │   │   ├── evidence.py
│   │   │   ├── compliance.py
│   │   │   └── notification.py
│   │   ├── routers/               ← FastAPI route handlers
│   │   │   ├── auth.py
│   │   │   ├── users.py
│   │   │   ├── incidents.py
│   │   │   ├── evidence.py
│   │   │   ├── compliance.py
│   │   │   ├── notifications.py
│   │   │   ├── reports.py         ← Weekly report + Compliance audit PDF
│   │   │   ├── dashboard.py
│   │   │   ├── audit.py
│   │   │   ├── ml.py
│   │   │   ├── infrastructure.py
│   │   │   ├── security_score.py
│   │   │   └── users.py
│   │   ├── services/              ← Business logic layer
│   │   │   ├── auth_service.py
│   │   │   ├── incident_service.py
│   │   │   ├── evidence_service.py
│   │   │   ├── compliance_service.py
│   │   │   ├── notification_service.py
│   │   │   ├── audit_service.py
│   │   │   ├── incident_explainer.py  ← Plain-English incident explanation
│   │   │   ├── s3_service.py
│   │   │   └── sqs_service.py
│   │   ├── ml/                    ← Machine learning pipeline
│   │   │   ├── classifier.py      ← AttackClassifier (sklearn + heuristic fallback)
│   │   │   ├── features.py        ← CICIDS2017 feature names + attack classes
│   │   │   └── model_registry.py  ← Model versioning and loading
│   │   ├── workers/               ← SQS background processors
│   │   │   ├── main.py            ← Worker entry point
│   │   │   ├── incident_worker.py
│   │   │   └── notification_worker.py
│   │   └── migrations/
│   │       └── versions/
│   │           ├── 001_initial_schema.py
│   │           ├── 002_rbac_roles.py
│   │           ├── 003_simplify_roles.py
│   │           ├── 004_sanitize_legacy_roles.py
│   │           ├── 005_revoked_tokens.py
│   │           └── 006_evidence_postgres_storage.py
│   ├── tests/
│   │   ├── conftest.py            ← SQLite in-memory test fixtures
│   │   ├── test_auth.py
│   │   ├── test_incidents.py
│   │   ├── test_rbac.py
│   │   └── test_missing_endpoints.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx                ← Root component, React Query + Router setup
│   │   ├── main.tsx               ← Entry point; conditionally starts MSW
│   │   ├── api/
│   │   │   └── client.ts          ← Axios instance, all API call functions
│   │   ├── components/
│   │   │   ├── incidents/
│   │   │   │   └── IncidentExplainer.tsx ← AI explanation card
│   │   │   ├── layout/
│   │   │   │   ├── Navbar.tsx
│   │   │   │   └── Sidebar.tsx    ← Permission-gated navigation
│   │   │   └── ui/                ← Design system primitives
│   │   │       ├── GlassCard.tsx
│   │   │       ├── SeverityBadge.tsx
│   │   │       ├── StatusBadge.tsx
│   │   │       ├── StatCard.tsx
│   │   │       ├── Skeleton.tsx
│   │   │       ├── Toast.tsx
│   │   │       └── ErrorBoundary.tsx
│   │   ├── hooks/
│   │   │   ├── useApi.ts          ← React Query wrapper hooks
│   │   │   └── usePermissions.ts  ← RBAC hooks (useCan, usePermissions)
│   │   ├── layouts/
│   │   │   └── AppLayout.tsx      ← Authenticated shell (Sidebar + Navbar + Outlet)
│   │   ├── lib/
│   │   │   ├── rbac.ts            ← Permission helpers (non-hook, for outside React)
│   │   │   ├── logger.ts          ← Structured client-side logger
│   │   │   └── rateLimiter.ts     ← Client-side request throttle + retry backoff
│   │   ├── mocks/
│   │   │   ├── browser.ts         ← MSW browser worker setup
│   │   │   ├── data.ts            ← Shared mock data fixtures
│   │   │   ├── mockPdf.ts         ← Base64 data URL for mock PDF downloads
│   │   │   └── handlers/          ← Per-domain MSW request handlers
│   │   │       ├── auth.ts
│   │   │       ├── incidents.ts
│   │   │       ├── evidence.ts
│   │   │       ├── reports.ts
│   │   │       └── ... (one file per domain)
│   │   ├── pages/                 ← One file per route
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── IncidentsPage.tsx
│   │   │   ├── IncidentDetailPage.tsx
│   │   │   ├── CreateIncidentPage.tsx
│   │   │   ├── EvidencePage.tsx
│   │   │   ├── CompliancePage.tsx
│   │   │   ├── ComplianceAuditPage.tsx
│   │   │   ├── WeeklyReportPage.tsx
│   │   │   ├── MLInsightsPage.tsx
│   │   │   ├── SecurityScorePage.tsx
│   │   │   ├── NotificationsPage.tsx
│   │   │   ├── AuditLogsPage.tsx
│   │   │   ├── InfrastructurePage.tsx
│   │   │   ├── UsersPage.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   └── ...
│   │   ├── routes/
│   │   │   ├── AppRouter.tsx      ← All routes, lazy-loading, permission guards
│   │   │   └── ProtectedRoute.tsx ← Auth + permission gate component
│   │   ├── store/
│   │   │   └── authStore.ts       ← Zustand auth store (JWT in memory, not localStorage)
│   │   ├── types/
│   │   │   ├── index.ts           ← Core TypeScript type definitions
│   │   │   └── rbac.ts            ← Permission and Role enums, ROLE_PERMISSIONS map
│   │   └── constants/
│   │       └── index.ts           ← App-wide constants (timeouts, limits, headers)
│   ├── public/
│   │   └── mockServiceWorker.js   ← MSW service worker (v2.14.6)
│   └── package.json
├── docker/
│   ├── Dockerfile.api             ← API server image
│   └── Dockerfile.worker          ← Background worker image
├── frontend/Dockerfile            ← Frontend image (Vite build → nginx)
├── docker-compose.yml             ← Full local dev stack
├── scripts/
│   ├── seed.py                    ← Create default admin user on first run
│   ├── seed_demo_data.py          ← Populate realistic demo incidents/records
│   └── localstack-init.sh         ← Create S3 buckets and SQS queues in LocalStack
└── terraform/
    ├── main.tf                    ← AWS provider, all modules wired together
    ├── variables.tf               ← Input variables with descriptions and defaults
    ├── outputs.tf                 ← ALB URL, ECS cluster name, etc.
    └── modules/
        ├── networking/            ← VPC, subnets, NAT gateway, security groups
        ├── ecs/                   ← ECS cluster, task definitions, services, ALB
        ├── rds/                   ← RDS PostgreSQL instance
        ├── s3/                    ← Evidence and reports buckets with encryption
        ├── sqs/                   ← Incident and notification queues + DLQ
        ├── iam/                   ← Task execution role, task role, policies
        └── monitoring/            ← CloudWatch alarms, dashboards, SNS alerts
```

---

## 4. Backend Deep Dive

### Entry Point: `main.py`

`main.py` is the FastAPI application factory. It does five things in order:

1. **Configures logging** — sets up structlog to output colored console logs in development and machine-readable JSON in production. Both paths use the same structlog processor chain so all third-party libraries (which use stdlib `logging`) are captured in the same format.

2. **Creates the FastAPI app** — with `lifespan` context manager that ensures S3 buckets exist on startup. Swagger UI and OpenAPI JSON are only served in debug mode.

3. **Registers middleware** — in outermost-first order: `SecurityHeadersMiddleware`, `RateLimitMiddleware`, `TrustedHostMiddleware`, `CORSMiddleware`, and finally a custom async middleware that attaches a `request_id` to every request and logs method/path/status/duration.

4. **Registers exception handlers** — `LBROException` for controlled application errors, and a generic handler for unhandled exceptions that returns a sanitized 500 response.

5. **Mounts all 12 routers** — all under the `/api/v1` prefix.

### Routers

Each router is a thin HTTP layer. Route handlers validate input (via Pydantic schemas), check permissions (via `require_permission` dependency), instantiate a service, call one service method, and return the result. Routers never contain business logic.

| Router | Prefix | Key endpoints |
|---|---|---|
| `auth` | `/api/v1/auth` | POST /login, POST /register, POST /logout, GET /me, POST /refresh |
| `incidents` | `/api/v1/incidents` | Full CRUD + /stats + /{id}/explain |
| `evidence` | `/api/v1/incidents/{id}/evidence` | POST (upload), GET (list), GET /{id}/download |
| `compliance` | `/api/v1/compliance` | GET /dashboard, POST /records/{id}/mark-met |
| `notifications` | `/api/v1/notifications` | GET (list), GET /{id}, POST /{id}/approve, POST /{id}/dispatch |
| `reports` | `/api/v1/reports` | GET /weekly (JSON), GET /weekly/pdf, GET /compliance/pdf |
| `dashboard` | `/api/v1/dashboard` | GET /summary |
| `users` | `/api/v1/users` | Full CRUD (admin only) |
| `ml` | `/api/v1/ml` | GET /stats, GET /model-info, POST /classify |
| `audit` | `/api/v1/audit` | GET /logs |
| `security_score` | `/api/v1/security-score` | GET / |
| `infrastructure` | `/api/v1/infrastructure` | GET / (AWS resource status) |

### Services

Services contain all business logic. Each service takes an async `AsyncSession` as a constructor argument and uses it for all database operations. Services never know about HTTP — they receive Python objects and return Python objects.

**`auth_service.py`** — Handles user registration, login with account lockout enforcement, JWT access and refresh token generation, and token refresh. On login, it embeds the user's full permission list into the JWT payload so the frontend can perform permission checks without a round-trip.

**`incident_service.py`** — CRUD for incidents with filtering (status, severity, ML review flag, text search). On create, it runs the ML classifier against any provided network features. Also provides the aggregated stats endpoint used by the dashboard.

**`evidence_service.py`** — Manages file uploads with SHA-256 hashing, content inspection (rejects dangerous file signatures like `MZ`, `ELF`, `<?php`), and chain-of-custody recording. Files are stored as `LargeBinary` in PostgreSQL, deferred-loaded so they do not appear in list queries.

**`compliance_service.py`** — Generates compliance obligations when an incident is created, based on jurisdiction flags (`personal_data_involved`, `health_data_involved`, `affected_jurisdictions`). Populates deadlines per regulation (GDPR: 72 hours; HIPAA: 60 days; DPDPA: 72 hours).

**`notification_service.py`** — Generates draft regulatory authority notifications from compliance obligations. Builds the subject and body of the notification letter, identifies the correct Data Protection Authority for each jurisdiction, and stores it with `status=pending` for human approval.

**`audit_service.py`** — Writes structured audit log entries. Called by the `dependencies.py` `require_permission` dependency on every 403, and explicitly by service methods for sensitive actions (evidence access, user modification).

**`incident_explainer.py`** — Takes an incident and returns a plain-English explanation of the attack: what it is, its MITRE ATT&CK mapping, business impact, technical impact, OWASP category (for web attacks), and recommended remediations. Has a curated knowledge base for all 15 CICIDS2017 attack classes.

### Dependencies (`dependencies.py`)

FastAPI dependency injection is the RBAC enforcement point. Two key dependencies:

**`get_current_active_user`** — Reads the `Authorization: Bearer <token>` header, decodes the JWT, checks the `jti` against the `revoked_tokens` table (for logout), and returns the active user. Also handles API key authentication by looking up `X-API-Key` against the hashed `api_key` column.

**`require_permission(permission)`** — Returns a dependency that calls `get_current_active_user` and then checks whether the user's role holds the requested permission using `has_permission()` from `core/rbac.py`. On failure, it logs a 403 to the audit log and raises an `HTTPException`.

### Authentication

Authentication is JWT-based with two token types:

- **Access token** — 30-minute lifetime, signed with HS256. Contains `sub` (user UUID), `exp`, `type: "access"`, `jti` (unique ID for revocation), `role`, and `permissions` (full permission list as an array).
- **Refresh token** — 7-day lifetime. Contains `sub`, `exp`, `type: "refresh"`. Used to obtain a new access token without re-entering credentials.

**Token revocation** — On logout, the token's `jti` is stored in the `revoked_tokens` table with its expiry timestamp. Every authenticated request checks this table. A background cleanup job removes expired JTI records.

**Account lockout** — After 5 failed login attempts, the account is locked for 15 minutes. The `failed_login_attempts` and `locked_until` columns on the `User` model track this.

**Password hashing** — bcrypt via `passlib`. The cost factor defaults to 12.

### Workers

The `workers/` directory contains two long-running queue consumers:

**`incident_worker.py`** — Polls `SQS_INCIDENT_QUEUE_URL`. For each message, it re-classifies the incident, applies automated containment actions (simulated firewall rule additions, rate limit triggers), and updates the incident record.

**`notification_worker.py`** — Polls `SQS_NOTIFICATION_QUEUE_URL`. For each approved notification message, it sends the notification email via SMTP, updates the notification status to `sent`, and records the sent timestamp.

---

## 5. Frontend Deep Dive

### Pages

Every page is a React component that fetches its own data using Axios API functions (not React Query hooks at the page level — most pages use local `useEffect`/`useState` patterns with the typed Axios client from `api/client.ts`).

| Page | Route | Description |
|---|---|---|
| `DashboardPage` | `/dashboard` | Summary cards (incidents, notifications, compliance), recent incident list, severity/status charts |
| `IncidentsPage` | `/incidents` | Filterable, searchable table of all incidents with status/severity badges |
| `IncidentDetailPage` | `/incidents/:id` | Full incident view: metadata, network details, ML result, actions, evidence list, IncidentExplainer |
| `CreateIncidentPage` | `/incidents/new` | Multi-field form to manually create an incident, including network feature inputs |
| `EvidencePage` | `/evidence` | Global evidence vault table with upload and download |
| `CompliancePage` | `/compliance` | Per-regulation summary cards and overdue/upcoming obligation tables |
| `ComplianceAuditPage` | `/compliance/audit` | Full compliance audit view; downloadable PDF report |
| `WeeklyReportPage` | `/weekly-report` | Interactive preview of the weekly security report with downloadable PDF |
| `SecurityScorePage` | `/security-score` | A–F security grade, contributing factors, and recommendations |
| `MLInsightsPage` | `/ml-insights` | Model info, feature importance, per-class confidence, attack distribution charts |
| `NotificationsPage` | `/notifications` | Regulatory notification queue with approve/dispatch workflow |
| `AuditLogsPage` | `/audit-logs` | Full audit trail (admin only) |
| `UsersPage` | `/users` | User management CRUD (admin only) |
| `InfrastructurePage` | `/infrastructure` | AWS resource health status |
| `LoginPage` | `/login` | Email/password login with lockout display |
| `RoadmapPage` | `/roadmap` | Public product roadmap |
| `PrivacyPage` | `/privacy` | Privacy policy |

### Components

**Layout components** (`components/layout/`):
- `Sidebar.tsx` — Navigation menu. Each item is conditionally rendered based on the user's permissions using the `useCan` hook. This means viewers never see the Users or Audit Logs links.
- `Navbar.tsx` — Top bar with user info and logout.

**UI primitives** (`components/ui/`):
- `GlassCard.tsx` — The main card container with the characteristic parchment/warm-white background and subtle border.
- `SeverityBadge.tsx` / `StatusBadge.tsx` — Color-coded status pills.
- `StatCard.tsx` — Dashboard metric card.
- `Skeleton.tsx` — Loading placeholder animations.
- `Toast.tsx` — Transient notification system.
- `ErrorBoundary.tsx` — React error boundary that catches and displays errors gracefully.

**Feature component** (`components/incidents/`):
- `IncidentExplainer.tsx` — Renders the plain-English AI explanation. Calls the `/api/v1/incidents/{id}/explain` endpoint on mount and presents structured sections: plain English, business impact, MITRE ATT&CK, recommended fixes.

### Hooks

**`usePermissions.ts`** — Two hooks:
- `usePermissions()` — Returns the full `Set<PermissionValue>` for the current user.
- `useCan(permission)` — Returns a boolean indicating whether the current user holds a specific permission.

**`useApi.ts`** — React Query wrapper hooks for common data-fetching patterns. Not all pages use these (some use direct Axios calls with `useState`), but the hooks provide consistent caching, loading, and error states where they are used.

### API Client (`api/client.ts`)

The single Axios instance for all API communication. Key design decisions:

**Token storage** — The access token is stored in module-level memory (`_accessTokenMemory`), not in Zustand state. This avoids a Zustand `persist` bug where spreading state into a new object converts a getter to a null data property, making the interceptor read `null` instead of the token.

**Request interceptor** — Attaches `Authorization: Bearer <token>` from memory, adds a unique `X-Request-ID` for distributed tracing, and checks the client-side rate limiter before sending.

**Response interceptor** — On `401`, silently attempts a token refresh using the stored refresh token. If refresh succeeds, it retries the original request. If refresh fails, it calls `logout()` and redirects to `/login`. On `429` or `5xx`, it applies exponential backoff and retries up to 3 times.

**Deduplication** — Concurrent 401s all wait on the same `_refreshing` Promise. Only one refresh call is made even if multiple requests fail simultaneously.

### State Management

**Zustand auth store** (`store/authStore.ts`) — The only global state store. Holds: the authenticated user object, session expiry timestamp, login attempt count, and lockout timestamp. The access token is NOT in Zustand state (it is in module-level memory). The refresh token is persisted to `sessionStorage` (tab-scoped) so sessions survive page refresh within a tab but are cleared when the tab closes.

On rehydration from `sessionStorage`, if the session has not expired, the store marks `isAuthenticated: true` and restores the refresh token to memory. The access token must be re-acquired via a refresh call on the next 401 — this is acceptable since the first protected-page load will trigger it.

### RBAC (Frontend)

The frontend mirrors the backend's permission model in `types/rbac.ts`:

```typescript
enum Permission {
  CREATE_INCIDENT = 'incident:create',
  READ_INCIDENT   = 'incident:read',
  // ... all 25 permissions
}

const ROLE_PERMISSIONS: Record<Role, PermissionValue[]> = {
  admin:   [...all permissions],
  analyst: [...analyst permissions],
  viewer:  [...viewer permissions],
}
```

The source of truth is the `permissions` array embedded in the JWT. The frontend reads it from `user.permissions`. The `ROLE_PERMISSIONS` map serves as a fallback if the JWT field is missing.

### Routing

`AppRouter.tsx` uses React Router v6 with lazy-loaded page chunks. Every page inside the authenticated shell is wrapped in `ProtectedRoute`. Some routes add an additional `requiredPermission` prop for pages that should only be visible to certain roles. The route structure:

```
/                       → redirect to /dashboard
/login                  → public (eager loaded)
/register               → public (eager loaded)
[ProtectedRoute]
  [AppLayout]
    /dashboard          → all authenticated users
    /incidents/*        → all authenticated users
    /evidence           → all authenticated users
    /compliance         → VIEW_COMPLIANCE required
    /compliance/audit   → VIEW_COMPLIANCE required
    /infrastructure     → VIEW_INFRASTRUCTURE required
    /ml-insights        → VIEW_ML required
    /audit-logs         → VIEW_AUDIT required (admin only)
    /users              → MANAGE_USERS required (admin only)
```

### Mock Mode

When running `npm run dev:mock`, Vite sets `VITE_MOCK=true`. `main.tsx` detects this and starts the MSW browser service worker before rendering the app. All `fetch`/XHR calls are intercepted by handlers in `src/mocks/handlers/`. This allows the full frontend to run without any backend.

For PDF downloads in mock mode, `WeeklyReportPage` and `ComplianceAuditPage` render native `<a href="data:application/pdf;base64,..." download>` anchor elements. This sidesteps MSW, the fetch API, service worker dependency, and browser gesture restrictions entirely.

---

## 6. Database Schema

All tables use UUIDs as primary keys (PostgreSQL `uuid` type with `uuid_generate_v4()` default). All timestamps are stored with timezone.

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | VARCHAR(255) UNIQUE | Indexed |
| `username` | VARCHAR(100) UNIQUE | Indexed |
| `full_name` | VARCHAR(255) | |
| `hashed_password` | TEXT | bcrypt |
| `role` | VARCHAR(50) | `admin`, `analyst`, or `viewer` |
| `is_active` | BOOLEAN | Soft-disable accounts |
| `is_verified` | BOOLEAN | Email verification flag |
| `mfa_enabled` | BOOLEAN | MFA flag |
| `mfa_secret` | TEXT NULLABLE | TOTP secret |
| `last_login` | TIMESTAMPTZ NULLABLE | |
| `failed_login_attempts` | INTEGER | Account lockout counter |
| `locked_until` | TIMESTAMPTZ NULLABLE | Lockout expiry |
| `api_key` | VARCHAR(128) UNIQUE NULLABLE | Indexed; hashed API key |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

**Relationships:** one-to-many to `incidents` (assigned_to), `audit_logs`.

### `incidents`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `external_id` | VARCHAR(100) UNIQUE NULLABLE | e.g. "INC-2024-0001" |
| `title` | VARCHAR(500) | |
| `description` | TEXT NULLABLE | |
| `status` | VARCHAR(50) INDEX | `new`, `triaging`, `contained`, `eradicating`, `recovering`, `closed`, `reopened` |
| `severity` | VARCHAR(50) INDEX | `critical`, `high`, `medium`, `low`, `info` |
| `attack_category` | VARCHAR(100) NULLABLE | ML-classified attack type |
| `confidence_score` | FLOAT NULLABLE | ML confidence (0–1) |
| `ml_model_version` | VARCHAR(50) NULLABLE | |
| `needs_analyst_review` | BOOLEAN | Set when confidence < threshold |
| `source_ip` / `destination_ip` | VARCHAR(45) NULLABLE | IPv4 or IPv6 |
| `source_port` / `destination_port` | INTEGER NULLABLE | |
| `protocol` | VARCHAR(20) NULLABLE | |
| `network_features` | JSONB NULLABLE | Full CICIDS2017 feature vector |
| `containment_actions` | JSONB NULLABLE | Array of action records |
| `affected_jurisdictions` | JSONB NULLABLE | Array of jurisdiction strings |
| `personal_data_involved` | BOOLEAN | Triggers GDPR/DPDPA compliance |
| `health_data_involved` | BOOLEAN | Triggers HIPAA compliance |
| `assigned_to` | UUID FK → users NULLABLE | |
| `created_by` | UUID FK → users NULLABLE | |
| `detected_at` / `closed_at` / `created_at` / `updated_at` | TIMESTAMPTZ | |

**Relationships:** many-to-one to `users`; one-to-many to `evidence`, `notifications`, `incident_actions`, `compliance_records`.

### `incident_actions`

Logs every action taken on an incident (automated or manual): status changes, containment steps, analyst notes.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `incident_id` | UUID FK → incidents CASCADE | Indexed |
| `action_type` | VARCHAR(100) | e.g. "status_changed", "contained" |
| `description` | TEXT | Human-readable action description |
| `performed_by` | UUID FK → users NULLABLE | |
| `automated` | BOOLEAN | True for ML/worker actions |
| `result` | TEXT NULLABLE | |
| `action_metadata` | JSONB NULLABLE | |
| `created_at` | TIMESTAMPTZ | |

### `evidence`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `incident_id` | UUID FK → incidents CASCADE | Indexed |
| `filename` | VARCHAR(500) | Sanitized filename |
| `original_filename` | VARCHAR(500) | As uploaded |
| `content_type` | VARCHAR(200) | Allowlisted MIME type |
| `file_size` | INTEGER | Bytes |
| `s3_key` / `s3_bucket` | TEXT NULLABLE | Legacy S3 storage fields |
| `sha256_hash` | VARCHAR(64) | Integrity verification |
| `file_data` | LARGEBINARY NULLABLE DEFERRED | Primary storage — not loaded on list queries |
| `description` | TEXT NULLABLE | |
| `tags` | TEXT NULLABLE | JSON array serialized as text |
| `is_immutable` | BOOLEAN | Once uploaded, file cannot be modified |
| `uploaded_by` | UUID FK → users NULLABLE | |
| `created_at` | TIMESTAMPTZ | |

**Key design note:** `file_data` is marked `deferred` in SQLAlchemy. This means it is excluded from `SELECT *` queries. When listing evidence records, PostgreSQL returns everything except the binary blob. Only when a download is explicitly requested does SQLAlchemy issue a separate `SELECT file_data FROM evidence WHERE id = ?`.

### `chain_of_custody`

Every access to an evidence record is logged here.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `evidence_id` | UUID FK → evidence CASCADE | Indexed |
| `action` | VARCHAR(100) | `uploaded`, `accessed`, `exported`, `verified` |
| `performed_by` | UUID FK → users NULLABLE | |
| `performed_by_name` | VARCHAR(255) | Denormalized name snapshot |
| `ip_address` | VARCHAR(45) NULLABLE | |
| `created_at` | TIMESTAMPTZ | |

### `compliance_records`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `incident_id` | UUID FK → incidents CASCADE | Indexed |
| `regulation` | VARCHAR(50) | `GDPR`, `HIPAA`, `DPDPA` |
| `jurisdiction` | VARCHAR(100) | e.g. "EU", "United States", "India" |
| `obligation` | VARCHAR(500) | e.g. "Notify supervisory authority within 72 hours" |
| `deadline` | TIMESTAMPTZ | Calculated from incident `detected_at` |
| `is_met` | BOOLEAN | |
| `met_at` | TIMESTAMPTZ NULLABLE | |
| `notes` | TEXT NULLABLE | |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

### `notifications`

Regulatory authority notification drafts.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `incident_id` | UUID FK → incidents CASCADE | Indexed |
| `regulation` | VARCHAR(50) | |
| `jurisdiction` | VARCHAR(100) | |
| `authority` | VARCHAR(500) | Full authority name (e.g. "ICO - UK") |
| `authority_email` | VARCHAR(255) NULLABLE | |
| `status` | VARCHAR(50) INDEX | `pending`, `approved`, `sent`, `failed`, `cancelled` |
| `subject` | VARCHAR(500) | Draft email subject |
| `body` | TEXT | Draft notification letter body |
| `deadline` | TIMESTAMPTZ | When notification must be sent |
| `sent_at` | TIMESTAMPTZ NULLABLE | |
| `approved_by` / `approved_at` | UUID NULLABLE / TIMESTAMPTZ NULLABLE | |
| `retry_count` | INTEGER | For failed dispatch retries |
| `last_error` | TEXT NULLABLE | |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

### `notification_recipients`

| Column | Type |
|---|---|
| `id` | UUID PK |
| `notification_id` | UUID FK → notifications CASCADE |
| `email` | VARCHAR(255) |
| `name` | VARCHAR(255) NULLABLE |
| `recipient_type` | VARCHAR(50) — `primary`, `cc`, `bcc` |

### `audit_logs`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users NULLABLE INDEX | |
| `user_email` | VARCHAR(255) NULLABLE | Denormalized — survives user deletion |
| `action` | VARCHAR(200) INDEX | e.g. "incident.created", "evidence.accessed" |
| `resource_type` | VARCHAR(100) NULLABLE INDEX | "incident", "evidence", etc. |
| `resource_id` | VARCHAR(36) NULLABLE | UUID of the resource |
| `ip_address` | VARCHAR(45) NULLABLE | |
| `user_agent` | TEXT NULLABLE | |
| `request_method` | VARCHAR(10) NULLABLE | |
| `request_path` | TEXT NULLABLE | |
| `response_status` | INTEGER NULLABLE | |
| `details` | JSONB NULLABLE | Arbitrary event metadata |
| `created_at` | TIMESTAMPTZ INDEX | |

### `revoked_tokens`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `jti` | VARCHAR(36) UNIQUE INDEX | JWT ID claim from the token |
| `expires_at` | TIMESTAMPTZ | When the token naturally expires |
| `created_at` | TIMESTAMPTZ | When the revocation was recorded |

Records are cleaned up periodically (by a background task or on-startup purge) once `expires_at < NOW()`.

### Key Indexes

- `incidents.status` — filtered by status on every list query
- `incidents.severity` — filtered by severity on every list query
- `audit_logs.created_at` — time-range queries for the audit log view
- `audit_logs.action` — filter by action type
- `users.email` / `users.username` / `users.api_key` — unique lookups
- `evidence.incident_id` — list all evidence for an incident
- `revoked_tokens.jti` — checked on every authenticated request

---

## 7. ML Pipeline

### Model

LBRO uses a scikit-learn pipeline trained on the **CICIDS2017** (Canadian Institute for Cybersecurity Intrusion Detection 2017) dataset. The classifier is stored as a serialized pickle file (`cicids2017_classifier.pkl`) and loaded at startup.

The model is a **Random Forest** classifier with 80 input features derived from network flow statistics. It outputs a probability distribution over 15 attack classes plus BENIGN.

### Dataset

CICIDS2017 is a publicly available labeled network traffic dataset containing 2.8 million samples across 15 attack categories generated in a realistic lab environment. The dataset covers Monday–Friday of a week with different attack scenarios each day:
- Monday: Benign traffic only
- Tuesday: FTP-Patator, SSH-Patator
- Wednesday: DoS slowloris, DoS Slowhttptest, DoS Hulk, DoS GoldenEye, Heartbleed
- Thursday: Web attacks (XSS, SQL injection, Brute Force), Infiltration
- Friday: Bot, PortScan, DDoS

### Features

The model uses 80 CICIDS2017 statistical flow features. These are per-flow network statistics that capture timing, packet length, flag patterns, and bulk transfer behavior. Key feature categories:

- **Flow duration and packet counts** — `flow_duration`, `total_fwd_packets`, `total_bwd_packets`
- **Packet length statistics** — max, min, mean, std for both forward and backward directions
- **Flow rates** — `flow_bytes_per_sec`, `flow_packets_per_sec`
- **Inter-arrival times (IAT)** — mean, std, max, min for flow, forward, and backward
- **TCP flag counts** — `syn_flag_count`, `ack_flag_count`, `psh_flag_count`, `rst_flag_count`, `fin_flag_count`
- **Window sizes** — `init_win_bytes_forward`, `init_win_bytes_backward`
- **Bulk transfer stats** — bytes/packets/rate for bulk segments in both directions
- **Active/idle time** — `active_mean`, `active_std`, `idle_mean`, `idle_std`

### Attack Classes and Severity Mapping

| Attack Class | LBRO Severity |
|---|---|
| BENIGN | info |
| DoS Hulk | critical |
| PortScan | medium |
| DDoS | critical |
| DoS GoldenEye | high |
| FTP-Patator | high |
| SSH-Patator | high |
| DoS slowloris | high |
| DoS Slowhttptest | high |
| Bot | critical |
| Web Attack - Brute Force | high |
| Web Attack - XSS | medium |
| Infiltration | critical |
| Web Attack - Sql Injection | critical |
| Heartbleed | critical |

### Confidence and Review Threshold

Every prediction returns a confidence score between 0 and 1 (the maximum class probability from `predict_proba`). Two thresholds are configured:

- **`ML_CONFIDENCE_THRESHOLD` (default: 0.75)** — Below this, the incident is flagged `needs_analyst_review = true`.
- **`ML_REVIEW_QUEUE_THRESHOLD` (default: 0.60)** — Below this, the incident is also enqueued for re-analysis by the background worker.

### Heuristic Fallback

When the model file does not exist (development environments without the trained model), the classifier falls back to a rule-based heuristic:
- `flow_packets_per_sec > 10,000` → DDoS
- `syn_flag_count > 1,000` → DoS Hulk
- `destination_port == 21` → FTP-Patator
- `destination_port == 22` → SSH-Patator
- `destination_port in (80, 443, 8080)` → Web Attack - Brute Force
- Otherwise → BENIGN

Heuristic predictions always set confidence to 0.65 (below both thresholds), so all heuristic incidents are flagged for review.

### Explainability

The classifier also returns the top 10 most influential features for each prediction, ranked by absolute feature value (normalized by the total feature magnitude). This is a simple approach, not full SHAP-style attribution, but gives analysts a starting point: "this traffic was classified as DDoS because it has extremely high `flow_packets_per_sec` and `syn_flag_count`."

### Limitations

- The model is trained on 2017 data. Modern attack tooling has evolved. The model handles the attack types it was trained on well but will misclassify novel attack patterns.
- The features require a network flow statistics collector (like CICFlowMeter or similar) in production. Raw packet capture must be pre-processed into CICIDS2017 feature format before classification.
- The pickle file must be present at `ML_MODEL_PATH` (default: `/app/ml/models/cicids2017_classifier.pkl`). It is not included in the repository and must be trained separately or provided externally.

### Future Improvements

- Integrate SHAP for proper feature attribution.
- Re-train annually on updated datasets (CICIDS2018, UNSW-NB15).
- Add online learning capability to adapt to emerging patterns without full retraining.
- Support custom feature mappings for organizations whose flow collectors use different column names.

---

## 8. Compliance Engine

### Overview

The compliance engine is triggered automatically when an incident is created with data sensitivity flags. It has three stages: obligation generation, notification drafting, and notification dispatch.

### Stage 1: Obligation Generation

When `create_incident` is called with any of:
- `personal_data_involved = true`
- `health_data_involved = true`
- `affected_jurisdictions = ["EU", ...]`

The `ComplianceService.generate_obligations(incident)` method runs. It creates `ComplianceRecord` rows for each applicable regulation with the correct deadline:

- **GDPR** — triggered by `personal_data_involved` or EU in `affected_jurisdictions`. Deadline: 72 hours from `detected_at`.
- **HIPAA** — triggered by `health_data_involved`. Deadline: 60 days from `detected_at`.
- **DPDPA** — triggered by India in `affected_jurisdictions`. Deadline: 72 hours from `detected_at`.

### Stage 2: Notification Drafting

Immediately after obligation generation, `NotificationService.generate_for_incident(incident)` creates draft `Notification` records for each jurisdiction-regulation pair. It fills in:
- `authority` — the full name of the relevant Data Protection Authority
- `authority_email` — known DPA contact addresses
- `subject` — a templated notification subject line
- `body` — a multi-paragraph notification letter explaining the breach
- `deadline` — copied from the compliance record
- `status = "pending"`

### Stage 3: Human Approval and Dispatch

The notification approval flow is a two-step process:
1. An analyst or admin views the pending notification in the Notifications page and clicks "Approve".
2. An admin clicks "Dispatch" to send the notification.

On dispatch, the notification is enqueued to SQS (`SQS_NOTIFICATION_QUEUE_URL`). The notification worker picks it up, sends the email via SMTP, and updates `status = "sent"` with `sent_at = now()`.

### Reports

**Weekly Security Report (JSON)** — `GET /api/v1/reports/weekly` returns a comprehensive JSON payload built from live database state. It includes incident counts by severity, top attack types, most targeted ports, critical open incidents, recently resolved incidents, evidence count, compliance summary, security score, recommendations, and trend analysis.

**Weekly Security Report (PDF)** — `GET /api/v1/reports/weekly/pdf` calls `_generate_pdf(data)` which uses ReportLab to produce a multi-page A4 PDF with the LBRO brand (warm cream background, orange LBRO wordmark), data tables, a numbered security score, and per-page footer with generation timestamp and page number.

**Compliance Audit Report (PDF)** — `GET /api/v1/reports/compliance/pdf` queries all `ComplianceRecord` rows, groups them by regulation, and produces a tabular audit report showing each obligation, its current status (MET/OVERDUE/PENDING), deadline, and notes. Also uses ReportLab.

### Evidence and Audit Logs

Every evidence upload, access, and download is recorded in both `chain_of_custody` (specific to each evidence file) and `audit_logs` (system-wide log). This creates a legally defensible record that LBRO can point to in a regulatory investigation: every person who touched the evidence is recorded with their user ID, name snapshot, IP address, and timestamp.

### PDF Generation and Download Workflow

PDF reports are generated on-demand per request — not pre-generated or cached. The flow:

1. Frontend calls `GET /api/v1/reports/weekly/pdf`
2. Backend runs `_build_report_data(db)` to aggregate current database state
3. Backend calls `_generate_pdf(data)` using ReportLab's Platypus document engine
4. Backend streams the result as `StreamingResponse` with `Content-Disposition: attachment; filename="..."` and `Content-Length`
5. Browser triggers a native file download

In mock mode, the frontend skips this entire chain and uses a pre-baked base64 PDF in `mockPdf.ts` served as a native anchor `<a href="data:..." download>`.

---

## 9. Security Model

### JWT Security

- Tokens are signed with HMAC-SHA256 using a secret key that must be at least 32 characters.
- In production, the application refuses to start if `SECRET_KEY` is the default placeholder — enforced by a Pydantic validator that checks `ENVIRONMENT == "production"`.
- Access tokens have a 30-minute lifetime. Refresh tokens have a 7-day lifetime.
- On logout, the access token's `jti` is stored in `revoked_tokens` and checked on every subsequent request.

### RBAC

A three-tier permission model:

**Viewer** — Read-only access. Can view incidents, download evidence, view compliance status, view reports, receive notifications.

**Analyst** — All viewer permissions plus: create/update/assign incidents, upload evidence, generate and approve reports, view and export audit logs, approve notifications, manage compliance records, view infrastructure.

**Admin** — All permissions including: delete incidents, delete evidence, manage users and roles, rotate API keys, manage ML models, system settings.

The permission check happens in a single location: `require_permission(permission)` in `dependencies.py`. The `ROLE_PERMISSIONS` map in `core/rbac.py` is the only place where the role-to-permission relationship is defined. No route handler compares role strings directly.

### Rate Limiting

Implemented as an async in-memory sliding window (`middleware/rate_limit.py`):

- **Default limit:** 60 requests per IP per minute (configurable via `RATE_LIMIT_PER_MINUTE`).
- **Auth endpoints (strict):**
  - `/api/v1/auth/login` → 10 req/min
  - `/api/v1/auth/register` → 10 req/min
  - `/api/v1/auth/refresh` → 20 req/min
- Rate limit keys are `ip:path` (not just `ip`), so hitting the login rate limit does not affect other endpoints.
- Returns `429` with `Retry-After` header.
- Exempt paths: `/health`, `/metrics`, `/docs`, `/openapi.json`.
- In production, this should be replaced with a Redis-backed implementation to work correctly across multiple API replicas.

### Password Hashing

bcrypt via `passlib`. The work factor is the passlib default (12). The hash is never logged or serialized to API responses.

### Security Headers

Every response gets (`middleware/security_headers.py`):
- `X-Content-Type-Options: nosniff` — prevents MIME sniffing
- `X-Frame-Options: DENY` — prevents clickjacking
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Strict-Transport-Security` (HTTPS only)
- Environment-appropriate `Content-Security-Policy`

The `Server` header is removed to avoid fingerprinting.

### Upload Validation

Evidence uploads check:
1. **Content-Length** — rejects files larger than 100 MB before reading.
2. **Declared MIME type** — only an allowlist of types are accepted.
3. **Content inspection** — reads the first few bytes and rejects known dangerous signatures: `MZ` (Windows executables), `ELF` (Linux binaries), `#!/` (shell scripts), `<script` (HTML/XSS), `<?php` (PHP).
4. **Filename sanitization** — strips directory traversal characters, limits to 255 characters.

### Audit Logging

The `audit_service.py` writes structured log entries for every significant action. The `require_permission` dependency automatically logs all 403 responses so failed access attempts are always recorded. The `audit_logs` table is append-only by design (no update or delete endpoints).

### Threat Model

| Threat | Mitigation |
|---|---|
| Credential brute force | Account lockout (5 attempts / 15 min), strict auth rate limits |
| Token theft | Short access token lifetime (30 min), JTI revocation on logout |
| Session fixation | Access token stored in module memory (not localStorage/cookies) |
| XSS | CSP headers, React's default DOM escaping, no `dangerouslySetInnerHTML` |
| SQL injection | SQLAlchemy parameterized queries — no raw SQL |
| CSRF | No cookies used for auth; no CSRF surface |
| Host header injection | `TrustedHostMiddleware` with explicit allowed hosts |
| SSRF via evidence upload | Content inspection + MIME allowlist |
| Privilege escalation | All permission checks in a single dependency; no client-side role bypass |
| Information disclosure | Generic error messages in production; Swagger disabled in production |

---

## 10. Deployment

### Local Development

```bash
# 1. Set required environment variable
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# 2. Start full stack
docker compose up --build

# 3. Seed admin user (runs once)
docker compose run --rm seed

# 4. Load demo data (optional)
docker compose run --rm api python /scripts/seed_demo_data.py
```

Services:
- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- LocalStack: `http://localhost:4566`

### Frontend Mock Mode (No Backend Required)

```bash
cd frontend
npm install
npm run dev:mock     # starts Vite with VITE_MOCK=true and MSW active
```

Default admin credentials (set by seed script):
- Email: `admin@lbro.local`
- Password: `Admin123!`

### Docker Architecture

**`Dockerfile.api`** — Multi-stage build. Stage 1 installs Python dependencies. Stage 2 copies the application code. Runs `uvicorn app.main:app --host 0.0.0.0 --port 8000` with `--workers 1` (async, single-process — scale by running multiple containers).

**`Dockerfile.worker`** — Same base image as the API. Entry point is `python -m app.workers.main` which starts the SQS polling loop.

**`frontend/Dockerfile`** — Stage 1: Node 20 Alpine, runs `npm ci && npm run build`. Stage 2: nginx Alpine, copies the `dist/` output, uses a custom `nginx.conf` that proxies `/api` to the API container and serves the SPA with `try_files $uri /index.html`.

### Docker Compose Services

| Service | Image | Ports | Dependencies |
|---|---|---|---|
| `postgres` | postgres:16-alpine | 5432 | — |
| `localstack` | localstack:3.4 | 4566 | — |
| `migrate` | local build | — | postgres healthy |
| `api` | local build | 8000 | postgres, localstack, migrate |
| `worker` | local build | — | postgres, localstack, migrate |
| `frontend` | local build | 3000 | api healthy |
| `seed` | local build | — | migrate completed |

### Terraform (AWS)

The Terraform configuration provisions the entire AWS infrastructure using modular design:

**`modules/networking`** — VPC with configurable CIDR, public and private subnets across multiple AZs, NAT gateway for outbound internet from private subnets, route tables and security groups.

**`modules/ecs`** — ECS Fargate cluster, ALB with target groups, ECS task definitions for API, worker, and frontend services, ECS services with configurable desired counts and auto-scaling policies.

**`modules/rds`** — RDS PostgreSQL 16 in a Multi-AZ configuration. Deletion protection enabled in production. The database password is generated by Terraform's `random_password` resource and stored in Secrets Manager.

**`modules/s3`** — Evidence and reports buckets with server-side encryption (AES-256), versioning enabled, and bucket policies that prevent public access.

**`modules/sqs`** — Incident queue, notification queue, and dead-letter queue. Messages visible for 300 seconds. Long-polling enabled (20 seconds wait time).

**`modules/iam`** — ECS execution role (pull images, write logs) and task role (access S3, SQS, Secrets Manager). Least-privilege policies scoped to specific bucket and queue ARNs.

**`modules/monitoring`** — CloudWatch alarms for: ECS service CPU/memory, RDS CPU, SQS dead-letter queue depth, ALB 5xx error rate. All alarms notify an SNS topic that emails `var.alert_email`.

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | **YES** | JWT signing key — min 32 chars |
| `DATABASE_URL` | **YES** | PostgreSQL connection string |
| `ENVIRONMENT` | YES | `development`, `test`, or `production` |
| `AWS_ACCESS_KEY_ID` | Production | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | Production | AWS credentials |
| `AWS_REGION` | YES | Default: `us-east-1` |
| `S3_BUCKET_EVIDENCE` | YES | Evidence file storage bucket |
| `S3_BUCKET_REPORTS` | YES | Report storage bucket |
| `SQS_INCIDENT_QUEUE_URL` | YES | Incident processing queue |
| `SQS_NOTIFICATION_QUEUE_URL` | YES | Notification dispatch queue |
| `CORS_ORIGINS` | YES | Comma-separated allowed origins |
| `SMTP_HOST` | Optional | Email relay for notifications |
| `ML_MODEL_PATH` | Optional | Path to classifier pickle |
| `ML_CONFIDENCE_THRESHOLD` | Optional | Default: 0.75 |

### CI/CD (GitHub Actions)

**`ci.yml`** — Runs on every push to `main`/`develop` and every PR:
1. **Backend lint** — Ruff (style + import sorting + modernization) + Ruff format check
2. **Backend tests** — pytest with SQLite in-memory, coverage report
3. **Backend Docker build** — builds API and worker images, verifies build succeeds
4. **Frontend lint** — TypeScript type check + ESLint
5. **Frontend build** — Vite production build + Docker image build
6. **Terraform validate** — `terraform fmt -check` + `terraform validate`
7. **Security scan** — Trivy filesystem scan (CRITICAL/HIGH only) + Bandit SAST

**`deploy.yml`** — Runs on push to `main` after CI passes:
1. Builds and pushes Docker images to ECR
2. Updates ECS task definitions with new image tags
3. Triggers ECS rolling deployment
4. Waits for service stability

---

## 11. API Reference

### Authentication

**`POST /api/v1/auth/register`**
- Creates a new user account (disabled in production unless `ALLOW_PUBLIC_REGISTRATION=true`)
- Body: `{ email, username, full_name, password }`
- Returns: `UserResponse`
- Permissions: public

**`POST /api/v1/auth/login`**
- Authenticates and returns tokens
- Body: `{ email, password }`
- Returns: `{ access_token, refresh_token, token_type, expires_in }`
- Rate limit: 10/min per IP

**`POST /api/v1/auth/refresh`**
- Exchanges a refresh token for a new access token
- Body: `{ refresh_token }`
- Returns: `TokenResponse`
- Rate limit: 20/min per IP

**`GET /api/v1/auth/me`**
- Returns the current authenticated user
- Auth: Bearer token required

**`POST /api/v1/auth/logout`**
- Revokes the current access token's JTI
- Returns: `204 No Content`

### Dashboard

**`GET /api/v1/dashboard/summary`**
- Returns aggregated incident counts, compliance status, evidence count, recent incidents, severity and status breakdowns
- Permission: `dashboard:read`

### Incidents

**`POST /api/v1/incidents`** — Permission: `incident:create`
- Body: `IncidentCreate` (title, description, severity, network features, jurisdiction flags)
- Auto-triggers ML classification, compliance obligation generation, notification drafting

**`GET /api/v1/incidents`** — Permission: `incident:read`
- Query params: `status`, `severity`, `needs_review`, `search`, `page`, `page_size`
- Returns: paginated list with `total`

**`GET /api/v1/incidents/stats`** — Permission: `incident:read`
- Returns: severity breakdown, status breakdown, recent counts

**`GET /api/v1/incidents/{id}`** — Permission: `incident:read`

**`PATCH /api/v1/incidents/{id}`** — Permission: `incident:update`

**`DELETE /api/v1/incidents/{id}`** — Permission: `incident:delete`

**`POST /api/v1/incidents/{id}/status`** — Permission: `incident:update`
- Body: `{ status, reason }`

**`POST /api/v1/incidents/{id}/assign`** — Permission: `incident:assign`

**`GET /api/v1/incidents/{id}/explain`** — Permission: `incident:read`
- Returns plain-English incident explanation from the incident explainer service

### Evidence

**`POST /api/v1/incidents/{id}/evidence`** — Permission: `evidence:upload`
- Multipart form: `file` (UploadFile), `description` (optional)
- Validates content type, inspects magic bytes, stores as binary in PostgreSQL

**`GET /api/v1/incidents/{id}/evidence`** — Permission: `evidence:download`

**`GET /api/v1/evidence/{id}/download`** — Permission: `evidence:download`
- Streams the file from PostgreSQL storage
- Records chain of custody

**`POST /api/v1/evidence/{id}/verify`** — Permission: `evidence:download`
- Re-computes SHA-256, compares to stored hash

### Compliance

**`GET /api/v1/compliance/dashboard`** — Permission: `compliance:read`
- Returns per-regulation summaries, overdue records, upcoming deadlines

**`POST /api/v1/compliance/records/{id}/mark-met`** — Permission: `compliance:manage`
- Body: `{ notes }` (optional)

### Notifications

**`GET /api/v1/notifications`** — Permission: `notification:read`
- Query params: `status`, `regulation`, `incident_id`, `page`, `page_size`

**`GET /api/v1/notifications/{id}`** — Permission: `notification:read`

**`POST /api/v1/notifications/{id}/approve`** — Permission: `notification:approve`

**`POST /api/v1/notifications/{id}/dispatch`** — Permission: `notification:dispatch`

### Reports

**`GET /api/v1/reports/weekly`** — Permission: `dashboard:read`
- Returns full weekly report as JSON

**`GET /api/v1/reports/weekly/pdf`** — Permission: `dashboard:read`
- Returns `application/pdf` attachment

**`GET /api/v1/reports/compliance/pdf`** — Permission: `compliance:read`
- Returns `application/pdf` attachment

### Security Score

**`GET /api/v1/security-score`** — Permission: `dashboard:read`
- Returns score (0–100), grade (A–F), contributing factors, recommendations

### ML

**`GET /api/v1/ml/stats`** — Permission: `ml:read`
- Returns per-attack-class incident counts from the database

**`GET /api/v1/ml/model-info`** — Permission: `ml:read`
- Returns model version, feature count, threshold settings

**`POST /api/v1/ml/classify`** — Permission: `ml:read`
- Body: JSON object with CICIDS2017 feature values
- Returns: `{ attack_category, confidence, severity, needs_review, probabilities, top_features }`

### Users

**`GET /api/v1/users`** — Permission: `user:manage`

**`POST /api/v1/users`** — Permission: `user:manage`

**`GET /api/v1/users/{id}`** — Permission: `user:manage`

**`PATCH /api/v1/users/{id}`** — Permission: `user:manage`

**`DELETE /api/v1/users/{id}`** — Permission: `user:manage`

### Audit

**`GET /api/v1/audit/logs`** — Permission: `audit:read`
- Query params: `page`, `page_size`, `user_id`, `action`

### Health

**`GET /health`** — Public
- Returns: `{ status: "ok", version, env }`

---

## 12. Frontend ↔ Backend Flows

### Login Flow

```
User enters email/password on LoginPage
  → LoginPage checks: useAuthStore.getState().isLocked() → show error if locked
  → authApi.login(email, password) → POST /api/v1/auth/login
      → Server validates credentials, checks lockout, checks account active
      → Server returns { access_token, refresh_token, user }
  → useAuthStore.getState().login(accessToken, refreshToken, user)
      → _accessTokenMemory = accessToken
      → _refreshTokenMemory = refreshToken
      → Zustand state: { isAuthenticated: true, user, sessionExpiresAt }
      → sessionStorage: { refreshToken, sessionExpiresAt, user }
  → navigate('/dashboard')
```

### Dashboard Load

```
Browser navigates to /dashboard
  → ProtectedRoute checks isAuthenticated → pass
  → DashboardPage mounts
  → dashboardApi.summary() → GET /api/v1/dashboard/summary
      → Axios interceptor: reads _accessTokenMemory, attaches Bearer header
      → Server: require_permission(VIEW_DASHBOARD) → check role
      → Server runs 8 COUNT queries + GROUP BY queries on incidents table
      → Returns aggregated JSON
  → DashboardPage renders summary cards, charts, recent incident table
```

### Incident Creation with ML Classification

```
Analyst fills CreateIncidentPage form (including optional network features)
  → incidentsApi.create(payload) → POST /api/v1/incidents
  → Server: require_permission(CREATE_INCIDENT)
  → IncidentService.create(data, user)
      → If network_features provided: classifier.predict(features)
          → Loads sklearn model from pickle (cached after first load)
          → Returns { attack_category, confidence, severity, needs_review }
      → Creates Incident record with ML results
      → If personal/health data flags or jurisdictions set:
          → ComplianceService.generate_obligations(incident)
          → NotificationService.generate_for_incident(incident)
  → Reload incident with selectinload (avoid lazy-load in async context)
  → Return IncidentResponse
  → Frontend: navigate to /incidents/:id
```

### Evidence Upload and Download

```
UPLOAD:
  Analyst selects file on EvidencePage
  → evidenceApi.upload(incidentId, file, description)
  → POST /api/v1/incidents/{id}/evidence (multipart)
  → Server checks Content-Length, reads file bytes
  → Validates MIME type against allowlist
  → Inspects first bytes for dangerous signatures
  → Sanitizes filename
  → Computes SHA-256 hash
  → Stores file bytes in evidence.file_data (PostgreSQL LargeBinary)
  → Creates chain_of_custody record: action="uploaded"
  → Returns EvidenceUploadResponse

DOWNLOAD:
  Analyst clicks download on EvidencePage
  → evidenceApi.downloadUrl(evidenceId) → GET /api/v1/evidence/{id}/download-url
  → Server creates blob URL from the file data, streams via StreamingResponse
  → Frontend: window.open(url) or anchor click triggers browser save dialog
  → Server records chain_of_custody: action="accessed"
```

### Notification Approval and Dispatch

```
GDPR incident created with EU jurisdiction
  → ComplianceService creates ComplianceRecord (GDPR, 72-hour deadline)
  → NotificationService creates Notification (status=pending, body=draft letter)

Analyst opens NotificationsPage
  → notificationsApi.list() → GET /api/v1/notifications
  → Sees pending notification with deadline countdown

Analyst reviews draft, clicks "Approve"
  → notificationsApi.approve(id) → POST /api/v1/notifications/{id}/approve
  → Server: require_permission(APPROVE_NOTIFICATION)
  → Updates status=approved, approved_by, approved_at

Admin clicks "Dispatch"
  → notificationsApi.dispatch(id) → POST /api/v1/notifications/{id}/dispatch
  → Server: require_permission(DISPATCH_NOTIFICATION)
  → Enqueues message to SQS_NOTIFICATION_QUEUE_URL
  → Notification worker picks up message
  → Sends email via SMTP
  → Updates status=sent, sent_at
```

### Reports Download

```
User opens WeeklyReportPage
  → reportsApi.weekly() → GET /api/v1/reports/weekly (JSON preview)
  → Page renders cards, tables, charts using the JSON data

User clicks "Download PDF"
  PRODUCTION PATH:
    → <button onClick={handleDownload}>
    → fetch GET /api/v1/reports/weekly/pdf (with Bearer token)
    → Server generates PDF with ReportLab from live DB
    → Returns StreamingResponse with Content-Disposition: attachment
    → Browser saves file

  MOCK MODE PATH:
    → <a href={MOCK_PDF_HREF} download="lbro-security-report-2026-07-04.pdf">
    → Browser natively handles data: URL download
    → No JavaScript, no fetch, no service worker involved
```

### RBAC in Action

```
Viewer user opens the app
  → Sidebar renders: only icons/links for permissions the viewer holds
  → "Users" and "Audit Logs" links do not appear in the sidebar
  → If viewer types /users manually in the URL:
      → ProtectedRoute checks requiredPermission={Permission.MANAGE_USERS}
      → useCan(Permission.MANAGE_USERS) returns false
      → Redirects to /dashboard

  → Even if viewer constructs a raw API call:
      → GET /api/v1/users with viewer's token
      → require_permission(MANAGE_USERS) dependency fires
      → has_permission(Role.VIEWER, Permission.MANAGE_USERS) → false
      → Returns 403, logs to audit_logs
```

---

## 13. Current Features

**Authentication and Users**
- Email/password login with JWT access + refresh tokens
- Token revocation on logout (JTI blacklist)
- Account lockout after 5 failed login attempts
- Three-role RBAC (admin, analyst, viewer) with 25 granular permissions
- API key authentication for programmatic access
- User CRUD (admin only)
- Self-registration (configurable, disabled by default in production)

**Incident Management**
- Create, read, update, delete incidents
- Lifecycle status machine (new → triaging → contained → eradicating → recovering → closed → reopened)
- Five severity levels (critical, high, medium, low, info)
- Filterable, searchable incident list with pagination
- Incident detail view with full metadata, network info, ML result
- Status history via incident actions table
- Incident assignment to team members
- Plain-English "explain this incident" powered by the knowledge base service

**ML Classification**
- CICIDS2017 Random Forest classifier with 80 features
- 15 attack categories with severity mapping
- Confidence score with configurable review threshold
- Analyst review flag (`needs_analyst_review`)
- Heuristic fallback when model file is not present
- Top contributing features returned with each prediction
- ML insights page with model info and per-class statistics

**Evidence Management**
- File upload (up to 100 MB) with MIME allowlist and magic byte inspection
- SHA-256 hash verification
- Chain-of-custody recording (upload, access, download events)
- Files stored directly in PostgreSQL (no S3 dependency for core function)
- Immutable after upload
- Evidence download with token authentication

**Compliance Automation**
- GDPR, HIPAA, DPDPA obligation auto-generation
- Deadline calculation per regulation
- Compliance dashboard with per-regulation summary
- Mark-as-met with notes
- Overdue and upcoming deadline views

**Regulatory Notifications**
- Automatic draft generation for each compliance obligation
- Identifies correct Data Protection Authority per jurisdiction
- Draft approval workflow (analyst approves, admin dispatches)
- SQS-based async email dispatch via notification worker
- Retry logic for failed sends

**Reports**
- Weekly security report (JSON preview + PDF download)
- Compliance audit report (PDF download)
- Both PDFs generated on-demand with ReportLab
- Executive summary, security score, incident breakdown, recommendations, trend analysis

**Security Score**
- 0–100 score with A–F grade
- Calculated from: open critical incidents, MFA coverage, compliance status, audit 403 rate
- Contributing factors with positive/negative classification
- Actionable recommendations

**Audit Logs**
- Append-only audit trail for all significant actions
- Automatic 403 logging
- Filterable by user, action, time range

**Dashboard**
- Summary metric cards
- Incident severity and status breakdown charts
- Recent incident list
- Overdue compliance count
- Pending notification count

**Infrastructure View**
- AWS service health status (S3, SQS connectivity)

**Settings and Profile**
- User settings page
- API key management

**Deployment**
- Full Docker Compose local stack (API, worker, frontend, PostgreSQL, LocalStack)
- Alembic database migrations with 6 migration versions
- Terraform configuration for full AWS production deployment
- GitHub Actions CI/CD with lint, test, Docker build, Terraform validate, Trivy + Bandit security scanning

---

## 14. Future Roadmap

### Version 1 (Current: 2.0.0) — Foundation

Everything documented above. The platform is functionally complete for its core use case: incident management, ML classification, compliance automation, evidence handling, and PDF reporting.

Known V1 limitations that must be addressed before production at scale:
- In-memory rate limiter (not distributed — must move to Redis)
- Evidence stored in PostgreSQL LargeBinary (fine for small teams, becomes a problem at scale — migrate to S3)
- No real email delivery (SMTP must be configured; no template system yet)
- HIPAA notification flow uses placeholder authority contacts
- ML model file not included in repository (must be trained and placed separately)

### Version 2 — Integration and Scale

**LBRO Agent** — A lightweight Go binary that can be installed on servers, container hosts, or network devices. It captures CICIDS2017 flow statistics from live traffic using CICFlowMeter or eBPF, classifies them locally, and pushes incident events to the LBRO API. This removes the manual feature extraction step and makes LBRO a real-time detection system.

**Cloudflare Integration** — Pull Cloudflare Firewall Events and WAF logs into LBRO automatically. Map Cloudflare threat types to CICIDS2017 attack categories. One-click investigation: click a Cloudflare firewall event to open a pre-populated LBRO incident.

**AWS WAF Integration** — Subscribe to AWS WAF sampled requests via CloudWatch Logs Insights. When AWS WAF blocks a request that matches a known attack pattern, auto-create an incident in LBRO with the WAF rule ID, matched request, and source IP.

**Automatic IP Blocking** — When an incident is confirmed as malicious and the source IP is known: automatically push a block rule to Cloudflare Firewall or AWS WAF via API. Tracked as a containment action in the incident timeline. Human approval required before execution.

**Security Score Trends** — Track the security score over time and display a 90-day trend chart. Alert when score drops below a configurable threshold.

### Version 3 — AI and Developer Positioning

**AI Security Assistant** — A conversational interface (powered by an LLM via the Anthropic API or OpenAI) embedded in the LBRO sidebar. Engineers can ask questions: "What attack patterns have we seen in the last week?", "What should I do about this DDoS?", "Draft a status update email for this incident." The assistant has access to the full LBRO context: incidents, compliance status, security score, audit logs.

**Developer-First Positioning** — VS Code extension and GitHub App:
- VS Code: shows the current security score and open incidents in the status bar.
- GitHub App: when a PR is opened that modifies security-sensitive files (auth, payments, data access), it comments with the relevant LBRO compliance obligations and recent related incidents.
- Slack/Teams integration: push incident notifications and weekly score summary to a chosen channel.

**Multi-Tenancy** — Organization-level separation within a single deployment. Each organization has its own incidents, users, and compliance configuration. Useful for managed security service providers (MSSPs) running LBRO for multiple clients.

**Advanced ML**
- SHAP integration for proper feature attribution.
- Online learning — the model updates incrementally from confirmed incident labels.
- Custom attack class definitions — organizations can add their own attack signatures.
- Anomaly detection mode — flag any traffic that deviates significantly from baseline even if it does not match a known attack class.

**Compliance Expansion**
- SOC 2 Type II control tracking.
- ISO 27001 control mapping.
- PCI-DSS incident response requirements.
- Automated DPA notification sending (currently manual + SMTP).
- Digital signature on notification PDFs.

---

## 15. Interview Guide

### How to Present LBRO

Start with the problem, not the technology: "Most small engineering teams have no documented security incident response process. When a breach happens, they lose hours figuring out what regulation applies, what the deadline is, and who to notify. LBRO automates that."

Then describe the key innovation: "LBRO uses a machine learning classifier trained on the CICIDS2017 dataset — the largest publicly available labeled network traffic dataset — to automatically classify network attacks into 15 categories with a confidence score. Below the confidence threshold, it flags the incident for human review."

Then close with the compliance angle: "When an incident involves personal data or health records, LBRO automatically calculates the legal notification deadlines under GDPR, HIPAA, and India's DPDPA, drafts the regulatory authority letters, and manages the approval-and-send workflow."

### Common Interview Questions

**"What is LBRO?"**
A full-stack security incident response platform with ML-powered attack classification and built-in compliance automation for GDPR, HIPAA, and DPDPA. It detects, classifies, triages, and manages security incidents from detection through resolution and regulatory reporting.

**"What was the hardest technical problem you solved?"**
Async SQLAlchemy with FastAPI has a subtle problem: when you return a Pydantic response model from a route, SQLAlchemy has already committed the transaction. Lazy-loaded relationships (like incident actions) cannot be loaded after the session closes — it raises `MissingGreenlet`. The fix is to always use `selectinload` for relationships that will appear in the response, and to reload the object after creation before returning it.

The evidence download had a similar issue: the `file_data` column is deferred to avoid loading binary blobs in list queries. But when downloading, we need to explicitly load it. The service uses `db.execute(select(Evidence).where(...).options(undefer(Evidence.file_data)))` for download requests.

**"Why FastAPI over Django?"**
FastAPI is async-native. Every database operation in LBRO is awaitable. With Django (pre-5.x), async database access requires workarounds. FastAPI also generates OpenAPI documentation automatically from type hints — the same Pydantic models used for validation become the API spec without any extra configuration.

**"How does the RBAC work?"**
Three roles (admin, analyst, viewer). The canonical permission map is in `core/rbac.py` — one dict that maps each role to a set of permission strings. Every protected endpoint uses `require_permission(permission)` as a FastAPI dependency. No route handler ever compares role strings. The permissions are embedded in the JWT so the frontend can also use them for navigation gating.

**"Why store evidence in PostgreSQL instead of S3?"**
For the initial version, eliminating S3 as a hard dependency for core functionality reduces operational complexity. The `file_data` column uses SQLAlchemy's `deferred` loading, so binary blobs are never loaded on list queries — only on explicit download requests. At scale (hundreds of GBs of evidence), we would migrate to S3 and store only the S3 key in the database. The schema already has `s3_key` and `s3_bucket` columns for this migration path.

**"What is MSW and why use it?"**
Mock Service Worker is a library that installs a browser service worker to intercept HTTP requests in development. When `VITE_MOCK=true`, the frontend behaves exactly as it would against a real backend — same Axios client, same request interceptors, same error handling — but every API call returns a realistic mock response. This means frontend development never blocks on backend availability, and the entire frontend can be demonstrated without any running infrastructure.

**"How do you handle token expiry?"**
Access tokens expire in 30 minutes. When the Axios response interceptor receives a 401, it checks whether it already has a refresh token. If yes, it calls `/api/v1/auth/refresh` once (deduplicating concurrent 401s with a shared Promise), gets a new access token, updates the in-memory store, and retries the original request — transparently to the user. If the refresh also fails (expired or revoked), it calls `logout()` and redirects to `/login`.

**"Why HS256 instead of RS256 for JWT signing?"**
For a single-service architecture where both the token issuer and the token verifier are the same FastAPI application, HS256 with a sufficiently long secret key is appropriate and simpler to manage. RS256 would be needed if we were issuing tokens that need to be verified by third-party services (like a separate frontend CDN or microservices). If LBRO evolves to a multi-service architecture, RS256 would be the right choice.

### Architecture Decisions and Tradeoffs

| Decision | What We Chose | What We Rejected | Reason |
|---|---|---|---|
| Token storage | Module-level memory | localStorage, Zustand state | localStorage is XSS-accessible; Zustand persist has a getter-to-null bug that makes the interceptor read null |
| Evidence storage | PostgreSQL LargeBinary | S3 | Simpler local dev, no AWS dependency for V1 |
| Rate limiting | In-memory sliding window | Redis | Simpler for single-process; TODO: Redis for multi-replica |
| PDF generation | ReportLab | headless Chrome/Puppeteer | ReportLab is pure Python, no browser dependency, deterministic output |
| ML training data | CICIDS2017 | NSL-KDD, UNSW-NB15 | Largest publicly available labeled dataset for network intrusion; covers the most attack classes |
| Background jobs | SQS + long-polling worker | Celery + Redis | SQS is a managed service with retry, DLQ, and exactly-once delivery guarantees; no Redis required |
| Database | PostgreSQL | MySQL, SQLite | JSONB for flexible feature storage, LISTEN/NOTIFY potential, strong async driver support (asyncpg) |

---

## 16. Known Technical Debt

### Current Limitations

**In-memory rate limiter** — The sliding-window rate limiter stores counters in process memory using Python `defaultdict`. In a multi-replica ECS deployment (which is the production configuration), each replica has its own counter — a user can hit 10x the limit by round-robining across replicas. Must be migrated to Redis before horizontal scaling.

**Model file not in repository** — The trained scikit-learn pickle file is not included in the codebase and is not built into the Docker image. Production deployment requires either training the model as part of the build pipeline or storing the pickle in S3 and downloading it on startup.

**SMTP not configured in local dev** — The notification worker sends emails via SMTP, but the local Docker Compose stack has no SMTP server. Notifications can be approved and marked as sent via the database, but actual email delivery requires configuring `SMTP_HOST`, `SMTP_USER`, and `SMTP_PASSWORD`.

**Evidence at scale** — PostgreSQL `LargeBinary` storage works well for small teams. The `file_data` column is deferred (not loaded on list queries), but large evidence files will still impact backup size, WAL volume, and restore times. Migration path to S3 is designed in (the `s3_key` and `s3_bucket` columns already exist).

**No pagination cursor** — The incidents and evidence list endpoints use offset pagination (`page` + `page_size`). At large row counts, offset pagination becomes slow. Migration to cursor-based pagination (using `created_at` + `id` as a composite cursor) would improve performance.

**Token revocation table cleanup** — The `revoked_tokens` table accumulates entries until they are manually purged. There is no background task that removes expired JTIs. A periodic cleanup job (Celery beat or a cron-triggered ECS task) should delete rows where `expires_at < NOW()`.

**Frontend uses mixed data-fetching patterns** — Some pages use React Query hooks from `useApi.ts`; others use raw `useEffect`/`useState` with Axios calls. This inconsistency makes it harder for new developers to know which pattern to follow. Standardizing on React Query for all server state would improve cache consistency and loading state handling.

**Core/config.py is a legacy shim** — `app/core/config.py` is deprecated (it re-exports from `app/config.py`) and exists only to avoid breaking `app/worker/` and `app/api/` legacy directories. These directories and the shim should be removed.

**No SMTP template system** — Notification emails use Python f-strings for body generation. A proper template system (Jinja2 + HTML templates) would allow non-engineers to modify notification content without code changes.

### Scaling Considerations

- **Database connection pool** — Default pool size is 10 with max overflow of 20. At high concurrency, increase `DATABASE_POOL_SIZE` and consider PgBouncer for connection pooling in front of RDS.
- **ECS task sizing** — API tasks default to 512 CPU / 1GB RAM. ReportLab PDF generation is CPU-intensive; consider bumping to 1024/2GB for the API in production.
- **SQS long-polling** — The worker uses 20-second long-polling. If incident volume is high, scale worker replicas and reduce the poll interval.
- **CloudWatch logging costs** — Structured JSON logs can be verbose. Consider sampling at high volume using structlog's sampling processor.

---

## 17. Developer Handoff

### Getting the Environment Running

```bash
# 1. Clone the repository
git clone <repo-url> lbro
cd lbro

# 2. Copy environment template
cp .env.example .env

# 3. Generate a secret key and update .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"

# 4. Build and start all services
docker compose up --build

# Wait for all services to be healthy (about 60–90 seconds first time)

# 5. Seed the admin user
docker compose run --rm seed

# 6. Open the app
open http://localhost:3000
# Login: admin@lbro.local / Admin123!

# 7. Load demo data (optional but recommended for development)
docker compose run --rm api python /scripts/seed_demo_data.py
```

### Running the Frontend in Mock Mode

```bash
cd frontend
npm install
npm run dev:mock
# http://localhost:5173
```

This starts the Vite dev server with Hot Module Replacement and MSW intercepting all API calls. No backend needed. Changes to any frontend file are reflected in the browser within milliseconds.

### Running Backend Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Tests use SQLite in-memory via `conftest.py` which sets `DATABASE_URL=sqlite+aiosqlite:///:memory:` before the app imports. No PostgreSQL is needed for tests.

### Making Changes

**Adding a new backend endpoint:**
1. Add the route handler in the appropriate router in `app/routers/`
2. Add or extend the schema in `app/schemas/`
3. Add the business logic in `app/services/`
4. Add the permission check: `require_permission(Permission.YOUR_PERMISSION)` in the route dependency
5. Write a test in `tests/`
6. Add a mock handler in `frontend/src/mocks/handlers/` if you want mock mode to work
7. Add the API call function to `frontend/src/api/client.ts`

**Adding a new frontend page:**
1. Create `frontend/src/pages/YourPage.tsx`
2. Add the route to `frontend/src/routes/AppRouter.tsx` with appropriate `ProtectedRoute` and `requiredPermission`
3. Add the navigation link to `frontend/src/components/layout/Sidebar.tsx` with a `useCan(Permission.YOUR_PERMISSION)` guard
4. Add mock data to `frontend/src/mocks/handlers/` if needed

**Adding a new database table:**
1. Create the ORM model in `backend/app/models/`
2. Export it from `backend/app/models/__init__.py`
3. Create an Alembic migration: `alembic revision --autogenerate -m "add_your_table"`
4. Review the generated migration in `backend/app/migrations/versions/`
5. Apply: `alembic upgrade head`

### Key Files to Understand First

If you are new to the codebase, read these files in order:
1. `backend/app/core/rbac.py` — the permission model
2. `backend/app/config.py` — all configuration options
3. `backend/app/main.py` — how the app is assembled
4. `backend/app/dependencies.py` — how auth and RBAC work in practice
5. `frontend/src/store/authStore.ts` — how frontend auth state works
6. `frontend/src/api/client.ts` — how every API call is made
7. `frontend/src/routes/AppRouter.tsx` — the full route map

### Code Conventions

- **Backend:** All async. Route handlers are thin. Business logic is in services. Never compare role strings — always use `Permission` enum. Every new endpoint needs `require_permission(...)`.
- **Frontend:** Permission checks via `useCan()` hook for UI visibility. All API calls through `api/client.ts` typed functions. Access token is read via `getAccessToken()` from memory, never from Zustand state.
- **Logs:** `logger.info("event_name", key=value, ...)` — snake_case event names, keyword args for structured fields. Never log secrets, tokens, or PII.
- **Migrations:** Alembic auto-generate, then manually review. Never run `--autogenerate` in production without reviewing the output.

### Local Troubleshooting

**"Cannot connect to database"** — The `migrate` service runs before `api`. If migrations fail (e.g., syntax error in a migration file), the API will refuse to start. Check `docker compose logs migrate`.

**"MSW handlers not intercepting"** — The service worker must be registered before React renders. Check `main.tsx` — the `startWorker()` call must complete before `ReactDOM.createRoot`. If you see console warnings about unhandled requests, you need to add a handler in `src/mocks/handlers/`.

**"TypeScript errors after backend change"** — TypeScript types in `src/types/index.ts` and `src/api/client.ts` must be kept in sync with backend Pydantic schemas. Run `npm run type-check` to see all current errors.

**"PDF download not working in dev:mock"** — The mock PDF uses a native `<a href="data:..." download>` element, not JavaScript. Confirm you are clicking the `<a>` element, not a `<button>`. The `isMock` condition must evaluate to `true` — check that `VITE_MOCK=true` is in `.env.mock` and you are running `npm run dev:mock`.

---

*This document is the single source of truth for the LBRO engineering team. Update it whenever the architecture changes, a new feature ships, or a significant technical decision is made.*

*Last reviewed: July 2026 · Version: 2.0.0*
