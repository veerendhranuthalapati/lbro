# LBRO Engineering Audit
**Reviewer:** Principal Software Engineer / Security Architect / DevOps Engineer  
**Date:** 2026-07-03  
**Scope:** Full monorepo — backend, frontend, auth, RBAC, ML, deployment, infrastructure, security, UX, code quality  
**Instruction:** No code modifications. Brutally honest. Treat as a pre-ship design review.

---

## 1. Executive Summary

| Dimension | Score |
|---|---|
| Architecture | 7.5 / 10 |
| Security | 5.5 / 10 |
| Backend | 7.0 / 10 |
| Frontend | 7.0 / 10 |
| UX | 5.5 / 10 |
| Deployment | 6.5 / 10 |
| Maintainability | 7.5 / 10 |
| **Overall Production Readiness** | **6.0 / 10** |

LBRO is a technically ambitious full-stack security platform with a well-structured FastAPI async backend, a clean React 18/TypeScript frontend, and a thoughtfully layered RBAC system. For a solo or small-team project, the architectural decisions above the line — async ORM, JWT in memory, permission-based guards, audit-logged 403s — are genuinely good.

**However, it is not production-ready today.** Three issues are blockers:

1. **No token revocation.** A stolen refresh token is valid for 7 days with no server-side mechanism to invalidate it. For a security product this is embarrassing.
2. **API key lookup is O(n) over all users.** The current implementation scans every user row and constant-time compares in Python. It will fall over at scale and is architecturally wrong.
3. **MFA is a UI fiction.** The score penalises users who have not enabled MFA. There are no TOTP setup or verify endpoints. The feature does not exist.

Beyond these blockers there are a cluster of medium-priority issues — in-memory rate limiting that breaks across workers, synchronous PDF generation, a SPA navigation hack, no request body size limit — that must be addressed before a public launch.

The new features (Security Score, Incident Explainer, Weekly Report) are well-conceived and correctly implemented. They add real differentiated value for the developer-first target market.

---

## 2. Strengths

### Architecture

- **Async throughout.** SQLAlchemy 2.x async ORM, `asyncpg`, `asyncio.Lock` in middleware. No blocking calls found in the hot path. This is the correct approach for an I/O-bound security platform.
- **Permission-based RBAC, not role-based.** `require_permission(Permission.X)` at every route means adding a role never requires touching router code. `ROLE_PERMISSIONS` is the single source of truth. The pattern is textbook and rare in solo projects.
- **Every 403 is audit-logged with IP, user-agent, path, and reason.** This is production-grade observability for a security product. The `_audit_authz_failure` helper uses `try/except` so a failed audit write never blocks the auth response — correct priority ordering.
- **Alembic migrations properly sequenced** with a `migrate` service in docker-compose that must complete before the API starts. No schema drift risk in CI/CD.
- **Multi-stage Docker build** with a dedicated non-root `lbro` user (UID 1000). Build dependencies do not land in the runtime image.
- **S3 pre-signed URLs for evidence downloads.** Clients never see raw credentials. Expiry is configurable.

### Security (positive)

- **Access token stored only in module-level memory.** The Zustand persist bug (getter → null on spread) is correctly worked around with `_accessTokenMemory`. Tokens never hit `localStorage` and survive only for the tab lifetime.
- **Refresh token in `sessionStorage`**, not `localStorage`. Tab-scoped, automatically cleared on browser close.
- **Timing-safe dummy hash for missing users.** `_DUMMY_HASH` in `auth_service.py` ensures the bcrypt verification runs for unknown emails, preventing timing-based user enumeration. This is a non-obvious security detail done correctly.
- **Account lockout after 5 failures, 15-minute duration.** Enforced server-side, not just client-side. The lockout check runs *before* bcrypt verification, preventing timing side-channels on locked accounts.
- **`hmac.compare_digest` for API key comparison.** Constant-time, correct.
- **`TrustedHostMiddleware` + `SecurityHeadersMiddleware` + CORS.** The security header middleware sets `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy`, `Permissions-Policy`, and a strict production CSP. HSTS is correctly gated to HTTPS connections only.
- **`ALLOW_PUBLIC_REGISTRATION: bool = False`** by default, enforced in the router, not just config. Self-registration returns 403 in production.

