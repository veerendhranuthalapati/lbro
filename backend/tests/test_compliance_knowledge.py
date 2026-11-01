"""Knowledge base validation — every file, cross-refs, ATTACK_CLASSES coverage."""
from __future__ import annotations

from app.compliance.knowledge.loader import load_knowledge_bundle, reload_knowledge_for_tests
from app.ml.features import ATTACK_CLASSES


def test_knowledge_bundle_loads():
    reload_knowledge_for_tests()
    bundle = load_knowledge_bundle()
    assert bundle.laws.rules
    assert len(bundle.data_categories.categories) >= 10


def test_every_attack_class_mapped():
    bundle = load_knowledge_bundle()
    for cls in ATTACK_CLASSES:
        assert cls in bundle.attack_to_technique.mappings


def test_benign_has_no_techniques():
    bundle = load_knowledge_bundle()
    m = bundle.attack_to_technique.mappings["BENIGN"]
    assert m.techniques == []
    assert m.unmapped_reason


def test_every_rule_has_citation():
    bundle = load_knowledge_bundle()
    for rule in bundle.laws.rules:
        assert rule.citations
        assert rule.verification_status in ("verified", "unverified")
        assert rule.legal_review_status == "unreviewed"
