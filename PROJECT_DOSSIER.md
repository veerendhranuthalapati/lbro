# LBRO: Technical Due-Diligence Dossier (refreshed)

**Refreshed:** 2026-11-03, against branch `release/production-ready` (HEAD `acf5d87`, plus uncommitted working-tree changes listed in section 9).
**Supersedes:** the 2026-11-01 dossier. The earlier version marked `/health/ready` as missing and reported 653 backend tests. Both are now out of date.

---

## 1. Executive summary

LBRO (Law-aware Breach Response Orchestrator) is a security incident response platform. It has a React 18 + Vite + TypeScript SPA, a FastAPI backend on PostgreSQL 16, SQS-driven workers for ML classification and notification retries, and Terraform for AWS. Its features include incident lifecycle management, GDPR/HIPAA/DPDPA notification deadlines, evidence with chain of custody, audit logging, multi-project tenancy, and an ML network-flow classifier.

**Maturity:** Production-hardened demo. Session 3 of the production-readiness run gave a verdict of **READY WITH CONDITIONS**. Nothing has been pushed to GitHub.

**Blocking conditions for release:**
1. The full Compose lifecycle smoke test (gate G5) has not been run. Only a partial smoke has passed.
2. Gates G14 (Playwright integration tests) and G15 (login performance, 20 runs) have not been started.
3. The ML bundle has uncommitted changes that have not been reviewed (section 9).

---

## 2. Project identity

| Field | Value |
|---|---|
| Name | LBRO, Law-aware Breach Response Orchestrator |
| Domain | Cybersecurity, GRC, SOC tooling |
| Users | SOC analysts, security admins, integrators sending events via project API keys (`proj_*`) |
| Repo | `github.com/veerendhranuthalapati/lbro` (contributors: Kedarnath, veerendhranuthalapati) |
| Context | Academic and portfolio project. `LBRO_IEEE_Paper.tex` is the paper. |
| License | **None yet.** Owner has deferred the decision (section 6). |

---

## 3. Stack

| Layer | Technology | Where |
|---|---|---|
| API | Python 3.12, FastAPI 0.141.1, Uvicorn 0.32.1, SQLAlchemy 2.0.36 + asyncpg, Alembic 1.14.0 | `backend/app/`, `docker/Dockerfile.api` |
| Auth | PyJWT 2.15.0, passlib + bcrypt, cryptography 50.0.0 | `app/core/security.py`, `app/dependencies.py` |
| ML | scikit-learn 1.7.2, numpy 1.26.4, joblib | `app/ml/` |
| Reports | reportlab 4.2.5 | `app/routers/reports.py` |
| Frontend | React 18, Vite 6, TypeScript 5.3, Tailwind, Radix, TanStack Query, Zustand, Axios | `frontend/src/` |
| Frontend tests | Vitest + RTL, MSW | `frontend/src/test/` |
| Data | PostgreSQL 16 (prod and Compose), SQLite (backend tests) | `docker-compose.yml`, `tests/conftest.py` |
| Local AWS | LocalStack 3.4 | `docker-compose.yml` |
| Edge | nginx serves SPA and proxies `/api/` | `frontend/nginx.conf` |
| IaC | Terraform AWS ~> 5 (ECS, RDS, S3, SQS) | `terraform/` |
| CI/CD | GitHub Actions. Deploy only on `workflow_dispatch` or `v*` tags. | `.github/workflows/` |
| Lint and security | Ruff, ESLint, Bandit, gitleaks, pip-audit, Trivy (CI) | CI, `.gitleaks.toml` |

Redis is referenced in config (`REDIS_URL`) but **not used**. Rate limiting is in-memory.

---

## 4. Repository layout

```
lbro/
├── backend/app/       core, middleware, ml, migrations (001–018), models, routers, schemas,
│                      services, integrations (new), workers/ (active), worker/ (legacy, see §8)
├── backend/tests/     pytest suite
├── frontend/src/      React SPA (src/pages, src/components, src/api, src/store)
├── docker/            Dockerfile.api, Dockerfile.worker
├── docker-compose.yml, docker-compose.prod.yml
├── scripts/           seed.py, run_migrations.py, compose_smoke.ps1, perf/, Docker validators
├── sdk/               client SDKs (go, java, nodejs, python)
├── agent/             lbro_agent.py (log shipper)
├── terraform/         main.tf, variables.tf, modules/, environments/
├── ml_evaluation/     demo-synthetic metrics and plots (not production claims)
├── docs/              ADRs, runbook, deployment, classification notes
└── *.md, *.docx, *.pdf  audit, certification and handbook documents (see §7)
```

