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
| Bandit CI | Removing `\|\| true` may surface new findings on next CI run — review and triage |

Attack guide content is **defensive** and **unreviewed** (`review_status: unreviewed`); legal/comms review before customer-facing release.
