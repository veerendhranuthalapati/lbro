"""Load and validate attack guide JSON (fail fast at startup)."""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.knowledge.schemas import AttackGuideEntry, AttackGuidesFile
from app.ml.features import ATTACK_CLASSES

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent
GUIDES_FILE = KNOWLEDGE_DIR / "attack_guides.json"

DECISION_SUPPORT_DISCLAIMER = (
    "LBRO detections are leads based on network-flow statistics and heuristics, not proof of compromise. "
    "Verify with logs, endpoints, and your incident process before destructive action. "
    "Preserve evidence before wiping or rebuilding systems."
)


@lru_cache(maxsize=1)
def load_attack_guides() -> AttackGuidesFile:
    if not GUIDES_FILE.is_file():
        raise FileNotFoundError(f"Missing attack guides: {GUIDES_FILE}")
    data = json.loads(GUIDES_FILE.read_text(encoding="utf-8"))
    bundle = AttackGuidesFile.model_validate(data)
    missing = [c for c in ATTACK_CLASSES if c not in bundle.guides]
    if missing:
        raise ValueError(f"Attack guides missing entries for: {missing}")
    extra = [k for k in bundle.guides if k not in ATTACK_CLASSES]
    if extra:
        raise ValueError(f"Orphan attack guide keys (not in ATTACK_CLASSES): {extra}")
    logger.info(
        "Attack guides loaded content_version=%s classes=%s",
        bundle.content_version,
        len(bundle.guides),
    )
    return bundle


def get_guide(class_id: str) -> AttackGuideEntry | None:
    bundle = load_attack_guides()
    return bundle.guides.get(class_id)
