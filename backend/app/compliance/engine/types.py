"""Typed inputs/outputs for the exposure inference engine (pure, no DB)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

InferenceMode = Literal["manual", "hybrid", "inferred"]
MatchConfidence = Literal["high", "medium", "low"]
LinkStatus = Literal["suggested", "confirmed", "rejected"]
AssessmentStatus = Literal["provisional", "confirmed", "superseded"]
ObligationOrigin = Literal["manual", "inferred", "both"]


@dataclass(frozen=True)
class ClassificationInput:
    attack_category: str | None
    confidence: float
    source: str
    needs_review: bool
    ood_flag: bool


@dataclass(frozen=True)
class ResidencyInput:
    jurisdiction_code: str
    record_count: int | None
    count_basis: str
    data_category: str | None = None


@dataclass(frozen=True)
class AssetInput:
    asset_id: str
    name: str
    data_categories: tuple[str, ...]
    residency: tuple[ResidencyInput, ...]
    link_status: LinkStatus
    match_confidence: MatchConfidence
    exposure_fraction: float


@dataclass(frozen=True)
class IncidentContextInput:
    detected_at: datetime
    confirmed_at: datetime | None
    manual_jurisdictions: tuple[str, ...]
    personal_data_involved: bool
    health_data_involved: bool


@dataclass(frozen=True)
class EngineConfigInput:
    inference_mode: InferenceMode
    ml_review_threshold: float


@dataclass
class JurisdictionExposure:
    jurisdiction_code: str
    lower_bound: int | None
    upper_bound: int | None
    point_estimate: int | None
    basis: str
    deduplication_unknown: bool = True


@dataclass
class InferredObligation:
    rule_id: str
    rule_version: str
    obligation_id: str
    law: str
    description: str
    recipient_type: str
    recipient: str
    deadline_at: datetime | None
    clock_start_at: datetime
    clock_start_source: str
    provisional: bool
    requires_assessment: bool
    origin: ObligationOrigin
    verification_status: str
    legal_review_status: str


@dataclass
class EngineWarning:
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceStep:
    step: str
    detail: dict[str, Any]


@dataclass
class ExposureAssessmentResult:
    status: AssessmentStatus
    overall_confidence: float
    provisional_reasons: list[str]
    techniques: list[dict[str, Any]]
    exposed_categories: list[str]
    jurisdiction_exposure: list[JurisdictionExposure]
    obligations: list[InferredObligation]
    warnings: list[EngineWarning]
    trace: list[TraceStep]
    no_breach_notification_trigger: bool
    no_breach_explanation: str | None
    inputs_hash: str
    disclaimer: str
