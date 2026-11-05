#!/usr/bin/env python3
"""Bootstrap a sklearn-compatible signed bundle inside the API container runtime."""
from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from app.ml.bundle_io import MODEL_NAME, PREPROCESSING_NAME, CLASSES_NAME, write_bundle_manifest, load_verified_bundle
from app.ml.features import ATTACK_CLASSES, CICIDS2017_FEATURES

BUNDLE = Path(os.environ.get("ML_MODEL_BUNDLE_DIR", "/app/app/ml/models/bundle"))


def main() -> None:
    key = os.environ.get("ML_MODEL_SIGNING_KEY")
    if not key:
        raise SystemExit("ML_MODEL_SIGNING_KEY required")

    rng = np.random.RandomState(42)
    n = 800
    X = rng.uniform(0, 1000, size=(n, len(CICIDS2017_FEATURES)))
    y = rng.choice(ATTACK_CLASSES, size=n)

    model = HistGradientBoostingClassifier(max_iter=100, random_state=42)
    model.fit(X, y)

    medians = {f: float(np.median(X[:, i])) for i, f in enumerate(CICIDS2017_FEATURES)}
    low = {f: float(np.percentile(X[:, i], 1)) for i, f in enumerate(CICIDS2017_FEATURES)}
    high = {f: float(np.percentile(X[:, i], 99)) for i, f in enumerate(CICIDS2017_FEATURES)}

    BUNDLE.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, BUNDLE / MODEL_NAME)
    (BUNDLE / PREPROCESSING_NAME).write_text(
        json.dumps({"medians": medians, "low_bounds": low, "high_bounds": high}, indent=2),
        encoding="utf-8",
    )
    (BUNDLE / CLASSES_NAME).write_text(
        json.dumps({"classes": list(model.classes_)}, indent=2),
        encoding="utf-8",
    )
    write_bundle_manifest(
        BUNDLE,
        version="1.0.0-docker-bootstrap",
        status="demo-synthetic",
        git_commit="docker-bootstrap",
        dataset_hashes={"synthetic": "n/a"},
        metrics_summary={"note": "container-bootstrap for red-team eval"},
        signing_key=key,
    )
    b = load_verified_bundle(BUNDLE)
    print("loaded_ok", b.version, b.signature_verified, len(b.classes))


if __name__ == "__main__":
    main()
