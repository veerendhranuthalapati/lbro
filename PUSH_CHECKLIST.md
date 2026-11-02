# Push checklist (owner — nothing was pushed by agent)

- [ ] `git log release/production-ready` vs `main`
- [ ] `gitleaks detect --source . --config .gitleaks.toml` → expect **no leaks** (59+ commits)
- [ ] `Remove-Item Env:DATABASE_URL`; `backend/.venv/Scripts/pytest -q` → expect **763+** passed
- [ ] `cd frontend && npm ci && npm run build && npm run test -- --run`
- [ ] Resolve **pip-audit** urllib3 and **npm** zod/axios (see `docs/NPM_AUDIT_CLASSIFICATION.md`)
- [ ] Run **full compose smoke** (seed, SHA-256 evidence, PDFs, SSE, 429, logs) then `down -v`
- [ ] Optional: G14 Playwright + G15 perf per RUNBOOK
- [ ] Merge: `git checkout main && git merge --no-ff release/production-ready`
- [ ] Push when you accept open gates: `git push origin main`

**Not READY until you accept:** G5 smoke, G7 urllib3/npm, and any mypy/ruff policy you enforce.
