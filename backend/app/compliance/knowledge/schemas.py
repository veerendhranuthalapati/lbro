"""Pydantic schemas for versioned compliance knowledge JSON files."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Likelihood = Literal["likely", "possible"]
VerificationStatus = Literal["verified", "unverified"]
LegalReviewStatus = Literal["unreviewed", "reviewed"]
CountBasis = Literal["exact", "estimated", "unknown"]


class SourceRef(BaseModel):
    title: str
    url: str
    note: str | None = None


class TechniqueLink(BaseModel):
    technique_id: str = Field(..., pattern=r"^T\d{4}(\.\d{3})?$")
    name: str
    tactics: list[str]
    likelihood: Likelihood
    rationale: str
    confirms_exfiltration: bool = False


class AttackClassMapping(BaseModel):
    techniques: list[TechniqueLink] = Field(default_factory=list)
    unmapped_reason: str | None = None


class AttackToTechniqueFile(BaseModel):
    schema_version: str
    content_version: str
    last_reviewed: str
    attack_enterprise_version: str
    attack_spec_version: str
    sources: list[SourceRef]
    mappings: dict[str, AttackClassMapping]


class DataCategoryDef(BaseModel):
    label: str
    is_personal_data: bool
    is_special_category: bool


class DataCategoriesFile(BaseModel):
    schema_version: str
    content_version: str
    last_reviewed: str
    sources: list[SourceRef]
    categories: dict[str, DataCategoryDef]


class TechniqueImpact(BaseModel):
    impact_types: list[Literal["confidentiality", "integrity", "availability"]]
    data_categories_at_risk: list[str]
    exposure_assumption: Literal[
        "data_at_rest_on_accessed_asset",
        "data_in_transit",
        "credentials_only",
        "none",
    ]
    rationale: str


class TechniqueToDataFile(BaseModel):
    schema_version: str
    content_version: str
    last_reviewed: str
    sources: list[SourceRef]
    techniques: dict[str, TechniqueImpact]


class DeadlineSpec(BaseModel):
    amount: int | None
    unit: Literal["hours", "days", "without_delay", "without_unreasonable_delay", "undue_delay"]
    clock_start: Literal["awareness", "confirmation", "detection", "discovery"]


class ObligationSpec(BaseModel):
    obligation_id: str
    description: str
    recipient_type: Literal["regulator", "data_subject", "media", "partner"]
    recipient: str
    deadline: DeadlineSpec
    is_conditional_on_risk_assessment: bool = False


class AppliesWhen(BaseModel):
    requires_personal_data: bool | None = None
    requires_categories_any: list[str] | None = None
    requires_impact_types: list[str] | None = None
    excludes_availability_only: bool | None = None
    min_record_count_point: int | None = None
    requires_cyber_incident_reporting: bool | None = None


class Citation(BaseModel):
    section: str
    url: str


class LegalRule(BaseModel):
    rule_id: str
    rule_version: str
    law: str
    jurisdiction_codes: list[str]
    applies_when: AppliesWhen
    obligations: list[ObligationSpec]
    citations: list[Citation]
    verification_status: VerificationStatus
    legal_review_status: LegalReviewStatus
    notes: str | None = None


class LawsFile(BaseModel):
    schema_version: str
    content_version: str
    last_reviewed: str
    disclaimer: str
    sources: list[SourceRef]
    rules: list[LegalRule]


class KnowledgeBundle(BaseModel):
    """Validated in-memory bundle returned by the loader."""

    attack_to_technique: AttackToTechniqueFile
    technique_to_data: TechniqueToDataFile
    data_categories: DataCategoriesFile
    laws: LawsFile

    @model_validator(mode="after")
    def cross_validate_references(self) -> KnowledgeBundle:
        cat_keys = set(self.data_categories.categories.keys())
        atk = self.attack_to_technique
        ttd = self.technique_to_data
        referenced_techniques: set[str] = set()
        for class_name, mapping in atk.mappings.items():
            for link in mapping.techniques:
                referenced_techniques.add(link.technique_id.split(".")[0])
                if link.technique_id.split(".")[0] not in ttd.techniques:
                    raise ValueError(
                        f"technique_to_data missing {link.technique_id} referenced by {class_name}"
                    )
        for tid, impact in ttd.techniques.items():
            for c in impact.data_categories_at_risk:
                if c not in cat_keys:
                    raise ValueError(f"Unknown data category {c} on technique {tid}")
        for rule in self.laws.rules:
            if not rule.citations:
                raise ValueError(f"Rule {rule.rule_id} has no citations")
            cats = rule.applies_when.requires_categories_any or []
            for c in cats:
                if c not in cat_keys:
                    raise ValueError(f"Rule {rule.rule_id} references unknown category {c}")
        return self