### Backend Quality

- **`from __future__ import annotations`** everywhere — consistent forward-reference handling.
- **`@lru_cache()` on `get_settings()`** — settings are instantiated once. Safe for production.
- **`pydantic-settings`** for config validation. The `validate_secret_key` validator rejects the dev default in production environments.
- **Rule-based incident explanation engine** with 16 attack categories. No LLM dependency means no API key exposure, no latency spike, no cost per request, always available offline. This is the right call for v1.
- **`conftest.py` with async test client, 98 passing tests** across auth, incidents, RBAC, and missing-endpoint suites. Test coverage for core paths is meaningful.
- **Structured error responses** with `{"error": "code", "message": "human text"}` shape throughout. Consistent API contract.

### Frontend Quality

- **React Query v5 with typed query key factory.** `qk.incidents`, `qk.securityScore` etc. ensures cache invalidation is type-safe and predictable.
- **Lazy-loaded routes with `Suspense`/`ErrorBoundary`** on every page. A page-level crash does not take down the app.
- **Token refresh interceptor with deduplication.** `_refreshing: Promise<string> | null` ensures concurrent 401s trigger exactly one refresh call. Correct.
- **Exponential backoff retry** for 429 and 5xx. Rate limiting is handled gracefully on the client.
- **Server-side PDF generation with `reportlab`.** Avoids browser print quirks, produces consistent output across devices. The blob URL + fetch with explicit `Authorization` header is the correct pattern when `<a href>` cannot send headers.

---

## 3. Critical Issues

### CRIT-1: No Token Revocation Mechanism

**File:** `backend/app/core/security.py`, `backend/app/services/auth_service.py`

Refresh tokens are stateless JWTs with a 7-day expiry (`REFRESH_TOKEN_EXPIRE_DAYS: int = 7`). There is no `jti` (JWT ID) claim, no server-side refresh token store, and no revocation endpoint. If a refresh token is stolen — via XSS, network interception, or a compromised device — an attacker has 7 days of silent access with no way to stop them short of rotating `SECRET_KEY` (which invalidates every user session globally).

For a security incident response platform, this is a first-principles failure. The product's core users are people who have just been breached. Their session management cannot have this exposure.

**Minimum fix:** Store refresh token JTIs in a DB table (or Redis SET). On every use, verify the JTI is present. On logout or password change, delete it. Add a `POST /auth/logout/all` that purges all JTIs for a user.

---

### CRIT-2: API Key Lookup is O(n) Over All Users

**File:** `backend/app/dependencies.py`, lines 64–76

```python
result = await db.execute(
    select(User).where(User.api_key.isnot(None)).where(User.is_active == True)
)
for candidate in result.scalars().all():
    if candidate.api_key and hmac.compare_digest(candidate.api_key, api_key):
        matched_user = candidate
        break
```

Every API key authenticated request loads every user with a non-null API key into Python memory and iterates. With 10,000 users this is a full table scan on every request. With 1,000,000 users it is an OOM event.

The intent is constant-time comparison to prevent timing attacks, but the correct approach is to store a *hash* of the API key (e.g. `SHA-256(key)`) in the DB, query `WHERE api_key_hash = hash(incoming_key)`, and compare the original in memory only if the hash matches. The hash comparison in the DB is fast and indexed; the in-memory comparison adds timing safety.

The current approach also stores API keys in plaintext in the database. A DB dump leaks every API key immediately.

**Minimum fix:** Add `api_key_hash VARCHAR(64) UNIQUE INDEX` column. Hash keys with `hashlib.sha256`. Look up by hash. Store the plaintext key only in the response to the rotation call.

---

### CRIT-3: MFA is a Schema Column, Not a Feature

**Files:** `backend/app/models/user.py` (`mfa_enabled`, `mfa_secret`), `backend/app/routers/security_score.py`

