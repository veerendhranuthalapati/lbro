# Audit command log

| Time (local) | Command | Exit | Decision / tail |
|--------------|---------|------|-----------------|
| 15:05 | `Get-Date` | 0 | Start 2026-11-02 15:05:56 +05:30 |
| 15:06 | `git branch -a`, log graph | 0 | Chose base `perf/login-and-ux` |
| 15:06 | `git checkout -b release/production-ready` | 0 | |
| 15:06 | `alembic heads` | 0 | `017_threat_to_obligation (head)` |
| 15:06 | `docker version` | 0 | Docker available |
| 15:06 | `git tag backup/pre-production-run-*`, `git bundle` | 0 | Bundle at `..\lbro-run-scratch\backup.bundle` |
| 15:07 | secrets regex grep | 0 | Only placeholders/examples in tracked docs; test keys in conftest only |
| 15:07 | `pytest -q` (background) | running | Log `..\lbro-run-scratch\pytest_baseline.log` |
