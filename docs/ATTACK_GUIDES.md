# Attack guides — maintainer notes

## Files

- `backend/app/knowledge/attack_guides.json` — versioned content (one entry per `ATTACK_CLASSES` in `app/ml/features.py`)
- `backend/app/knowledge/schemas.py` — Pydantic validation
- `scripts/build_attack_guides.py` — regenerates JSON from `incident_explainer` + compliance MITRE mappings

## Update workflow

1. Edit copy in `incident_explainer.py` or compliance `attack_to_technique.json` as needed.
2. Run: `backend\.venv\Scripts\python.exe scripts\build_attack_guides.py`
3. Review generated JSON; set `review_status` to `reviewed` only after human review.
4. Run `pytest tests/test_attack_guides.py`.

## API

- `GET /api/v1/knowledge/attacks` — list/search (requires `READ_INCIDENT`)
- `GET /api/v1/knowledge/attacks/{class_id}?audience=executive|analyst`
- `GET /api/v1/incidents/{id}/explanation` — guide + incident facts + uncertainty banner

All responses include the decision-support disclaimer (detection is a lead, not proof).

## MITRE

Technique IDs must exist in pinned Enterprise version (`attack_enterprise_version` in JSON). Include MITRE attribution notice in UI when displaying techniques.