The `mfa_enabled` and `mfa_secret` columns exist on the User model. The security score deducts points for users without MFA enabled (`-4 per user, cap -20`). The Weekly Report mentions MFA coverage. The frontend Users page presumably shows MFA status.

However: there is no `POST /auth/mfa/setup` endpoint, no `POST /auth/mfa/verify` endpoint, and no TOTP QR code generation. No user can actually enable MFA through any supported flow. The score is penalising users for a feature that does not exist.

**This is a product integrity issue.** The score is telling users something is wrong when there is no fix available within the product. It erodes trust immediately.

**Minimum fix (if MFA is not being built now):** Remove MFA from the security score calculation and the weekly report until the feature is implemented. Do not surface metrics for non-existent features.

---

## 4. High Priority Improvements

### HIGH-1: Rate Limiter Does Not Work Across Workers

**File:** `backend/app/middleware/rate_limit.py`

The module docstring reads: *"In-memory sliding-window rate limiter middleware (Redis-backed in production)."* The implementation uses `_windows: dict[str, deque]` — a process-local dictionary. The Dockerfile runs `uvicorn --workers 2`, which forks two separate processes, each with their own `_windows`. A client can exceed the rate limit by round-robin-ing between workers.

Redis is configured in `settings.REDIS_URL` but is never connected to by the rate limiter. The "Redis-backed in production" claim in the docstring is aspirational, not actual.

**Fix:** Either connect to Redis from the middleware (use `aioredis` / `redis.asyncio`), or document clearly that rate limiting is per-worker and set `--workers 1` until this is resolved.

---

### HIGH-2: `SECRET_KEY` Generates a New Value on Every Cold Start

**File:** `backend/app/config.py`

```python
SECRET_KEY: str = secrets.token_urlsafe(32)  # MUST be overridden via env in production
```

If `SECRET_KEY` is not set in the environment, a new random key is generated on *every* process startup. In the docker-compose setup the key is hardcoded as `dev-secret-key-change-in-production-minimum-32-chars`, which is fine for development. But if someone deploys without setting `SECRET_KEY`, every container restart invalidates all active sessions — all users are logged out silently.

The `validate_secret_key` validator correctly rejects the dev default in production, but only if `ENVIRONMENT=production` is set. If `ENVIRONMENT` is not set (defaults to `"production"` in the `Settings` class) but `SECRET_KEY` is also not set, the validator would run against a freshly generated key and pass — because it only checks for the known bad values, not for the "was this value set by the user" case.

**Fix:** Add a startup check that raises an error if `SECRET_KEY` equals `secrets.token_urlsafe(32)` (i.e., it was never overridden). Or require `SECRET_KEY` to have a `min_length` sentinel checked against environment-provided value.

---

### HIGH-3: SPA Navigation Hack in SecurityScorePage

**File:** `frontend/src/pages/SecurityScorePage.tsx`, lines 136–138

```javascript
window.history.pushState({}, '', rec.link)
window.dispatchEvent(new PopStateEvent('popstate'))
```

This manually fires a `popstate` event to trigger React Router navigation. It is fragile:

- React Router v6 uses its own internal history listener; `popstate` events from user code are handled inconsistently.
- It bypasses `ProtectedRoute` and the lazy-loading `SuspenseRoute` wrapper.
- It will break if React Router's internals change in a patch version.
- It produces no TypeScript type safety on `rec.link`.

The correct fix is to pass `useNavigate` into the component and call `navigate(rec.link)` directly. This is a one-line change per recommendation card click.

---

### HIGH-4: PDF Generation Blocks the Request Thread

**File:** `backend/app/routers/reports.py`

`GET /reports/weekly/pdf` calls `_generate_pdf()` synchronously inside an async FastAPI endpoint. `reportlab` is a synchronous CPU-bound library. This blocks the entire uvicorn worker for the duration of PDF generation. With a large dataset and complex layout, this could easily take 2–5 seconds, starving all other requests on that worker.

