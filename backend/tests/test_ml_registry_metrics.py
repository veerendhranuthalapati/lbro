"""Regression tests: CICIDS2017 bundle metrics must surface in the API, not N/A."""

from app.ml.features import ATTACK_CLASSES, CICIDS2017_FEATURES
from app.ml.model_registry import _with_realistic_block


def test_held_out_metrics_exposed_as_realistic():
    summary = {"held_out_test": {"accuracy": 0.9983, "macro_f1": 0.8773, "weighted_f1": 0.9983}}
    out = _with_realistic_block(summary)
    assert out["realistic"] == {"accuracy": 0.9983, "macro_f1": 0.8773, "weighted_f1": 0.9983}


def test_existing_realistic_block_is_not_overwritten():
    summary = {"realistic": {"macro_f1": 0.5}, "held_out_test": {"macro_f1": 0.9}}
    assert _with_realistic_block(summary)["realistic"] == {"macro_f1": 0.5}


def test_summary_without_held_out_is_unchanged():
    assert _with_realistic_block({"algorithm": "x"}) == {"algorithm": "x"}


def test_cicids_feature_and_class_counts():
    assert len(CICIDS2017_FEATURES) == 77
    assert len(ATTACK_CLASSES) == 15
