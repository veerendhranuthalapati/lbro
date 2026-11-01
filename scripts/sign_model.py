#!/usr/bin/env python3
"""Sign an ML bundle manifest (writes manifest.sig). Exit 0 on success."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.bundle_io import MANIFEST_NAME, SIGNATURE_NAME, compute_manifest_hmac  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign ML model bundle manifest with HMAC-SHA256")
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=BACKEND / "app" / "ml" / "models" / "bundle",
    )
    parser.add_argument("--signing-key", default=None, help="Defaults to ML_MODEL_SIGNING_KEY env var")
    args = parser.parse_args()

    key = args.signing_key or os.environ.get("ML_MODEL_SIGNING_KEY")
    if not key:
        print("ERROR: provide --signing-key or ML_MODEL_SIGNING_KEY", file=sys.stderr)
        return 2

    manifest_path = args.bundle_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"ERROR: missing {manifest_path}", file=sys.stderr)
        return 1

    manifest_bytes = manifest_path.read_bytes()
    sig = compute_manifest_hmac(manifest_bytes, key)
    (args.bundle_dir / SIGNATURE_NAME).write_text(sig, encoding="utf-8")
    print(f"Signed {args.bundle_dir / SIGNATURE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