**Fix:** Wrap the call in `asyncio.to_thread(_generate_pdf, data)` or `loop.run_in_executor(None, _generate_pdf, data)` to move it off the event loop thread.

---

### HIGH-5: No Request Body Size Limit

**File:** `backend/app/main.py`

FastAPI / Starlette has no default maximum request body size. An unauthenticated attacker can POST a 1 GB body to `/api/v1/auth/login` and exhaust worker memory. There is no upload size guard anywhere in the middleware stack.

**Fix:** Add a middleware or configure uvicorn's `limit_max_requests` / `limit_concurrency`. For the evidence upload endpoint specifically, add a FastAPI `UploadFile` size validation guard.

---

### HIGH-6: `network_features: JSON` Column Has No Schema or Size Limit

**File:** `backend/app/models/incident.py`

The `network_features` column accepts arbitrary nested JSON with no validation, no depth limit, and no size cap. An authenticated user with `CREATE_INCIDENT` permission can store megabytes of arbitrary data in a single incident. This is both a storage abuse vector and a denial-of-service risk.

**Fix:** Add a Pydantic schema for `network_features` in `schemas/incident.py` and enforce it at the endpoint level. Add a `CHECK` constraint or application-level size validation.

---

### HIGH-7: Security Score Leaks Sensitive Metrics to All Roles

**File:** `backend/app/routers/security_score.py`

The endpoint requires `Permission.VIEW_DASHBOARD`, which every role holds (viewer, analyst, admin). The response includes: count of open critical incidents, count of users without MFA, count of users with failed logins, count of locked users, and count of recent 403 bursts.

A viewer role is intended for read-only observation. Giving every viewer a real-time intelligence dashboard about organisational security posture — including active attack indicators — may violate need-to-know. Consider requiring at least `Permission.READ_INCIDENT` or `Permission.VIEW_AUDIT` for the full snapshot, and returning only the aggregate score to viewers.

---

## 5. Nice-to-Have Improvements

### NICE-1: No Structured Logging

`structlog` is installed (visible in the `.venv`). The application uses `logging.basicConfig(format="%(asctime)s %(levelname)s ...")` — plain text logs. In production, ingesting plain-text logs into CloudWatch / Datadog requires custom parsers. Structured JSON logs (`structlog.get_logger()`) are machine-readable out of the box.

### NICE-2: Security Score Runs 9 DB Queries Per Request, Every 60 Seconds Per User

With 10 concurrent users, the security score endpoint fires 90 DB queries every 60 seconds at idle. The data changes infrequently. A 60-second Redis TTL cache on the result would reduce this to 9 queries per minute total regardless of active users.

### NICE-3: No Onboarding Flow for New Users

A new user logging in for the first time sees the dashboard, which renders empty state with no guidance. There is no "first-run wizard", no sample data, no tooltip tour. For a product targeting students and indie developers, the empty-state experience is a conversion risk. People who see nothing assume the product is broken.

### NICE-4: `role` Is Stored as `String(50)`, Not a DB Enum

The `User.role` column accepts any string up to 50 characters. The Python RBAC layer validates it, but nothing prevents a raw SQL INSERT with `role = 'superadmin'` from succeeding. A `PostgreSQL ENUM` type or a `CHECK (role IN ('admin', 'analyst', 'viewer'))` constraint would enforce this at the DB level.

### NICE-5: Refresh Token Rotation Does Not Invalidate the Old Token

In `auth_service.refresh()`, a new refresh token is returned but the old one is never invalidated (there is no revocation store). If a refresh token is intercepted in transit, both the attacker and the legitimate user can refresh indefinitely.

### NICE-6: No `Content-Security-Policy` `nonce` or Hash for Inline Scripts

The production CSP sets `script-src 'self'`, which is strict. However, Vite injects inline scripts for module preloading. Without a nonce or hash, the frontend will likely violate its own CSP in production. This should be tested end-to-end with CSP reporting enabled before shipping.

### NICE-7: OpenAPI Schema Disabled in Production — No Versioned API Spec

