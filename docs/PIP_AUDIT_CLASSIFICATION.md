# Pip audit — session 3

| Finding | Fix version | Reachability in LBRO |
|---------|-------------|----------------------|
| urllib3 2.7.0 | **2.8.0** | **Fixed** — pinned in `requirements.txt` |
| python-jose 3.3.0 | 3.4.0+ | **Transitive** (not imported in `app/`); pip-audit still flags — **Open** until dependency tree bumped |

Command: `pip-audit` → tail `pip_audit_session3.txt`
