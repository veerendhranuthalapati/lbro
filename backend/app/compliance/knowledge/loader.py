"""Load and validate compliance knowledge files (fail fast at startup)."""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.compliance.knowledge.schemas import (
    AttackToTechniqueFile,
    DataCategoriesFile,
    KnowledgeBundle,
    LawsFile,
    TechniqueToDataFile,
)
from app.ml.features import ATTACK_CLASSES

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent

ENGINE_VERSION = "1.0.0"


def _read_json(name: str) -> dict[str, Any]:
    path = KNOWLEDGE_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Missing knowledge file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_knowledge_bundle() -> KnowledgeBundle:
    """Parse and cross-validate all knowledge files once per process."""
    bundle = KnowledgeBundle(
        attack_to_technique=AttackToTechniqueFile.model_validate(_read_json("attack_to_technique.json")),
        technique_to_data=TechniqueToDataFile.model_validate(_read_json("technique_to_data.json")),
        data_categories=DataCategoriesFile.model_validate(_read_json("data_categories.json")),
        laws=LawsFile.model_validate(_read_json("laws.json")),
    )
    _assert_attack_classes_covered(bundle)
    logger.info(
        "Compliance knowledge loaded attack=%s laws=%s categories=%s",
        bundle.attack_to_technique.content_version,
        bundle.laws.content_version,
        len(bundle.data_categories.categories),
    )
    return bundle


def _assert_attack_classes_covered(bundle: KnowledgeBundle) -> None:
    """Every ATTACK_CLASSES entry must appear in mappings (explicit unmapped OK)."""
    missing = [c for c in ATTACK_CLASSES if c not in bundle.attack_to_technique.mappings]
    if missing:
        raise ValueError(f"attack_to_technique.json missing ATTACK_CLASSES: {missing}")


def knowledge_versions_snapshot() -> dict[str, str]:
    b = load_knowledge_bundle()
    return {
        "engine_version": ENGINE_VERSION,
        "attack_to_technique": b.attack_to_technique.content_version,
        "technique_to_data": b.technique_to_data.content_version,
        "data_categories": b.data_categories.content_version,
        "laws": b.laws.content_version,
        "attack_enterprise_version": b.attack_to_technique.attack_enterprise_version,
    }


def reload_knowledge_for_tests() -> None:
    """Clear cache after test fixtures swap knowledge files."""
    load_knowledge_bundle.cache_clear()
