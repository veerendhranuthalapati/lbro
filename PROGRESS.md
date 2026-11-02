# Production run progress — session 3

**Branch:** `release/production-ready` | **HEAD:** see `git log -1`

| Item | Status | Evidence |
|------|--------|----------|
| urllib3 / pip-audit | partial | urllib3 fixed; python-jose transitive open |
| npm zod 4 + axios | **done** | lint/tsc/test/build green |
| ESLint | **done** | `.eslintrc.cjs`, `npm run lint` |
| Ruff CI paths | **done** | All checks passed |
| G11 dispatch gate | **done** | `notification_service._ensure_regulatory_dispatch_allowed` |
| Backend suite | **done** | **763 passed** (`pytest_session3_full.log`) |
| gitleaks | **done** | 68 commits, 0 leaks |
| G9 ops | **16** | `G9_OPENAPI_PROJECT_SCOPED_OPS=16` |
| Compose G5 | **partial** | `up -d` + ready/ui 200; full smoke **NOT RUN** |
| G14/G15 | **NOT RUN** | |
| Alembic PG16 cycle | **NOT RUN** this session | |

Tests do not modify tracked files (artifacts under `..\lbro-run-scratch\` only).
