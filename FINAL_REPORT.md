# FINAL REPORT — production run (session 2)

**Verdict:** **READY WITH CONDITIONS**  
**Branch:** `release/production-ready` (not pushed)  
**Reason:** G5 full smoke **NOT RUN** (compose rebuild in progress / not finished); G7 **FAIL** (npm runtime advisories + zod major blocker); quality gates **FAIL** (`ruff`, `mypy`, `npm run lint` no ESLint config); G14/G15 **NOT RUN**.

## Findings (AUD)

| ID | Sev | Status | Evidence |
|----|-----|--------|----------|
| AUD-010 | High | **Fixed** | `ml.py` uses `sha256`; Bandit **High: 0** (`bandit_after_aud010.txt`); `test_aud010_flow_id_sha256.py` |
| AUD-011 | High | **Open** | axios **1.13.2**; zod **3.25.76** — see `docs/NPM_AUDIT_CLASSIFICATION.md` |
| AUD-006 | Info | **Accepted** | `.gitleaks.toml` allowlist `AKIAIOSFODNN7EXAMPLE`; gitleaks **no leaks** (59 commits) |

## Gate table

| Gate | Result | Evidence |
|------|--------|----------|
| G1 Secrets | **PASS** | gitleaks: `no leaks found`, 59 commits (`gitleaks_tail.txt`) |
| G2 Backend | **PASS** | `763 passed, 1 deselected` (`pytest_session2_full.log`) |
| G3 Frontend tests/build | **PASS** | Vitest **75 passed**; `npm run build` OK (`vite_build.txt`) |
| G3b type-check | **PASS** | (prior session; re-run if needed before push) |
| G4 / G4b | **PASS** | (prior `alembic_cycle.txt`) |
| G5 Compose smoke | **NOT RUN** | `docker compose build --no-cache` started (`compose_build.log`); lifecycle smoke not completed |
| G6 | **FAIL** | AUD-011 open |
| G7 Deps | **FAIL** | pip-audit see `pip_audit_session2.txt`; npm `npm audit --omit=dev` exit 1 |
| G8 / G8b Bandit | **PASS** / **PASS** | `-ll`: **0 High**, 5 Medium (`bandit_after_aud010.txt`) |
| G9 Isolation | **PASS** | OpenAPI project-scoped ops × cross-tenant + in-project role matrix (`g9_openapi_matrix.json`) |
| G10 ML | **PASS** | (existing `test_g10_ml_bundle_gate.py`) |
| G11 Dispatch | **PASS** | `test_g11_inferred_dispatch_gate.py` + `test_g11_notification_send_paths.py` |
| G12 Guides | **PASS** | STIX **49MB** scratch; **0** deprecated hits; Flesch **min 50.6** all 15 (`attack_guides_verify.json`) |
| G13 gitleaks | **PASS** | Installed; scan complete, **0** leaks |
| G14 Playwright | **NOT RUN** | Integrations viewport matrix |
| G15 Perf | **NOT RUN** | 20-run login benchmark |
| Lint/ruff/mypy | **FAIL** | ruff 777 issues; mypy 49 errors; eslint config missing |

## G9 coverage

Run `pytest tests/test_g9_openapi_project_matrix.py -s` prints `G9_OPENAPI_PROJECT_SCOPED_OPS=N`. Artifact includes `cross_tenant_coverage_ratio: 1.0` and `role_matrix` for mutating ops × viewer / project_admin / platform_admin / super_admin.

## G11 send paths (code)

| Path | File | Gate |
|------|------|------|
| HTTP dispatch/send | `notifications.py:55–77` | `send()` requires `approved` or `failed`; dispatch auto-approves only with `DISPATCH_NOTIFICATION` |
| Worker retry | `notification_worker.py:37–42` | Skips unless `approved`/`failed` |
| Incident create | `incidents.py:88` | `generate_for_incident` → `status=pending` only |
| SQS enqueue | `notification_service.py:200` | After explicit `approve()` |

## NOT RUN

Full compose smoke script, Playwright G14, login perf G15, `npm run lint` (no config), full `ruff format` apply.

Nothing pushed.
