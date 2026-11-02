# FINAL REPORT — production run (reconciled)

**Verdict:** **READY WITH CONDITIONS**  
**Branch:** `release/production-ready` (not pushed)  
**Session wall clock:** 2026-11-02 continue (~60 min box)  

## Executive summary

Reconciled gates against fresh command output. Backend **756 passed** after PyJWT bump and new G9/G10/G11 tests. Frontend **75** Vitest + type-check green. G9 OpenAPI matrix artifact: **16** operations × **4** cross-tenant actors = **64** rows (`..\lbro-run-scratch\g9_openapi_matrix.json`). Attack guide URLs **45/45** reachable (HEAD); MITRE STIX pin check **NOT RUN** (no `enterprise-attack.json` in scratch). Full compose rebuild/smoke, gitleaks, Playwright Integrations matrix, and login perf 20-run **NOT RUN** this session.

## Findings table (AUD)

| ID | Sev | Location | Fix / note | Status |
|----|-----|----------|------------|--------|
| AUD-001 | High | `backend/app/main.py:213`, `tests/test_health_ready.py` | `/health/ready` | **Fixed** — commit `7423fd6` / earlier main work |
| AUD-002 | High | `.github/workflows/ci.yml` | Removed Bandit `\|\| true` | **Fixed** — `53445d1` |
| AUD-003 | High | `backend/tests/conftest.py` | ML bundle copy to scratch | **Fixed** — `d94742d` |
| AUD-004 | Med | `docker-compose.yml` | Readiness healthcheck | **Fixed** — `7423fd6` |
| AUD-005 | Med | `backend/app/knowledge/attack_guides.json` | Guides + APIs | **Fixed** — `aa0bba5` |
| AUD-006 | Info | `.env.prod.example:19` | AWS doc placeholder AKIA… | **Accepted** — `git grep` only example |
| AUD-007 | Info | `backend/tests/integration/` | Postgres migration cycle | **Fixed** — evidence `..\lbro-run-scratch\alembic_cycle.txt`; commit `5903f33` |
| AUD-008 | Low | `backend/app/core/rate_limit.py:24` | Login 10/min/IP | **Mitigated** — RUNBOOK pacing |
| AUD-009 | Info | local `.venv` | Bandit run | **Run** — see G8b |
| AUD-010 | High | `backend/app/routers/ml.py:270` | MD5 for demo `flow_id` (Bandit B324) | **Open** — triage / `# nosec` or SHA-256 |
| AUD-011 | High | `frontend/node_modules/axios` | npm audit (dev transitive) | **Open** — runtime browser bundle; `npm audit fix` pending |

## Gate table (PASS / FAIL / NOT RUN only)

| Gate | Result | Evidence |
|------|--------|----------|
| G1 No real secret in tree | **PASS** | `git grep AKIA…` → `.env.prod.example` placeholder only |
| G2 Backend green | **PASS** | `Remove-Item Env:DATABASE_URL; pytest -q` → **`756 passed, 1 deselected`** tail in `..\lbro-run-scratch\pytest_full_after_gates.log` |
| G3 Frontend type-check/tests | **PASS** | `npm run type-check`; `npm run test -- --run` → **75 passed** (`..\lbro-run-scratch\vitest_after_gates.log`) |
| G4 Alembic single head | **PASS** | Head `017_threat_to_obligation` (`alembic_cycle.txt`) |
| G4b Postgres cycle | **PASS** | PG16 throwaway upgrade/downgrade (`alembic_cycle.txt`) |
| G5 Compose smoke | **NOT RUN** | Full `build --no-cache` / seed / lifecycle / `down -v` not executed; partial HTTP only: `curl …/health/ready` → **200**, `:3000` → **200** (`compose_smoke_session.txt`) |
| G6 Critical/High open | **FAIL** | AUD-010, AUD-011 open |
| G7 Dependency audit | **FAIL** | `pip-audit` clean post PyJWT (`pip_audit.txt`); **npm** 5+ advisories (`npm_audit.txt`) |
| G8 CI hides failures | **PASS** | Bandit `\|\| true` removed (`53445d1`) |
| G8b Bandit local `-ll` | **FAIL** | `bandit -r app -ll` → **1 High, 5 Medium** (`..\lbro-run-scratch\bandit.txt`) |
| G9 Tenant isolation | **PASS** | `pytest tests/test_g9_openapi_project_matrix.py` + red-team suite; matrix **64** rows, 0×200 cross-tenant |
| G10 ML fail-closed prod | **PASS** | `pytest tests/test_g10_ml_bundle_gate.py` (6 tests): tamper, wrong/missing sig, prod test key, heuristic fallback |
| G11 Inferred dispatch | **PASS** | `pytest tests/test_g11_inferred_dispatch_gate.py`; dispatch only via `POST /notifications/{id}/dispatch` (`notifications.py:55`) |
| G12 Attack guides | **PASS** | 15 classes; `test_attack_guides.py`; URL verify **45/45 ok** (`attack_guides_verify.json`) |
| G13 Secret history scan | **NOT RUN** | `gitleaks` not installed; manual `git grep` / pickaxe only |
| G14 Integrations Playwright | **NOT RUN** | 360/768/1024/1440 matrix not executed |
| G15 Login perf 20-run | **NOT RUN** | No before/after medians recorded this session |

## Test counts

| Suite | After this session |
|-------|-------------------|
| Backend pytest | **756 passed**, 1 deselected |
| Frontend Vitest | **75 passed** |

New tests: `test_g9_openapi_project_matrix.py`, `test_g10_ml_bundle_gate.py`, `test_g11_inferred_dispatch_gate.py`, `test_incident_pdf_escape.py`, `IncidentExplainer.test.tsx`, `AttackLibraryPage.test.tsx`.

## Attack guides & UX

- Incident PDF section **1a Attack Summary** with `xml.sax.saxutils.escape` — `test_incident_pdf_escape.py` (`%PDF`, no raw `<script>`).
- UI: **Understand this attack** tabs + executive/analyst toggle; **Attack library** nav route.
- Readability (Flesch on sample summaries): **see** `attack_guides_verify.json` → `readability_flesch_sample`.
- MITRE vs pinned STIX: **NOT RUN** (missing scratch STIX bundle).
- Readability: Flesch reading ease **27.5** on first-five-guide sample (`attack_guides_verify.json`).

## Performance

Inherited from `perf/login-and-ux` branch (`PERF_UX_REPORT.md`). This session: **NOT RUN** 20× login benchmark.

## NOT RUN (explicit)

1. `docker compose build --no-cache`, full smoke script, `down -v`  
2. gitleaks / trufflehog full history  
3. Playwright Integrations viewport/state matrix (scratch)  
4. Login click-to-interactive medians (20 runs)  
5. MITRE Enterprise STIX cross-check (no pinned file in `lbro-run-scratch`)  

Nothing was pushed to any remote.
