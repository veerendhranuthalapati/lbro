# AUDIT REPORT (production run)

**Branch:** `release/production-ready`  
**Started:** 2026-11-02 15:05 +05:30  

| ID | Sev | Area | Evidence | Status |
|----|-----|------|----------|--------|
| AUD-001 | High | Ops | `/health/ready` missing in `main.py` while integration tests expect it (`test_incidents.py:99`) | **Fixed** — `main.py`, `test_health_ready.py` |
| AUD-002 | High | CI | Bandit step used `\|\| true` hiding failures (`.github/workflows/ci.yml:305`) | **Fixed** |
| AUD-003 | High | Tests | `conftest.py` wrote `manifest.sig` into tracked bundle | **Fixed** — copy to `../lbro-run-scratch/ml-bundle-copy` |
| AUD-004 | Med | Docker | API healthcheck probed `/health` not readiness (`docker-compose.yml:105`) | **Fixed** |
| AUD-005 | Med | UX/API | Attack guides required by spec as versioned JSON; only inline `incident_explainer.py` existed | **Fixed** — `attack_guides.json` + `/knowledge/attacks` + `/incidents/{id}/explanation` |
| AUD-006 | Info | Secrets | Test signing keys in `conftest.py` / README examples only; `.env.prod.example` uses AWS doc example AKIA… | **Accepted** — no real secrets in tree (FACT: regex scan) |
| AUD-007 | Info | Tests | `integration/test_incidents.py` excluded on SQLite (`conftest collect_ignore`) | **Open** — Postgres cycle NOT RUN this session |
| AUD-008 | Low | Rate limit | Auth login 10/min/IP (`rate_limit.py:24`) blocks unpaced benchmark bursts | **Mitigated** — paced scripts; document in RUNBOOK |
| AUD-009 | Info | Deps | `bandit` not installed in local `.venv` | **NOT RUN** locally; CI installs via pip |

Evidence commands logged in `AUDIT_LOG.md`.