```python
docs_url="/docs" if settings.DEBUG else None,
openapi_url="/openapi.json" if settings.DEBUG else None,
```

Disabling Swagger in production is a reasonable security default. However, there is no alternative versioned API spec (e.g., a committed `openapi.json`). External consumers (integrations, SDK generators, third-party SIEM connectors) have no machine-readable contract.

---

## 6. Product Review

### What Works Well

The product pivot to "developer-first post-deployment security companion" is correct and well-timed. The three new features shipped in this session — Security Score, Incident Explainer, Weekly Security Report — are exactly the right things for a v1 that targets developers who built something with an AI tool and now need to understand what's happening in production.

The Security Score is the standout feature. It gives an immediate, plain-English answer to "how secure am I right now?" with actionable recommendations and navigation links. The grade system (A–F) with colour coding is universally understood. The 60-second auto-refresh makes it feel live.

The Incident Explainer is genuinely differentiated. OWASP + MITRE ATT&CK mappings, business impact vs. technical impact, numbered fixes — this is the kind of output a developer needs when they have no security background but got paged at 2 AM. The rule-based engine is the right call: fast, offline, deterministic, no API key, no hallucinations.

### What Needs Work

**The sidebar.** Thirteen icon-only navigation items with no labels. On a 13-inch laptop at 100% zoom, this is visually overwhelming and none of the icons are self-documenting enough to be unambiguous without the tooltip. Consider collapsible labels or grouping items into sections (Monitoring, Response, Governance, Settings).

**Empty states.** Every page that makes an API call but gets back an empty array renders a blank area with no message. A developer evaluating the product for the first time sees nothing and assumes it's broken. Every list page needs an empty-state component with a clear message and a primary action ("No incidents yet. Run a scan or simulate an event →").

**Compliance page is overwhelming for indie devs.** GDPR, HIPAA, DPDPA deadline tracking is enterprise-level compliance management. A solo developer shipping a weekend project does not have a DPO. This section needs either: a simplified "does this apply to me?" onboarding filter, or a clear toggle to hide compliance features that don't apply to the user's context.

**No self-serve demo mode.** There is a `seed.py` script that creates an admin user, but no seed for demo incidents, compliance records, or evidence. New users evaluating the product see all zeroes. A "Load demo data" button on an empty dashboard would dramatically improve first-run conversion.

**The product name and URL are under-defined.** "Law-aware Breach Response Orchestrator" is an enterprise SIEM acronym. The new positioning is "developer-first security companion." The name, the landing page copy (in the README), and the sidebar brand mark still reflect the old positioning. These should be aligned.

---

## 7. Interview Review

**This project would impress a senior engineer at the architecture layer.** The RBAC implementation is better than what most mid-sized companies ship. JWT memory storage with the Zustand getter-override fix shows attention to non-obvious security detail. The async ORM pattern, the audit-logged permission system, and the `_DUMMY_HASH` timing attack mitigation are all signs of genuine security thinking.

**However, a senior interviewer would immediately catch:**

**1. The O(n) API key scan.** This is the kind of bug that makes an interviewer question whether the candidate has thought about scale. It should be the first thing fixed if this project is being used as a portfolio piece.

**2. `window.history.pushState + popstate` for React Router navigation.** An interviewer who knows React Router v6 will raise an eyebrow. The correct answer is `useNavigate`. Using low-level browser APIs to work around a framework's navigation primitives signals unfamiliarity with the framework.

**3. "MFA-enabled" in the schema but no MFA flow.** If shown in an interview, the question "how does a user enable MFA?" has no answer. This suggests a feature was started and not finished, which is worse than not starting it.

**4. No token revocation for a security product.** An interviewer focusing on security architecture will ask "what happens if I steal a session token?" If the answer is "wait 7 days," that's a fundamental design gap in something marketed as a security tool.

**Strengths that would stand out in an interview:**
- The `_audit_authz_failure` pattern — observability-first thinking
- `require_permission` as a dependency factory — clean FastAPI idiom, correct separation
- React Query key factory — shows familiarity with caching patterns
- The incident explainer engine — pragmatic over flashy (rule-based vs LLM)
- 98 passing tests with RBAC coverage — you can claim confidence in the auth system