---

## 5. Architecture and runtime

```
Browser → nginx:80 → /api/* → FastAPI:8000 → PostgreSQL 16
                                          → S3 / LocalStack (legacy evidence fields, reports)
                                          → SQS → app.workers.main (classify, notifications)
External app → Bearer proj_* → POST /api/v1/events → SecurityEvent → inline ML → optional Incident
```

**Entry points**

| Process | Command |
|---|---|
| API | `uvicorn app.main:app` (Docker: 2 workers, uvloop) |
| Worker | `python -m app.workers.main` (Docker `CMD`, `docker/Dockerfile.worker`) |
| Migrations | `python scripts/run_migrations.py` (Compose `migrate` service) |
| Seed | `python scripts/seed.py` (Compose `seed` service) |
| Agent | `python agent/lbro_agent.py` |

**Probes:** `GET /health` is liveness. `GET /health/ready` now exists (`app/main.py:213`), which closes AUD-001.

**Known architectural limits:** The SSE event bus (`/events/stream`) and the rate limiter are both in-memory, so they only work correctly on a single API replica.

---

## 6. Authentication, authorization and security

- Humans log in with email and password and receive a JWT (HS256, 30-minute access token, per `config.py:46`). Logout revokes the token's `jti` via `revoked_tokens`.
- Event ingestion uses `Bearer proj_*` only. The legacy `X-API-Key` path still exists for the human-facing API.
- RBAC: platform `super_admin` plus project-level `admin`, `analyst` and `viewer` (`app/core/rbac.py`). Denied requests are written to the audit log.
- Rate limit: 60 requests per minute per IP by default (`config.py:87`), stricter on auth paths. Disabled when `ENVIRONMENT=test`.
- Security headers come from middleware plus nginx (CSP and HSTS). The CSP currently allows `unsafe-inline` scripts.
- MFA: schema fields exist, but there is no TOTP flow.
- Seed accounts use documented default passwords and must be changed before any exposed deployment.

**Security scan status (session 3):** gitleaks found 0 leaks across 68 commits. Bandit reports 0 High and 5 Medium findings. `pip-audit` on the pinned `backend/requirements.txt` reports **no known vulnerabilities** (see section 8.2). Per session 3, `npm audit --omit=dev` shows no production findings. Three dev-only npm findings are documented in `NPM_AUDIT_CLASSIFICATION.md`.

---

## 7. Documentation inventory

The repo root holds a large set of audit, certification and handbook files. Many of them overlap, and some exist in several formats (for example, the engineering handbook is present as .md, .docx and .pdf). The current source of truth for status is `PROGRESS.md`, `FINAL_REPORT.md`, `AUDIT_REPORT.md`, `KNOWN_RISKS.md` and `SKIPPED.md`. This dossier and `README.md` are the other two references. Several older audit reports should be archived, but that decision is still open (section 9).

---

## 8. Known gaps and cleanup status

### 8.1 Resolved since the 2026-11-01 dossier

| Item | Resolution |
|---|---|
| `GET /health/ready` missing | Implemented in `app/main.py` (AUD-001) |
| Vite config timestamp clutter (44 files in `frontend/`) | Deleted. A `.gitignore` rule was added so they don't reappear. |
| python-jose flagged by pip-audit | Not a project dependency. See 8.2. |
| Backend test count | 763 passed, 1 skipped, 1 deselected (session 3 log). This replaces the earlier 653. |

### 8.2 python-jose finding (resolved as a dev-environment artifact)

`python-jose 3.3.0` does not appear in `backend/requirements.txt`, `requirements-dev.txt` or `pyproject.toml`, and nothing in `backend/app`, `backend/tests` or `scripts` imports `jose`. It was installed only in the local Windows `backend/.venv`. Running `pip-audit -r backend/requirements.txt` on the pinned set returned **"No known vulnerabilities found"**. The finding came from the developer's local environment, not from the shipped dependency tree.

