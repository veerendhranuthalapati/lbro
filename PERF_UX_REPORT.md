# LBRO Performance & UX Report

**Branch:** `perf/login-and-ux` (from `feature/threat-to-obligation` @ `84eb94c`)  
**Machine:** Windows 10 (user workstation), warm runs unless noted  
**Date:** 2026-11-02  

## Executive summary

Login and post-login UX were improved without weakening security: bcrypt verification runs off the asyncio event loop, login responses optionally include a user bootstrap payload (skipping `/auth/me` on the happy path), and the Integrations page gained accessible copy controls, deployment-aware API URLs, error/retry states, and project-admin gating for key rotation. Backend tests grew from **738 → 741** passed; frontend Vitest from **60 → 69**. Docker-backed HTTP benchmarks (after API restart, 8 paced login samples) show login median ~**577 ms** (dominated by bcrypt) while `/health` stayed responsive during 20 concurrent logins (p95 ~**132 ms**).

Playwright cold/warm timelines and Lighthouse CLI runs were **not executed** in this pass (see §Not run).

---

## Before / after measurements

| Metric | Before (Phase 0) | After | Command / notes |
|--------|------------------|-------|-----------------|
| Backend pytest | 738 passed, 1 deselected | **741 passed**, 1 deselected | `cd backend; .\.venv\Scripts\python.exe -m pytest -q` |
| Frontend Vitest | 60 passed | **69 passed** | `cd frontend; npm run test` |
| Bcrypt verify (this machine) | (not recorded Phase 0) | median **490 ms**, p95 **738 ms** (warm) | `python ..\scripts\perf\bcrypt_bench.py` → `perf-scratch/bcrypt_bench.txt` |
| POST `/auth/login` (Docker, warm) | (not recorded; rate limit blocked unpaced 25-run) | median **577 ms**, p95 **1272 ms** (n=8, 0.4s spacing) | API restarted; `measure_login_http.py --runs 8` → `perf-scratch/measure_login_after.json` |
| `/health` during 20 concurrent logins | (not recorded) | median **17 ms**, p95 **132 ms** | same script (concurrent block) |
| Entry chunk `index-*.js` | ~236 KB / **73.7 KB** gzip | **236385 B** / **73.80 KB** gzip | `npm run build` |
| Integrations chunk | ~29 KB / **9.5 KB** gzip | **31.45 KB** / **10.25 KB** gzip | `npm run build` (added a11y copy UI) |
| Post-login `/auth/me` round trip | always | **skipped** when `user` bootstrap present | `LoginPage.tsx`, `auth_service.login` |
| Alembic heads | single | **single** (`017_threat_to_obligation`) | `alembic heads` |

Raw after login JSON:

```json
{
  "label": "after-warm",
  "runs": 8,
  "login_median_ms": 576.7812499980209,
  "login_p95_ms": 1271.631100000377,
  "health_during_20_logins_median_ms": 17.4708999984432,
  "health_during_20_logins_p95_ms": 131.50650000170572
}
```

**Targets (honest):**

- Login p95 ≈ bcrypt cost + overhead: **met** (p95 ~1.27s vs bcrypt p95 ~0.74s on same host, plus DB/JWT).
- `/health` responsive under concurrent logins: **met** (p95 132 ms).
- Login-to-interactive improvement: **partially proven** (one fewer sequential API call; no Playwright click-to-interactive).
- CLS / Lighthouse a11y on three pages: **not measured** (not run).

---

## Changes by phase

### Phase 2 — Faster login

| Change | Files |
|--------|--------|
| Async bcrypt verify/hash via `asyncio.to_thread` | `backend/app/core/security.py` |
| Rehash only when `passlib.needs_update` | `backend/app/services/auth_service.py` |
| Login bootstrap on `TokenResponse.user` (backward compatible optional field) | `backend/app/schemas/auth.py`, `auth_service.py` |
| Skip `/auth/me` when bootstrap present; prefetch dashboard | `frontend/src/pages/LoginPage.tsx`, `frontend/src/api/client.ts` |
| Fix `/auth/me` 500 on seed emails (`EmailStr` → `str`) | `backend/app/schemas/user.py` |
| Entry bundle budget check | `frontend/scripts/check-entry-bundle-budget.mjs`, `package.json` (`check:budget`) |

