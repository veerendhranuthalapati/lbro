"""Serialize engine dataclasses for JSON persistence and API responses."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.compliance.engine.types import ExposureAssessmentResult, InferredObligation, TraceStep


def obligation_to_dict(ob: InferredObligation) -> dict[str, Any]:
    d = asdict(ob)
    if d.get("deadline_at"):
        d["deadline_at"] = ob.deadline_at.isoformat() if ob.deadline_at else None
    if d.get("clock_start_at"):
        d["clock_start_at"] = ob.clock_start_at.isoformat()
    return d


def assessment_result_to_dict(result: ExposureAssessmentResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "overall_confidence": result.overall_confidence,
        "provisional_reasons": result.provisional_reasons,
        "techniques": result.techniques,
        "exposed_categories": result.exposed_categories,
        "jurisdiction_exposure": [asdict(j) for j in result.jurisdiction_exposure],
        "obligations": [obligation_to_dict(o) for o in result.obligations],
        "warnings": [asdict(w) for w in result.warnings],
        "no_breach_notification_trigger": result.no_breach_notification_trigger,
        "no_breach_explanation": result.no_breach_explanation,
        "inputs_hash": result.inputs_hash,
        "disclaimer": result.disclaimer,
    }


def trace_to_json(trace: list[TraceStep]) -> list[dict[str, Any]]:
    return [{"step": t.step, "detail": t.detail} for t in trace]
