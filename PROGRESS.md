# Production run progress

**Branch:** `release/production-ready`  
**Updated:** 2026-11-02 session 2 (~90 min box)  

| Item | Status | Evidence |
|------|--------|----------|
| AUD-010 MD5 → SHA-256 | **done** | Bandit High 0; `test_aud010_flow_id_sha256.py` |
| AUD-011 / axios | **partial** | axios 1.13.2; zod blocker documented |
| G9 matrix + roles | **done** | `g9_openapi_matrix.json` |
| G11 send-path tests | **done** | `test_g11_notification_send_paths.py` |
| G12 STIX + Flesch | **done** | scratch STIX; min Flesch 50.6 |
| gitleaks | **done** | 0 leaks / 59 commits |
| Backend suite | **done** | **763 passed** |
| Compose G5 | **build done; smoke NOT RUN** | `compose_build.log` exit **0** (~234s); lifecycle smoke + `down -v` still pending |
| G14/G15 | **NOT RUN** | |
| FINAL_REPORT + zip | **pending commit** | |

**Git hygiene:** pytest writes only under `..\lbro-run-scratch\`; tracked tree unchanged by tests (verify `git status` before/after).
