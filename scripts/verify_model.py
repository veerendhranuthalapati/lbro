#!/usr/bin/env python3
"""Verify ML bundle integrity and HMAC signature. Exit 0 when valid."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ML_ALLOW_UNSIGNED_MODEL", "true")

from app.config import settings  # noqa: E402
from app.ml.bundle_io import BundleLoadError, load_verified_bundle, verify_bundle_directory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ML model bundle hashes and signature")
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=BACKEND / "app" / "ml" / "models" / "bundle",
    )
    parser.add_argument("--load-model", action="store_true", help="Also joblib-load the model after verify")
    args = parser.parse_args()

    settings.ML_MODEL_BUNDLE_DIR = str(args.bundle_dir)

    try:
        verify_bundle_directory(args.bundle_dir)
        print("Manifest and file hashes OK")
        if args.load_model:
            bundle = load_verified_bundle(args.bundle_dir)
            print(f"Model loaded: version={bundle.version} status={bundle.status} verified={bundle.signature_verified}")
        return 0
    except BundleLoadError as exc:
        print(f"VERIFY FAILED [{exc.reason_code}]: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
