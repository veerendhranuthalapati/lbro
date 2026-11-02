# npm audit classification — session 2026-11-02
# Commands: npm ls axios zod; npm audit; npm audit --omit=dev
# axios direct dep upgraded to 1.13.2 (was 1.19.0 in lock before session fix)

| Package | Scope | Runtime vs dev | Action |
|---------|--------|----------------|--------|
| axios | direct dependency | **Runtime** (browser API client) | Upgraded to **1.13.2**; `npm audit --omit=dev` still reports **4 high** (transitive follow-redirects etc.) |
| zod | direct dependency | **Runtime** (form validation) | **3.25.76**; GHSA targets zod 4.x line — bump to **4.6.6+** breaks `@hookform/resolvers@3` peer; **blocker**: major upgrade needs resolver v5 + regression pass |
| postcss-selector-parser | transitive | **Dev** (tailwind/postcss build) | `npm audit fix` candidate |
| source-map-js | transitive | **Dev** (vite build) | `npm audit fix` candidate |
| vitest/msw/eslint chain | transitive | **Dev** | Majority of **30** full-tree findings |

Evidence tails: `..\lbro-run-scratch\npm_ls_axios_zod.txt`, `npm_audit_omit_dev.txt`, `vite_build.txt` (build PASS after axios bump).
