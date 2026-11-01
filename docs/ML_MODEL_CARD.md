# LBRO ML model card

## Model

| Field | Value |
|-------|--------|
| Version | `lbro-demo-synthetic-1.0.0` (from bundle `manifest.json`) |
| Status | `demo-synthetic` until trained on real CICIDS2017 CSVs |
| Location | `backend/app/ml/models/bundle/` |
| Integrity | HMAC-SHA256 (`manifest.sig`) + per-file SHA-256 in `manifest.json` |

## Intended use

- Assist analysts by suggesting CICIDS2017-style attack labels from flow feature dictionaries.
- Flag low coverage, OOD, and heuristic paths with **`needs_review`**.

## Out of scope

- Autonomous blocking or host isolation (not implemented).
- Replacing enterprise IDS/NDR or SOC playbooks.
- High-stakes enforcement without human review.

## Inputs

- Up to **77** numeric features in canonical order (`CICIDS2017_FEATURES`).
- Event payloads mapped via `app/ml/event_mapper.py` (supports nested `flow_features` and aliases).

## Outputs

Structured classification (`ClassificationResult`): `attack_category`, `confidence` (calibrated when `source=model`), `source`, `feature_coverage`, `ood_flag`, `needs_review`, `reasons`, `top_k`.

## Metrics

See `ML_MODEL_EVALUATION.md` — headline **realistic block macro-F1 ≈ 0.91** on synthetic fast train only.

## Ethical considerations

- False positives can increase analyst load; default auto-containment is **off**.
- Biased training data can mislabel minority classes; per-class support warnings apply when test support &lt; 30.

## Update / rotation

1. Train: `python scripts/train_models_cli.py --fast --sign` (with `ML_MODEL_SIGNING_KEY` set).
2. Verify: `python scripts/verify_model.py --load-model`.
3. Deploy bundle read-only (Docker volume `:ro`).
4. Rotate key: generate new `ML_MODEL_SIGNING_KEY`, run `scripts/sign_model.py`, redeploy API/workers together.

See runbook section in `ML_FIX_REPORT.md`.
