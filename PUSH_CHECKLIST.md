# Push checklist (owner — nothing was pushed by agent)

- [ ] Review `git log release/production-ready` vs `main`
- [ ] Re-run secrets scan (gitleaks or manual) on final tree and recent commits
- [ ] Confirm no `lbro-run-scratch` or `.env` files staged
- [ ] Run fresh venv pytest + `npm ci` + build (see FINAL_REPORT.md)
- [ ] Resolve any Bandit findings after CI change
- [ ] Merge to `main` locally: `git checkout main; git merge --no-ff release/production-ready`
- [ ] Push only after gates PASS: `git push origin main`
- [ ] Tag release locally if desired (agent did not tag)

**PUSH BLOCKED if:** real secrets found, Critical findings open, or migrations fail on Postgres.
