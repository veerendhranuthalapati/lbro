"""Training pipeline and loader unit tests (tiny synthetic fixture — not real CICIDS2017)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.ml.training.labels import MIN_TEST_SUPPORT_FOR_REPORTING, normalize_label
from app.ml.training.pipeline import TrainConfig, train_and_export


def test_normalize_label_benign():
    assert normalize_label("BENIGN") == "BENIGN"


def test_normalize_label_strips_whitespace():
    assert normalize_label("  PortScan  ") == "PortScan"


def test_min_test_support_constant():
    assert MIN_TEST_SUPPORT_FOR_REPORTING == 30


@pytest.mark.slow
def test_train_and_export_reproducible_metrics(tmp_path: Path):
    key = "test-ml-signing-key-minimum-32-characters-long"
    cfg = TrainConfig(
        fast=True,
        max_rows_per_class=20,
        bundle_dir=tmp_path / "bundle",
        eval_dir=tmp_path / "eval",
        signing_key=key,
    )
    m1 = train_and_export(cfg)
    m2 = train_and_export(cfg)
    assert m1["realistic"]["macro_f1"] == m2["realistic"]["macro_f1"]
    assert (tmp_path / "bundle" / "manifest.sig").is_file()
