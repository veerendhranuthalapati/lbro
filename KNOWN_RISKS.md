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
| Bandit B324 (AUD-010) | `ml.py:270` MD5 for synthetic flow_id — replace or `# nosec` with rationale |
| npm audit (AUD-011) | axios/zod/source-map-js — mostly dev/build; zod major bump needed for GHSA |
| Compose smoke | Full lifecycle smoke not run on this session — do before prod cutover |

Attack guide content is **defensive** and **unreviewed**; legal/comms review before customer-facing release.

**Secret scanning:** gitleaks not run on full history — run locally before push (see PUSH_CHECKLIST).