Recommended housekeeping: run `pip uninstall python-jose` in `backend/.venv`, then re-run `pip-audit -r requirements.txt` to confirm.

### 8.3 Remaining gaps

| Gap | Severity | Notes |
|---|---|---|
| Full Compose smoke (G5) not run | **Release blocker** | Sandbox cannot pull base images (Docker Hub returns 403). Needs a machine with registry access. |
| G14 Playwright and G15 login perf not run | Release blocker | Not started |
| Legacy `app/worker/` package | Medium | Not used by Docker. Imports undefined settings (`SQS_QUEUE_URL`) and an invalid enum (`IncidentStatus.CONTAINING`). Contains `containment.py`, which has the EC2/SSM TODO. Should be merged or removed. |
| Two DB engine definitions | Low | `app/database.py` (used by the API) and `app/core/database.py` (used by the legacy worker) |
| EC2/SSM containment | Stub | `app/worker/containment.py:176` TODO. Terraform validated but never applied. |
| SSE and rate limiter in-memory | Medium | Single-replica only |
| Compliance rules unreviewed | Medium | `review_status: unreviewed`. Attack-guide content also unreviewed for legal and comms. |
| CICIDS2017 model | Medium | Shipped bundle is `demo-synthetic`. Do not use its metrics for compliance or marketing claims. |
| mypy | Low | 49 errors on full `app/`. Not a CI gate. |
| README drift | Low | README documents a 1-hour JWT expiry and a 100/min rate limit. Config uses 30 minutes and 60/min. Login is described as API-key login in places, but it is email and password. |

---

## 9. Working tree state (needs review before commit)

The branch has **17 modified tracked files, 44 deleted tracked files (the Vite timestamp files removed on 2026-11-03), a modified `.gitignore`, and 30 untracked paths**. Nothing has been committed or pushed. The notable items are:

- **ML bundle (review first).** `backend/app/ml/models/bundle/` has modified `model.joblib` (2.5 MB → 4.6 MB), `preprocessing.json`, `classes.json`, `manifest.json` and `manifest.sig`. This does not match the "demo-synthetic, tests don't modify tracked files" claim in `PROGRESS.md`. Determine whether this came from a deliberate retrain or from a test run, and confirm that the signature still validates before committing.
- **Application changes.** Modified files include `config.py`, `models/incident.py`, `routers/events.py`, `routers/incidents.py`, `schemas/incident.py`, `docker-compose.yml`, `nginx.conf`, and several frontend incident components and pages.
- **New files.** `backend/app/integrations/`, migration `018_integration_context.py`, `services/incident_presenter.py`, `tests/test_realistic_event_ingestion.py`, `docs/REALISTIC_INTEGRATION_TESTING.md`, and `deliverable_staging/`.

---

## 10. Open owner decisions

1. **License:** deferred. The repo currently has no LICENSE.
2. **Worker consolidation:** merge or remove `app/worker/`?
3. **Evidence storage:** PostgreSQL bytea, S3 WORM, or both? The README and the implementation disagree.
4. **Redis:** adopt for rate limiting and SSE, or document single-replica operation?
5. **MFA:** build TOTP, or remove MFA from the security score?
6. **Readiness probe contents:** should `/health/ready` check DB, SQS and the ML bundle?
7. **Doc archive:** which older audit and certification files should move to `docs/archive/`?

---

## 11. Verification log

| Check | Result | Date |
|---|---|---|
| gitleaks | 0 leaks (68 commits) | session 3 |
| Backend pytest | 763 passed, 1 skipped, 1 deselected | session 3 |
| Frontend lint, type-check, Vitest (75), build | Pass | session 3 |
| Ruff (CI paths) | Pass | session 3 |
| pip-audit on pinned `backend/requirements.txt` | No known vulnerabilities | 2026-11-03 |
| Compose smoke (G5) | Partial only. Full lifecycle not run. | session 3 |
| Terraform validate | Not re-run this refresh. Never applied. | — |
