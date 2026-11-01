"""Coverage for compliance engine serialization."""
from __future__ import annotations

from datetime import datetime, timezone

from app.compliance.engine.serialize import assessment_result_to_dict, obligation_to_dict
from app.compliance.engine.types import InferredObligation


def test_obligation_to_dict_formats_datetimes():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ob = InferredObligation(
        rule_id="r1",
        rule_version="1",
        obligation_id="o1",
        law="GDPR",
        description="Notify authority",
        recipient_type="regulator",
        recipient="DPA",
        deadline_at=start,
        clock_start_at=start,
        clock_start_source="detected_at",
        provisional=False,
        requires_assessment=False,
        origin="inferred",
        verification_status="unverified",
        legal_review_status="unreviewed",
    )
    d = obligation_to_dict(ob)
    assert d["deadline_at"].startswith("2026")


def test_assessment_result_to_dict_minimal():
    from app.compliance.engine.pipeline import run_exposure_assessment
    from app.compliance.engine.types import ClassificationInput, EngineConfigInput, IncidentContextInput

    result = run_exposure_assessment(
        ClassificationInput("BENIGN", 0.9, "model", False, False),
        IncidentContextInput(datetime.now(timezone.utc), None, (), False, False),
        (),
        EngineConfigInput("manual", 0.75),
    )
    d = assessment_result_to_dict(result)
    assert d["disclaimer"]


def test_trace_to_json():
    from app.compliance.engine.serialize import trace_to_json
    from app.compliance.engine.types import TraceStep

    out = trace_to_json([TraceStep("step", {"k": "v"})])
    assert out[0]["step"] == "step"
