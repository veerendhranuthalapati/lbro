# Push checklist (owner — nothing was pushed by agent)

- [ ] Review `git log release/production-ready` vs `main`
- [ ] Install and run **gitleaks** (or trufflehog) on full git history + working tree
- [ ] Confirm no `lbro-run-scratch/`, `.env`, or tokens in staged files
- [ ] Re-run with clean env: `Remove-Item Env:DATABASE_URL`; `backend/.venv/Scripts/pytest -q` (expect **756+** passed)
- [ ] `cd frontend && npm ci && npm run type-check && npm run test -- --run` (expect **75+** passed)
- [ ] Triage **Bandit** High (AUD-010) and **npm audit** (AUD-011) or document acceptance
- [ ] Run full **docker compose** smoke per RUNBOOK (SHA-256 evidence, SSE, PDFs, 429, logs)
- [ ] Optional: drop MITRE Enterprise STIX JSON into `../lbro-run-scratch/` and run `python scripts/verify_attack_guides_mitre.py`
- [ ] Merge locally: `git checkout main; git merge --no-ff release/production-ready`
- [ ] Push only when G5/G6/G7/G13 gates you accept: `git push origin main`

**PUSH BLOCKED if:** real secrets found, unresolved Critical findings you care about, or migrations fail on Postgres.
