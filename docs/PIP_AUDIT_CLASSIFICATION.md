# Pip audit — session 3

| Finding | Fix version | Reachability in LBRO |
|---------|-------------|----------------------|
| urllib3 2.7.0 | **2.8.0** | **Fixed** — pinned in `requirements.txt` |
| python-jose 3.3.0 | n/a | **Not a project dependency.** Not in `requirements.txt`, `requirements-dev.txt` or `pyproject.toml`, and not imported anywhere in `backend/app`, `backend/tests` or `scripts`. It was present only in the local Windows `backend/.venv`. `pip-audit -r backend/requirements.txt` on the pinned set reports no known vulnerabilities (2026-11-03). **Resolved** by removing it from the local venv (`pip uninstall python-jose`). |

Command: `pip-audit` → tail `pip_audit_session3.txt`


Re-verified 2026-11-03: `pip-audit -r requirements.txt` → `No known vulnerabilities found`.
