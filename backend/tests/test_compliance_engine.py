"""Pure inference engine golden scenarios."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.compliance.engine.pipeline import run_exposure_assessment
from app.compliance.engine.types import (
    AssetInput,
    ClassificationInput,
    EngineConfigInput,
    IncidentContextInput,
    ResidencyInput,
)


def _ts() -> datetime:
    return datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def test_benign_produces_no_techniques_or_obligations():
    result = run_exposure_assessment(
        ClassificationInput("BENIGN", 0.9, "model", False, False),
        IncidentContextInput(_ts(), None, (), False, False),
        (),
        EngineConfigInput("inferred", 0.75),
    )
    assert result.techniques == []
    assert result.obligations == []


def test_dos_availability_only_no_breach_trigger():
    result = run_exposure_assessment(
        ClassificationInput("DoS Hulk", 0.92, "model", False, False),
        IncidentContextInput(_ts(), None, ("EU",), True, False),
        (
            AssetInput(
                "a1",
                "web",
                ("personal_identifiers",),
                (ResidencyInput("EU", 1000, "exact"),),
                "confirmed",
                "high",
                1.0,
            ),
        ),
        EngineConfigInput("inferred", 0.75),
    )
    assert result.no_breach_notification_trigger
    assert not any(o.law == "GDPR" for o in result.obligations)


def test_ssh_patator_auth_asset_triggers_gdpr_evaluation():
    result = run_exposure_assessment(
        ClassificationInput("SSH-Patator", 0.88, "model", False, False),
        IncidentContextInput(_ts(), None, (), True, False),
        (
            AssetInput(
                "auth",
                "identity",
                ("authentication_credentials", "personal_identifiers"),
                (
                    ResidencyInput("EU", 500, "exact"),
                    ResidencyInput("IN", 200, "exact"),
                ),
                "confirmed",
                "high",
                1.0,
            ),
        ),
        EngineConfigInput("inferred", 0.75),
    )
    assert "authentication_credentials" in result.exposed_categories
    gdpr = [o for o in result.obligations if o.law == "GDPR"]
    assert gdpr
    assert gdpr[0].deadline_at is not None


def test_heuristic_classification_is_provisional():
    result = run_exposure_assessment(
        ClassificationInput("SSH-Patator", 0.5, "heuristic", True, False),
        IncidentContextInput(_ts(), None, (), True, False),
        (
            AssetInput(
                "auth",
                "id",
                ("authentication_credentials",),
                (ResidencyInput("EU", 10, "exact"),),
                "confirmed",
                "high",
                1.0,
            ),
        ),
        EngineConfigInput("inferred", 0.75),
    )
    assert result.status == "provisional"
    assert result.obligations[0].provisional


def test_deduplication_unknown_bounds():
    result = run_exposure_assessment(
        ClassificationInput("SSH-Patator", 0.9, "model", False, False),
        IncidentContextInput(_ts(), None, (), True, False),
        (
            AssetInput(
                "a1",
                "db1",
                ("personal_identifiers",),
                (ResidencyInput("EU", 100, "exact"),),
                "confirmed",
                "high",
                1.0,
            ),
            AssetInput(
                "a2",
                "db2",
                ("personal_identifiers",),
                (ResidencyInput("EU", 80, "exact"),),
                "confirmed",
                "high",
                1.0,
            ),
        ),
        EngineConfigInput("inferred", 0.75),
    )
    eu = next(j for j in result.jurisdiction_exposure if j.jurisdiction_code == "EU")
    assert eu.lower_bound == 100
    assert eu.upper_bound == 180
    assert eu.deduplication_unknown


def test_deterministic_inputs_hash():
    args = (
        ClassificationInput("PortScan", 0.8, "model", False, False),
        IncidentContextInput(_ts(), None, ("US",), False, False),
        (),
        EngineConfigInput("hybrid", 0.75),
    )
    r1 = run_exposure_assessment(*args)
    r2 = run_exposure_assessment(*args)
    assert r1.inputs_hash == r2.inputs_hash
