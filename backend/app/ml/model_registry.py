"""Model registry — tracks model versions, metrics, and evaluation reports."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import settings

REGISTRY_PATH = Path(settings.ML_MODEL_PATH).parent / "registry.json"


def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {"models": [], "active_version": None}


def _save_registry(data: dict) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)


def register_model(
    version: str,
    accuracy: float,
    precision: float,
    recall: float,
    f1: float,
    confusion_matrix: Optional[list] = None,
    notes: str = "",
) -> dict:
    registry = _load_registry()
    entry = {
        "version": version,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "confusion_matrix": confusion_matrix,
        "notes": notes,
    }
    registry["models"].append(entry)
    registry["active_version"] = version
    _save_registry(registry)
    return entry


def get_active_model_info() -> dict:
    registry = _load_registry()
    active = registry.get("active_version")
    for m in registry.get("models", []):
        if m["version"] == active:
            return m
    return {
        "version": settings.ML_MODEL_VERSION,
        "metrics": {},
        "registered_at": None,
        "notes": "No registry entry found",
    }


def list_models() -> list[dict]:
    return _load_registry().get("models", [])
