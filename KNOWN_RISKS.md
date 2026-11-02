# Known risks — owner decisions

| Topic | Why it needs you |
|-------|------------------|
| Licence | No SPDX/legal licence chosen for distribution |
| Evidence storage | PostgreSQL vs S3 WORM — README claims vs actual env |
| Redis rate limiting | In-memory limiter only; Redis noted for production |
| MFA | Not implemented |
| Real EC2/SSM isolation | Terraform validated only, never applied |
| CICIDS2017 retraining | Shipped model is demo/synthetic; operational use needs retrain |
| Compliance rule legal sign-off | Inference engine rules are `review_status: unreviewed` |
| npm / pip deps (G7) | **AUD-011**: zod 4.x needed for some GHSA — blocked on `@hookform/resolvers@3`; **pip-audit**: urllib3 2.7.0 → 2.8.0 |
| Compose smoke (G5) | Full lifecycle smoke **NOT RUN** after rebuild — required before prod |
| Static analysis | `ruff` / `mypy` / ESLint config gaps — CI may differ; triage before calling release clean |

Attack guide summaries rewritten for readability; content still **unreviewed** for legal/comms.

**Secrets:** gitleaks **0 leaks** on 59 commits with `.gitleaks.toml` allowlist for AWS doc example key.
