# ML model evaluation (synthetic demo bundle)

**Status:** The shipped bundle is **`demo-synthetic`** — CICIDS2017 CSV files were **not** present in the repository at train time. Metrics below are from a **fast synthetic run** (`TrainConfig(fast=True)`) and are **not** indicative of production IDS performance.

## Dataset

| Item | Value |
|------|--------|
| Source | `scripts/train_models.py` synthetic generator (via `app/ml/training/pipeline.py`) |
| Real CICIDS2017 CSV | **NOT FOUND** (searched `backend/app/ml/data`, `data/`, `ml_data/`, repo root) |
| Features | **77** (`app/ml/features.py` → `FEATURE_COUNT`) |
| Classes | 15 (`ATTACK_CLASSES`) |
| Cleaning | Dedupe rows, inf→NaN→median impute, rare-label merge policy in `training/labels.py` |

## Splits

| Split | Method |
|-------|--------|
| **Headline (realistic)** | Contiguous 70/15/15 blocks with 10-row gaps (`_block_split`) |
| Optimistic | Stratified random 70/15/15 after dedupe |

## Headline metrics (realistic block)

Command (recorded):

```powershell
cd c:\Users\veere\Desktop\lbro\backend
$env:ENVIRONMENT="development"
$env:ML_MODEL_SIGNING_KEY="test-ml-signing-key-minimum-32-characters-long"
.\.venv\Scripts\python.exe -c "from app.ml.training.pipeline import TrainConfig, train_and_export; train_and_export(TrainConfig(fast=True, signing_key='test-ml-signing-key-minimum-32-characters-long'))"
```

| Metric | Realistic | Optimistic |
|--------|-----------|------------|
| Accuracy | 0.98 | 0.9979 |
| Macro F1 | 0.9103 | 0.9940 |
| Weighted F1 | 0.9785 | 0.9979 |
| Log loss | 0.1224 | 0.0121 |
| ECE | 0.0082 | 0.0080 |

Algorithm selected on validation macro-F1: **HistGradientBoosting** with **isotonic** calibration.

Artifacts: `ml_evaluation/metrics.json`, `confusion_matrix.csv`, `confusion_matrix.png`, `classification_report.txt`, `run_metadata.json`.

## Limitations

- Synthetic data ≠ live network traffic.
- CICIDS2017 lab bias and label noise still apply when real CSVs are used later.
- **This model is not a production IDS replacement** — use for demo, triage hints, and analyst review queues only.

## Reproducibility

Re-run the same command twice; `metrics_summary.realistic.macro_f1` matches (verified during `test_ml_training.py`).
