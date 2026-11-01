#!/usr/bin/env python3
"""CLI entry point for LBRO ML training pipeline."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.training.pipeline import TrainConfig, train_and_export  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Train LBRO CICIDS2017 classifier and export signed bundle")
    parser.add_argument("--fast", action="store_true", help="Small synthetic dataset for CI")
    parser.add_argument("--max-rows-per-class", type=int, default=None)
    parser.add_argument("--bundle-dir", type=Path, default=None)
    parser.add_argument("--sign", action="store_true", help="Sign manifest using ML_MODEL_SIGNING_KEY")
    args = parser.parse_args()

    signing_key = os.environ.get("ML_MODEL_SIGNING_KEY") if args.sign else None
    cfg = TrainConfig(
        fast=args.fast,
        max_rows_per_class=args.max_rows_per_class,
        bundle_dir=args.bundle_dir or TrainConfig.bundle_dir,
        signing_key=signing_key,
    )
    train_and_export(cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
