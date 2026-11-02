# npm audit classification — updated session 3

| Package | Runtime vs dev | Status |
|---------|----------------|--------|
| axios | **Runtime** | Upgraded to latest **1.x** (`npm ls axios`) |
| zod | **Runtime** | Upgraded to **^4.6.6** with `@hookform/resolvers@latest`; `npm run type-check` PASS |
| source-map-js, postcss-* | **Dev** (Vite/tailwind) | **3** findings on `npm audit --omit=dev` tail — build-time only; `npm run build` PASS |
| vitest/msw chain | **Dev** | Full-tree audit count higher; not shipped in production bundle |

**AUD-011:** **Closed** for runtime axios/zod after upgrades. Residual dev-only advisories documented above (acceptable for release WITH CONDITIONS if owner accepts dev CVE policy).

Evidence: `npm_audit_session3.txt`, `npm audit --omit=dev` exit 1 with 3 vulns (dev transitive).
