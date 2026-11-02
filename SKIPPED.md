# Skipped (time box)

| Item | Reason |
|------|--------|
| Playwright Integrations viewport matrix | Not started; perf work covered RTL tests |
| Lighthouse CLI | NOT RUN |
| PostgreSQL 16 throwaway migration cycle | **DONE** — upgrade head / downgrade -1 / upgrade on PG16 `:5434`; single head `017_threat_to_obligation` (log: `..\lbro-run-scratch\alembic_upgrade.log`) |
| docker compose smoke E2E | **PARTIAL** — `/health/ready` 200 after API restart; login 200; nginx `:3000` 200 (`compose_smoke.txt`; redeploy API for readiness route) |
| pip-audit / npm audit full pass | **RUN** — PyJWT bumped to 2.15.0 (pip-audit clean); npm 5 vulns (zod high — needs owner on major bump) |
| pandoc .docx export | pandoc availability not verified |

Resume: run Postgres cycle, compose smoke, audits, then update gate table.
