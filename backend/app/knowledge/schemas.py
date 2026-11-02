"""Pydantic schemas for user-facing attack guide content."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class MitreTechniqueRef(BaseModel):
    technique_id: str = Field(..., pattern=r"^T\d{4}(\.\d{3})?$")
    name: str


class PreventionGroup(BaseModel):
    people: list[str] = Field(default_factory=list)
    process: list[str] = Field(default_factory=list)
    technology: list[str] = Field(default_factory=list)


class AttackGuideEntry(BaseModel):
    class_id: str
    title: str
    summary_plain: str
    how_it_works: str
    why_it_matters: str
    typical_indicators: list[str]
    immediate_actions: list[str]
    containment: list[str]
    recovery: list[str]
    prevention: PreventionGroup
    detection_tips: list[str]
    mitre_techniques: list[MitreTechniqueRef]
    data_at_risk_hint: str
    references: list[HttpUrl]
    content_version: str
    last_reviewed: str
    review_status: Literal["unreviewed", "reviewed"] = "unreviewed"


class AttackGuidesFile(BaseModel):
    schema_version: str
    content_version: str
    last_reviewed: str
    attack_enterprise_version: str
    disclaimer: str
    mitre_attribution: str
    guides: dict[str, AttackGuideEntry]
