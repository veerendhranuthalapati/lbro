# FEATURE_REPORT: Threat-to-obligation pipeline

## Phase 0 — Baseline (2026-11-01)

**Branch:** `feature/threat-to-obligation` (from `fix/ml-hardening` @ `29b5e02`)

| Check | Command | Result |
|-------|---------|--------|
| Alembic head | `backend\.venv\Scripts\alembic.exe heads` | `016_ml_classification_retry (head)` |
| Backend tests | `pytest tests/ -q` (env as CI) | `710 passed, 1 deselected, 15 warnings in 301.20s` |
| Frontend | `npm run type-check`; `npm run test -- --run` | type-check pass; `58 passed` |

### Current compliance flow (manual jurisdictions)

1. **Incident create** (`app/routers/incidents.py` ~84–88): if `affected_jurisdictions` or personal/health flags, calls `ComplianceService.generate_obligations` and `NotificationService.generate_for_incident`.
2. **ComplianceService** (`app/services/compliance_service.py` ~57–84): loops `REGULATION_RULES` (GDPR/HIPAA/DPDPA); matches when any manual jurisdiction code is in the rule’s jurisdiction list, or HIPAA+health, or GDPR/DPDPA+personal; sets `deadline = now + timedelta(hours=rules["hours"])` (72/1440/72 hardcoded in dict).
3. **NotificationService** (`app/services/notification_service.py` ~123–167): same jurisdiction logic; deadlines from `settings.GDPR_NOTIFICATION_HOURS`, `HIPAA_NOTIFICATION_HOURS`, `DPDPA_NOTIFICATION_HOURS` (`app/config.py` ~179+); notifications created with `status="pending"` (human approve/dispatch required).

**Duplicated deadline truth:** `REGULATION_RULES[*].hours` vs `settings.*_NOTIFICATION_HOURS` — reconciled in ADR-001 (engine uses `laws.json`; legacy path unchanged until migration complete).

---

*(Phases 1–7 appended as completed.)*
