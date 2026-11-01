#!/usr/bin/env python3
"""
Sign the ML bundle during Docker image build or release pipeline.

Requires ML_MODEL_SIGNING_KEY in the environment (CI secret or build-arg).
Rejects missing keys, short keys, and known test keys when ENVIRONMENT=production.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("ENVIRONMENT", os.environ.get("ENVIRONMENT", "production"))

from app.ml.signing_policy import validate_signing_key_for_environment  # noqa: E402


def main() -> int:
    key = os.environ.get("ML_MODEL_SIGNING_KEY", "").strip()
    env = os.environ.get("ENVIRONMENT", "production")
    try:
        validate_signing_key_for_environment(key, env)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    sign_path = REPO_ROOT / "scripts" / "sign_model.py"
    spec = importlib.util.spec_from_file_location("lbro_sign_model", sign_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    bundle_dir = Path(
        os.environ.get(
            "ML_MODEL_BUNDLE_DIR",
            str(BACKEND / "app" / "ml" / "models" / "bundle"),
        )
    )
    sys.argv = [
        "sign_bundle_at_build.py",
        "--bundle-dir",
        str(bundle_dir),
    ]
    return int(mod.main())


if __name__ == "__main__":
    raise SystemExit(main())
