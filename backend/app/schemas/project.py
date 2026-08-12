"""Project Pydantic schemas."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


def _slugify(name: str) -> str:
    """Convert a project name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug[:100] or "project"


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    environment: str = "production"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty")
        if len(v) > 200:
            raise ValueError("Project name must be 200 characters or fewer")
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {sorted(allowed)}")
        return v


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    environment: Optional[str] = None
    status: Optional[str] = None

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {sorted(allowed)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"active", "archived"}
        if v not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return v


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    environment: str
    status: str
    owner_id: Optional[uuid.UUID]
    api_key_prefix: str
    created_at: datetime
    updated_at: datetime
    my_role: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    email: str
    full_name: Optional[str] = None
    is_owner: bool = False
    invited_by: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectMemberUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"admin", "analyst", "viewer"}
        if v not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}")
        return v


class ProjectInvitationCreate(BaseModel):
    email: str
    role: str = "analyst"

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not v or "@" not in v:
            raise ValueError("A valid email address is required")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"admin", "analyst", "viewer"}
        if v not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}")
        return v


class ProjectInvitationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    invited_email: str
    role: str
    invited_by: Optional[uuid.UUID]
    status: str
    expires_at: datetime
    created_at: datetime
    project_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectInvitationCreatedResponse(ProjectInvitationResponse):
    """Token returned once for sharing (no email sent unless configured)."""
    invite_token: str


class ProjectInvitationListResponse(BaseModel):
    items: list[ProjectInvitationResponse]
    total: int


class ProjectInvitationAccept(BaseModel):
    token: Optional[str] = None


class ProjectMemberCreate(BaseModel):
    user_id: uuid.UUID
    role: str = "analyst"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"admin", "analyst", "viewer"}
        if v not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}")
        return v


class ProjectMemberListResponse(BaseModel):
    items: list[ProjectMemberResponse]
    total: int


class ProjectCreatedResponse(ProjectResponse):
    """Returned only on create/regenerate — includes the full key once."""
    api_key: str


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int


class ProjectDashboard(BaseModel):
    """Aggregated statistics for a single project's dashboard card."""
    project_id: uuid.UUID
    project_name: str
    environment: str
    status: str
    security_score: int
    security_grade: str
    open_incidents: int
    critical_incidents: int
    evidence_count: int
    overdue_compliance: int
    last_activity: Optional[datetime]
    most_common_attack: Optional[str]
    most_targeted_port: Optional[int]
    top_recommendations: list[dict]
