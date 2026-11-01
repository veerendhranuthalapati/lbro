"""End-to-end training, evaluation, and signed bundle export."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    _HAS_PLOTTING = True
except ImportError:  # pragma: no cover - optional for runtime API
    _HAS_PLOTTING = False
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import GaussianNB

from app.ml.bundle_io import CLASSES_NAME, MODEL_NAME, PREPROCESSING_NAME, write_bundle_manifest
from app.ml.features import ATTACK_CLASSES, CICIDS2017_FEATURES
from app.ml.training.cicids_loader import discover_cicids_files, load_cicids_frame
from app.ml.training.labels import MIN_TEST_SUPPORT_FOR_REPORTING

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE_DIR = BACKEND_ROOT / "app" / "ml" / "models" / "bundle"
EVAL_DIR = REPO_ROOT / "ml_evaluation"
SEED = 42


@dataclass
class TrainConfig:
    bundle_dir: Path = DEFAULT_BUNDLE_DIR
    eval_dir: Path = EVAL_DIR
    max_rows_per_class: int | None = None
    fast: bool = False
    signing_key: str | None = None
    data_dirs: list[Path] | None = None


def _git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True)
        return out.strip()
    except Exception:
        return "unknown"


def _load_synthetic_module():
    script = REPO_ROOT / "scripts" / "train_models.py"
    spec = importlib.util.spec_from_file_location("lbro_train_models", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _frame_from_synthetic(cfg: TrainConfig) -> tuple[pd.DataFrame, dict[str, str], str]:
    mod = _load_synthetic_module()
    if cfg.fast:
        mod.TOTAL_SAMPLES = 3_000
    X, y = mod.generate_dataset()
    df = pd.DataFrame(X, columns=CICIDS2017_FEATURES)
    df["label"] = y
    if cfg.max_rows_per_class:
        parts = []
        for label in ATTACK_CLASSES:
            subset = df[df["label"] == label].head(cfg.max_rows_per_class)
            parts.append(subset)
        df = pd.concat(parts, ignore_index=True)
    return df, {"synthetic_generator": "scripts/train_models.py"}, "demo-synthetic"


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates()
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    medians = df[CICIDS2017_FEATURES].median(numeric_only=True)
    df[CICIDS2017_FEATURES] = df[CICIDS2017_FEATURES].fillna(medians)
    return df


def _dedupe_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_df, hold = train_test_split(df, test_size=0.30, random_state=SEED, stratify=df["label"])
    val_df, test_df = train_test_split(hold, test_size=0.50, random_state=SEED, stratify=hold["label"])
    return train_df, val_df, test_df


def _block_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    n = len(df)
    train_end = int(n * 0.70)
    val_start = train_end + 10
    val_end = val_start + int(n * 0.15)
    test_start = val_end + 10
    return df.iloc[:train_end], df.iloc[val_start:val_end], df.iloc[test_start:]


def _compute_ood_stats(train_df: pd.DataFrame) -> dict:
    return {
        "medians": train_df[CICIDS2017_FEATURES].median(numeric_only=True).to_dict(),
        "ood_low": train_df[CICIDS2017_FEATURES].quantile(0.001).to_dict(),
        "ood_high": train_df[CICIDS2017_FEATURES].quantile(0.999).to_dict(),
        "feature_order": list(CICIDS2017_FEATURES),
    }


def _ece(probas: np.ndarray, y_true: np.ndarray, n_bins: int = 15) -> float:
    preds = np.argmax(probas, axis=1)
    conf = probas.max(axis=1)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (conf > bins[i]) & (conf <= bins[i + 1])
        if not np.any(mask):
            continue
        acc = np.mean(preds[mask] == y_true[mask])
        ece += np.abs(acc - conf[mask].mean()) * np.mean(mask)
    return float(ece)


def _evaluate_split(name: str, model, X, y_labels, class_names: list[str]) -> dict:
    probas = model.predict_proba(X)
    preds = np.argmax(probas, axis=1)
    y_idx = np.array([class_names.index(l) for l in y_labels])
    report = classification_report(y_idx, preds, target_names=class_names, output_dict=True, zero_division=0)
    return {
        "split": name,
        "accuracy": float(accuracy_score(y_idx, preds)),
        "macro_f1": float(f1_score(y_idx, preds, average="macro")),
        "weighted_f1": float(f1_score(y_idx, preds, average="weighted")),
        "log_loss": float(log_loss(y_idx, probas)),
        "ece": _ece(probas, y_idx),
        "classification_report": report,
        "confusion_matrix": confusion_matrix(y_idx, preds).tolist(),
    }


def _pick_model(X_train, y_train, X_val, y_val):
    candidates = {
        "GaussianNB": GaussianNB(),
        "RandomForest": RandomForestClassifier(
            n_estimators=80,
            max_depth=12,
            class_weight="balanced",
            random_state=SEED,
            n_jobs=-1,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(max_depth=8, max_iter=120, random_state=SEED),
    }
    best_name, best_model, best_f1 = None, None, -1.0
    for name, est in candidates.items():
        est.fit(X_train, y_train)
        f1 = f1_score(y_val, est.predict(X_val), average="macro")
        if f1 > best_f1:
            best_f1, best_name, best_model = f1, name, est
    return best_name, best_model, best_f1


def _calibrate(base_model, X_val, y_val):
    frozen = FrozenEstimator(base_model)
    for method in ("sigmoid", "isotonic"):
        cal = CalibratedClassifierCV(estimator=frozen, method=method)
        cal.fit(X_val, y_val)
        ll = log_loss(y_val, cal.predict_proba(X_val))
        yield method, cal, ll


def train_and_export(cfg: TrainConfig | None = None) -> dict:
    cfg = cfg or TrainConfig()
    cfg.bundle_dir.mkdir(parents=True, exist_ok=True)
    cfg.eval_dir.mkdir(parents=True, exist_ok=True)

    search_roots = cfg.data_dirs or [
        REPO_ROOT / "backend" / "app" / "ml" / "data",
        REPO_ROOT / "data",
        REPO_ROOT / "ml_data",
        REPO_ROOT,
    ]
    csv_files = discover_cicids_files(search_roots)
    if csv_files:
        frame, dataset_hashes = load_cicids_frame(csv_files)
        bundle_status = "production"
    else:
        frame, dataset_hashes, bundle_status = _frame_from_synthetic(cfg)

    frame = _prepare_dataframe(frame)
    train_df, val_df, test_df = _block_split(frame)
    _, _, test_opt_df = _dedupe_split(frame)

    class_names = ATTACK_CLASSES
    y_train = [class_names.index(l) for l in train_df["label"]]
    y_val = [class_names.index(l) for l in val_df["label"]]

    X_train = train_df[CICIDS2017_FEATURES].to_numpy(dtype=np.float64)
    X_val = val_df[CICIDS2017_FEATURES].to_numpy(dtype=np.float64)
    X_test = test_df[CICIDS2017_FEATURES].to_numpy(dtype=np.float64)
    X_test_opt = test_opt_df[CICIDS2017_FEATURES].to_numpy(dtype=np.float64)
    y_test = test_df["label"].tolist()
    y_test_opt = test_opt_df["label"].tolist()

    algo_name, base_model, val_f1 = _pick_model(X_train, y_train, X_val, y_val)
    best_method, calibrated, _cal_ll = min(_calibrate(base_model, X_val, y_val), key=lambda t: t[2])

    realistic_metrics = _evaluate_split("realistic_block", calibrated, X_test, y_test, class_names)
    optimistic_metrics = _evaluate_split("optimistic_stratified", calibrated, X_test_opt, y_test_opt, class_names)

    ood = _compute_ood_stats(train_df)
    joblib.dump(calibrated, cfg.bundle_dir / MODEL_NAME)
    (cfg.bundle_dir / PREPROCESSING_NAME).write_text(json.dumps(ood, indent=2), encoding="utf-8")
    (cfg.bundle_dir / CLASSES_NAME).write_text(json.dumps({"classes": class_names}, indent=2), encoding="utf-8")

    metrics_summary = {
        "headline_evaluation": "n/a - demo-synthetic" if bundle_status == "demo-synthetic" else "realistic_block",
        "algorithm": algo_name,
        "calibration_method": best_method,
        "validation_macro_f1": "n/a - demo-synthetic"
        if bundle_status == "demo-synthetic"
        else val_f1,
        "realistic": "n/a - demo-synthetic"
        if bundle_status == "demo-synthetic"
        else {k: realistic_metrics[k] for k in ("accuracy", "macro_f1", "weighted_f1", "log_loss", "ece")},
        "optimistic": "n/a - demo-synthetic"
        if bundle_status == "demo-synthetic"
        else {k: optimistic_metrics[k] for k in ("accuracy", "macro_f1", "weighted_f1", "log_loss", "ece")},
    }

    write_bundle_manifest(
        cfg.bundle_dir,
        version=f"lbro-{bundle_status}-1.0.0",
        status=bundle_status,
        git_commit=_git_commit(),
        dataset_hashes=dataset_hashes,
        metrics_summary=metrics_summary,
        signing_key=cfg.signing_key,
    )

    (cfg.eval_dir / "metrics.json").write_text(
        json.dumps({"realistic": realistic_metrics, "optimistic": optimistic_metrics, "metrics_summary": metrics_summary}, indent=2),
        encoding="utf-8",
    )
    cm = np.array(realistic_metrics["confusion_matrix"])
    pd.DataFrame(cm).to_csv(cfg.eval_dir / "confusion_matrix.csv", index=False)
    if _HAS_PLOTTING:
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=False, fmt="d", cmap="Blues")
        plt.title("Confusion matrix (realistic split)")
        plt.tight_layout()
        plt.savefig(cfg.eval_dir / "confusion_matrix.png")
        plt.close()

    with open(cfg.eval_dir / "classification_report.txt", "w", encoding="utf-8") as f:
        f.write(
            classification_report(
                [class_names.index(l) for l in y_test],
                np.argmax(calibrated.predict_proba(X_test), axis=1),
                target_names=class_names,
                zero_division=0,
            )
        )

    (cfg.eval_dir / "run_metadata.json").write_text(
        json.dumps({"command": " ".join(sys.argv), "git_commit": _git_commit(), "dataset_hashes": dataset_hashes}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(metrics_summary, indent=2))
    return metrics_summary
