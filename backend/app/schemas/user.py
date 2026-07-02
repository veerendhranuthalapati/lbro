"""User schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from typing import Literal
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    role: str = "viewer"


class UserCreate(UserBase):
    password: str = Field(min_length=8)
    # Restrict role to the known set so admins cannot inject arbitrary role strings
    role: Literal[
        "super_admin", "security_admin", "incident_manager",
        "soc_analyst", "compliance_officer", "auditor", "viewer"
    ] = "viewer"


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    role: Optional[Literal[
        "super_admin", "security_admin", "incident_manager",
        "soc_analyst", "compliance_officer", "auditor", "viewer"
    ]] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