---

## 8. Code Review

### Poor Practices

**`api_key` stored in plaintext (User model).**  
Passwords are bcrypt-hashed. API keys are stored raw. This is an inconsistency that creates a DB-dump credential leak risk. All secrets that authenticate a user must be hashed before storage.

**Hardcoded `_DUMMY_HASH` in `auth_service.py`.**  
```python
_DUMMY_HASH = "$2b$12$KIXOg5OcV2I8k/fNEaGm8uLK7s1Q1xXzQ0tYOF9n5Q6k4F3v9KBSW"
```
This is a constant bcrypt hash of an unknown password. If this hash ever gets cracked (bcrypt is slow but not impossible) or if a future version of passlib changes how `verify_password` handles this string, the timing protection silently breaks. Better: generate a fresh bcrypt hash at startup with `hash_password(secrets.token_hex(32))`.

**`window.history.pushState` + manual `popstate` event (SecurityScorePage.tsx).**  
As noted above, this is a framework bypass anti-pattern. It also makes the navigation untestable with React Testing Library.

**`select(User).where(User.locked_until > now)` with naive timezone comparison.**  
`now` is `datetime.now(timezone.utc)` — timezone-aware. `User.locked_until` is `DateTime(timezone=True)` — stored with timezone in PostgreSQL. This should work, but the comparison depends on PostgreSQL correctly interpreting the timezone. In testing environments using SQLite (if any future test uses SQLite) this comparison would silently fail.

**The `created_by` field on `Incident` is never set by the create endpoint.**  
`created_by` has a FK to `users.id` (`ondelete="SET NULL"`). If the incident creation router does not set this field, every incident has `created_by = NULL`, making audit trails for incident origin impossible.

### Excellent Practices

**`ROLE_PERMISSIONS` as the single source of truth.**  
Adding a new permission to a role is one line in one file. No router changes, no enum changes, no migration needed. This is clean design.

**Deduplication of concurrent token refresh calls.**  
```python
if _refreshing: return _refreshing
```
A classic singleton pattern for async operations. Prevents thundering-herd 401 → refresh → retry scenarios from triggering N refresh calls. Well-executed.

**`partialize` in Zustand persist — access token excluded.**  
```python
partialize: (state): PersistedSlice => ({
    refreshToken: _refreshTokenMemory,  # reads module-level memory
    ...
    # access token intentionally omitted
})
```
The access token is explicitly not persisted. This is correct security posture and shows understanding of what "secure storage" means in a browser context.

**`hmac.compare_digest` for API key comparison.**  
Even though the lookup strategy is flawed (O(n)), the comparison itself uses the correct constant-time function. This shows security awareness at the right level.

**Strict CSP in production, loose in development.**  
The CSP correctly distinguishes environments. Development allows `unsafe-inline` and CDN assets for Swagger UI. Production is strict `self`-only. This is the right trade-off.

### Architectural Improvements to Consider

- **CQRS for security score.** The score is a read-heavy aggregate of slow-changing data. A separate `SecurityScoreSnapshot` table updated by a background job (cron or SQS message) would let the GET endpoint return a single-row read instead of 9 aggregation queries.
- **Event sourcing for incident status.** Instead of updating `status` in place, each state transition appends to `IncidentAction`. The current model does this partially (`IncidentAction` exists) but `status` is still mutable on the `Incident` row. Consider making status derivable from the action log.
- **OpenTelemetry for distributed tracing.** The `X-Request-ID` header is set and logged, but there is no trace propagation across the FastAPI → SQS → Worker boundary. Adding OpenTelemetry would make the system observable without changing the API contract.

---

## 9. Production Readiness Score

