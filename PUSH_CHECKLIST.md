# Push checklist

- [ ] `pytest -q` → **763+** passed (`pytest_session3_full.log`)
- [ ] `cd frontend && npm ci && npm run lint && npm run type-check && npm run test -- --run && npm run build`
- [ ] `pip-audit` — resolve **python-jose** transitive or document acceptance
- [ ] `npm audit --omit=dev` — 3 dev-only findings OK?
- [ ] Full compose smoke + `docker compose down -v`
- [ ] `gitleaks detect --config .gitleaks.toml`
- [ ] Deploy: only **`workflow_dispatch`** or **`v*`** tags (no `main` push deploy)
- [ ] Merge/push when gates accepted

Not pushed by agent.
