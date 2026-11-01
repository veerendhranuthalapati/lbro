# Compliance inference pipeline

LBRO maps ML attack classes through a **versioned knowledge base** (MITRE techniques, data categories, residency counts, legal rule packs) to **suggested** regulatory obligations. Output is **decision support only** — not legal advice. Every assessment carries a `disclaimer` field.

## Modes (`projects.compliance_inference_mode`)

| Mode | Behaviour |
|------|-----------|
| `manual` | Engine disabled; legacy manual jurisdictions only. |
| `hybrid` | Engine runs; suggestions union with manual jurisdictions. |
| `inferred` | Engine-primary; manual entries remain allowed. |

## Confidence and provisional gating

Assessments are **provisional** when classification is not model-sourced, OOD/review flags are set, confidence is below `ML_REVIEW_THRESHOLD`, or asset match / record counts are weak. Obligations may still appear but require analyst **accept** or **dismiss** before notifications.

## Trace

Each `incident_exposure_assessments.trace` JSON array records ordered steps: attack class → techniques → categories → residency counts → rule ids → deadlines. Rendered verbatim in the UI.

## Adding knowledge

1. Edit JSON under `backend/app/compliance/knowledge/` (increment `content_version`).
2. Run `scripts/verify_attack_mapping.py` after ATT&CK mapping changes.
3. Restart API (loader validates at startup).
4. Have counsel review rules (`legal_review_status` starts `unreviewed`).

## Deadlines

Inferred obligations read deadlines from `laws.json` only. Legacy manual incident creation still uses `REGULATION_RULES` / `settings.*_NOTIFICATION_HOURS` until fully migrated.

## MITRE

Technique names/IDs are curated mappings verified against pinned Enterprise ATT&CK; see UI footer on exposure views.
