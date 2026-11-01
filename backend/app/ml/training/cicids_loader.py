"""Load and clean CICIDS2017 MachineLearningCSV files."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.features import CICIDS2017_FEATURES
from app.ml.training.labels import normalize_label

# Public dataset column name for destination port differs from our canonical snake_case list.
CSV_COLUMN_MAP = {
    " Destination Port": "destination_port",
    "Destination Port": "destination_port",
}


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_cicids_files(search_roots: list[Path]) -> list[Path]:
    """Find MachineLearningCSV*.csv under known roots."""
    found: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        found.extend(sorted(root.glob("**/MachineLearningCSV*.csv")))
        found.extend(sorted(root.glob("**/*.csv")))
    # De-dupe while preserving order
    seen = set()
    unique = []
    for p in found:
        if p.resolve() in seen:
            continue
        seen.add(p.resolve())
        if "MachineLearning" in p.name or "cicids" in p.name.lower():
            unique.append(p)
    return unique


def load_cicids_frame(csv_paths: list[Path]) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Load one or more CSVs, normalize columns to CICIDS2017_FEATURES order.

    Returns frame with columns FEATURES + ``label``, and a map of source file -> sha256.
    """
    if not csv_paths:
        raise FileNotFoundError("No CICIDS2017 CSV files provided")

    hashes: dict[str, str] = {}
    frames: list[pd.DataFrame] = []
    for path in csv_paths:
        hashes[str(path.name)] = _file_sha256(path)
        df = pd.read_csv(path, low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        # Drop duplicate Fwd Header Length column deterministically (keep first).
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated()]

        rename = {}
        for col in df.columns:
            if col in CSV_COLUMN_MAP:
                rename[col] = CSV_COLUMN_MAP[col]
            else:
                snake = col.strip().lower().replace(" ", "_")
                rename[col] = snake
        df = df.rename(columns=rename)

        label_col = None
        for candidate in ("label", " Label", "attack", "class"):
            if candidate in df.columns:
                label_col = candidate
                break
        if label_col is None:
            # Last column is typically Label in CICIDS exports
            label_col = df.columns[-1]

        df["label"] = df[label_col].apply(normalize_label)
        df = df.dropna(subset=["label"])

        feature_cols = [f for f in CICIDS2017_FEATURES if f in df.columns]
        missing = set(CICIDS2017_FEATURES) - set(feature_cols)
        if missing:
            for m in missing:
                df[m] = 0.0
        frames.append(df[CICIDS2017_FEATURES + ["label"]])

    combined = pd.concat(frames, ignore_index=True)
    combined.replace([np.inf, -np.inf], np.nan, inplace=True)
    return combined, hashes
