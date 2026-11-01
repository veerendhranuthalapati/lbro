# ML model evaluation

## Headline (public)

| Field | Value |
|-------|--------|
| Shipped bundle status | `demo-synthetic` |
| Headline evaluation metrics | **n/a - demo-synthetic** |
| UI / API manifest summary | **n/a - demo-synthetic** (see `app/ml/metrics_public.py`) |

CICIDS2017 CSV files were **not** in the repository at train time. Do **not** use numeric metrics from the demo bundle for compliance or marketing claims.

## Dataset (intended)

| Item | Value |
|------|--------|
| Source | CICIDS2017-style features when CSVs are added; current bundle uses synthetic generator |
| Features | **77** (`FEATURE_COUNT` in `app/ml/features.py`) |
| Classes | 15 (`ATTACK_CLASSES`) |

---

## Appendix A — Synthetic lab run only (not production claims)

**Label:** demo-synthetic fast train (`TrainConfig(fast=True)`). These numbers are archived for engineering reproducibility only.

Reproduce (slow; excluded from default pytest):

```powershell
cd backend
$env:ENVIRONMENT="development"
$env:ML_MODEL_SIGNING_KEY="test-ml-signing-key-minimum-32-characters-long"
pytest tests/test_ml_training.py -m slow -v
```

| Metric | Realistic block | Optimistic stratified |
|--------|-----------------|------------------------|
| Accuracy | 0.98 | 0.9979 |
| Macro F1 | 0.9103 | 0.9940 |
| Weighted F1 | 0.9785 | 0.9979 |
| Log loss | 0.1224 | 0.0121 |
| ECE | 0.0082 | 0.0080 |

Artifacts (when generated locally): `ml_evaluation/metrics.json`, `confusion_matrix.csv`, `confusion_matrix.png`, `classification_report.txt`, `run_metadata.json`.

Algorithm in last fast run: **HistGradientBoosting** with **isotonic** calibration.

## Limitations

- Synthetic data ≠ live network traffic.
- **Not a production IDS replacement** — triage hints and review queues only.