| Subsystem | Score | Key Blocker |
|---|---|---|
| Auth & Session Management | 5 / 10 | No token revocation, no MFA implementation |
| RBAC & Authorization | 9 / 10 | Best-in-class for a project of this size |
| Backend API | 7 / 10 | O(n) API key scan, sync PDF, no body size limit |
| Database & ORM | 7 / 10 | No DB-level role enum, `created_by` unset, no UUID index on api_key_hash |
| Frontend | 7 / 10 | SPA nav hack, missing empty states, icon-only sidebar |
| Security Headers & Middleware | 7 / 10 | Rate limiter not Redis-backed, CSP nonce gap |
| Testing | 6 / 10 | 98 tests but no integration tests against real DB, no frontend tests, no load tests |
| Deployment & Infrastructure | 6 / 10 | Terraform exists but untested, no CI/CD pipeline, secret rotation undefined |
| ML Pipeline | 5 / 10 | Model mounted as volume (works), no retraining pipeline, no drift detection |
| Observability | 4 / 10 | Plain-text logs, no metrics endpoint, no tracing, no alerting |
| **Overall** | **6.0 / 10** | |

---

## 10. Action Plan

Ordered by highest impact to lowest effort. Time estimates assume a single developer.

### Sprint 1 — Blockers (Do Before Any Public Launch)

| # | Action | File(s) | Effort |
|---|---|---|---|
| 1 | Replace `pushState` hack with `useNavigate()` | `SecurityScorePage.tsx` | 30 min |
| 2 | Remove MFA from security score & weekly report until TOTP is implemented | `security_score.py`, `reports.py` | 1 hour |
| 3 | Wrap `_generate_pdf()` in `asyncio.to_thread()` | `routers/reports.py` | 30 min |
| 4 | Add request body size limit middleware (e.g. 10 MB) | `main.py` or new middleware | 1 hour |
| 5 | Hash API keys before storage; rewrite lookup to `WHERE api_key_hash = ?` | `models/user.py`, `dependencies.py`, migration | 3 hours |

### Sprint 2 — High Priority (Do in First Month)

| # | Action | File(s) | Effort |
|---|---|---|---|
| 6 | Implement refresh token JTI store (PostgreSQL table) + revocation endpoint | `models/`, `routers/auth.py`, migration | 4 hours |
| 7 | Connect rate limiter to Redis (`redis.asyncio`) | `middleware/rate_limit.py` | 2 hours |
| 8 | Add `CHECK (role IN (...))` DB constraint via Alembic migration | new migration | 1 hour |
| 9 | Set `created_by` in the incident create endpoint | `routers/incidents.py` | 30 min |
| 10 | Add empty-state components to all list pages | `IncidentsPage`, `EvidencePage`, `CompliancePage`, etc. | 3 hours |
| 11 | Replace `_DUMMY_HASH` constant with `hash_password(secrets.token_hex(32))` at startup | `auth_service.py` | 30 min |

### Sprint 3 — Observability & UX

| # | Action | Effort |
|---|---|---|
| 12 | Switch to `structlog` JSON logging + request ID propagation | 2 hours |
| 13 | Add Redis TTL cache (60s) for security score calculation | 2 hours |
| 14 | Add sidebar item labels (collapsible or always-visible on wider screens) | 1 hour |
| 15 | Add "Load demo data" button on empty dashboard | 3 hours |
| 16 | Add OpenAPI spec export step to CI (committed `openapi.json`) | 1 hour |
| 17 | Add GitHub Actions CI: lint → type-check → test → build | 2 hours |

### Sprint 4 — Production Hardening

| # | Action | Effort |
|---|---|---|
| 18 | Implement TOTP MFA setup + verify endpoints | 6 hours |
| 19 | Add Prometheus `/metrics` endpoint + Grafana dashboard | 4 hours |
| 20 | OpenTelemetry trace propagation across API → SQS → Worker | 4 hours |
| 21 | Validate Terraform `prod` environment against real AWS account | 4 hours |
| 22 | Write frontend integration tests (Playwright or Vitest + MSW) | 8 hours |
| 23 | Implement CQRS security score snapshot (background job updates every 5 min) | 3 hours |

---

*End of audit. No code was modified during this review.*
