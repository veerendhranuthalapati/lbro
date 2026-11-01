"""Asset data map API schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


ASSET_TYPES = {
    "database",
    "object_storage",
    "file_share",
    "saas_application",
    "endpoint",
    "server",
    "api",
    "backup",
    "other",
}
CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}
COUNT_BASIS = {"exact", "estimated", "unknown"}


class ResidencyCreate(BaseModel):
    jurisdiction_code: str = Field(..., max_length=20)
    record_count: Optional[int] = Field(None, ge=0)
    count_basis: str = Field("unknown", max_length=20)
    as_of: Optional[date] = None
    data_category: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("count_basis")
    @classmethod
    def validate_basis(cls, v: str) -> str:
        if v not in COUNT_BASIS:
            raise ValueError(f"count_basis must be one of {sorted(COUNT_BASIS)}")
        return v


class ResidencyResponse(ResidencyCreate):
    id: uuid.UUID

    model_config = {"from_attributes": True}


class AssetCreate(BaseModel):
    name: str = Field(..., max_length=255)
    asset_type: str = Field(..., max_length=50)
    environment: Optional[str] = Field(None, max_length=50)
    owner: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    classification: str = Field("internal", max_length=50)
    criticality: Optional[str] = Field(None, max_length=50)
    data_categories: List[str] = Field(default_factory=list, max_length=50)
    encrypted_at_rest: Optional[bool] = None
    identifiers: List[dict[str, Any]] = Field(default_factory=list, max_length=100)
    is_active: bool = True
    residency: List[ResidencyCreate] = Field(default_factory=list, max_length=100)

    @field_validator("asset_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ASSET_TYPES:
            raise ValueError(f"asset_type must be one of {sorted(ASSET_TYPES)}")
        return v

    @field_validator("classification")
    @classmethod
    def validate_class(cls, v: str) -> str:
        if v not in CLASSIFICATIONS:
            raise ValueError(f"classification must be one of {sorted(CLASSIFICATIONS)}")
        return v


class AssetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    asset_type: Optional[str] = Field(None, max_length=50)
    environment: Optional[str] = Field(None, max_length=50)
    owner: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    classification: Optional[str] = Field(None, max_length=50)
    criticality: Optional[str] = Field(None, max_length=50)
    data_categories: Optional[List[str]] = Field(None, max_length=50)
    encrypted_at_rest: Optional[bool] = None
    identifiers: Optional[List[dict[str, Any]]] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    residency: Optional[List[ResidencyCreate]] = Field(None, max_length=100)


class AssetResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    asset_type: str
    environment: Optional[str]
    owner: Optional[str]
    description: Optional[str]
    classification: str
    criticality: Optional[str]
    data_categories: List[str]
    encrypted_at_rest: Optional[bool]
    identifiers: List[dict[str, Any]]
    is_active: bool
    residency: List[ResidencyResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssetListResponse(BaseModel):
    items: List[AssetResponse]
    total: int
    page: int
    page_size: int


class AssetImportRequest(BaseModel):
    dry_run: bool = True
    rows: List[AssetCreate] = Field(..., max_length=500)


class AssetImportRowError(BaseModel):
    row: int
    error: str


class AssetImportResult(BaseModel):
    dry_run: bool
    valid_count: int
    errors: List[AssetImportRowError]
    imported: int = 0


class ExposureSimulationRequest(BaseModel):
    attack_category: str = Field(..., max_length=100)
    confidence: float = Field(0.85, ge=0.0, le=1.0)


class IncidentAssetLinkRequest(BaseModel):
    asset_id: uuid.UUID
    exposure_fraction: float = Field(1.0, ge=0.0, le=1.0)


class IncidentAssetUpdateRequest(BaseModel):
    exposure_fraction: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[str] = Field(None, pattern="^(suggested|confirmed|rejected)$")


class IncidentAssetResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    asset_id: uuid.UUID
    asset_name: str
    link_source: str
    match_reason: Optional[str]
    match_confidence: str
    exposure_fraction: float
    status: str
    confirmed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ExposureAssessmentResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    computed_at: datetime
    engine_version: str
    knowledge_versions: dict[str, str]
    inputs_hash: str
    overall_confidence: float
    status: str
    results: dict[str, Any]
    trace: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class ObligationDecisionRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=2000)


class ComplianceInferenceModeUpdate(BaseModel):
    compliance_inference_mode: str = Field(..., pattern="^(manual|hybrid|inferred)$")