**Deliberately not changed:** bcrypt cost factor, JWT shape/expiry, rate limits, audit/last_login writes, dummy hash on unknown user, refresh-token storage (memory + existing flow).

### Phase 3 — Integrations page

| ID | Severity | Issue | Cause | Status |
|----|----------|-------|-------|--------|
| INT-01 | High | Inline copy buttons without clipboard fallback or failure feedback | Removed `CopyBtn` | **Fixed** — `IntegrationCodeBlock.tsx` |
| INT-02 | High | Snippets used `window.location.origin` inconsistently | Hard-coded origin | **Fixed** — `getPublicApiOrigin()` |
| INT-03 | Med | No error UI when project fetch fails | Missing `isError` branch | **Fixed** — `IntegrationsPage.tsx` |
| INT-04 | Med | Code blocks overflow on mobile; no wrap toggle | Fixed `pre` styling | **Fixed** — `IntegrationCodeBlock.tsx` |
| INT-05 | Med | Viewers saw Regenerate control | No `my_role` check | **Fixed** — `canRegenerateKey` |
| INT-06 | Low | Reveal/hide key button missing accessible name | icon-only | **Fixed** — `aria-label` |
| INT-07 | Med | Full responsive screenshot matrix | — | **Not run** (no scratch captures) |

### Phase 4 — General smoothness

- **Partial:** dashboard prefetch on login; bundle budget script. SSE throttling / global API dedup not changed in this branch (out of measured benefit for this sprint).

### Tests added

- `backend/tests/test_login_bootstrap.py`
- `backend/tests/test_login_timing.py` (unknown-user timing bound; `/health` under concurrent logins)
- `frontend/src/components/integrations/IntegrationCodeBlock.test.tsx`
- `frontend/src/pages/IntegrationsPage.test.tsx`

---

## Security decisions

| Item | Decision |
|------|----------|
| Lower bcrypt cost | **Rejected** |
| Skip dummy hash on unknown email | **Rejected** — timing test enforces similar medians |
| Remove rate limiting for speed | **Rejected** — Docker benchmarks require pacing / API restart |
| Store access token in localStorage | **Rejected** (unchanged) |
| Embed real API keys in snippets | **Rejected** — placeholders except session one-time key |

## Needs owner decision

- None for security/performance trade-offs implemented here.
- **Optional follow-up:** run Playwright + Lighthouse in CI/scratch to close Phase 1.4 / 5.2 gaps.

---

## Not run (and why)

| Item | Reason |
|------|--------|
| Playwright login→dashboard timeline | Not installed in scratch folder this session |
| Lighthouse CLI (login, dashboard, integrations) | Timeboxed; production preview not scripted |
| Full Integrations viewport screenshot audit | Browser matrix not executed; fixes driven by code review + RTL tests |
| Docker Compose rebuild smoke (create/copy/revoke key) | Stack running; manual smoke recommended after merge |
| SQL echo / EXPLAIN login + dashboard | No PostgreSQL echo capture this pass |
| `before` Docker login median (25 runs) | Rate limit (10 logins/min/IP) prevented unpaced batch; no pre-change capture saved |

---

## Verification commands (Phase 5)

```powershell
cd backend; .\.venv\Scripts\python.exe -m pytest -q
cd frontend; npm run type-check; npm run test; npm run build; npm run check:budget
cd backend; .\.venv\Scripts\alembic.exe heads
docker restart lbro-api; Start-Sleep 15
cd backend; .\.venv\Scripts\python.exe ..\scripts\perf\measure_login_http.py --runs 8
```

---

## Remaining issues

- Frontend container reported **unhealthy** in Docker while API was healthy — investigate separately (out of scope).
- Integrations visual regression still benefits from owner-run screenshot pass at 360–1920px.
- Concurrent benchmark script’s 20-login burst can trip auth rate limit if run repeatedly without restart.
