"""Notification schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator


class NotificationCreate(BaseModel):
    incident_id: uuid.UUID
    regulation: str
    jurisdiction: str
    authority: str
    authority_email: Optional[EmailStr] = None
    subject: str
    body: str
    additional_recipients: Optional[List[EmailStr]] = None


class NotificationUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None


class NotificationRecipientResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: Optional[str] = None
    recipient_type: str

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    regulation: str
    jurisdiction: str
    authority: str
    authority_email: Optional[str] = None
    status: str
    subject: str
    body: str
    deadline: datetime
    sent_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    retry_count: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    recipients: List[NotificationRecipientResponse] = []

    model_config = {"from_attributes": True}

    @field_validator("recipients", mode="before")
    @classmethod
    def coerce_recipients_to_list(cls, v):
        """Guard against SQLAlchemy returning a scalar instead of a collection."""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        # Single ORM object — wrap it
        return [v]


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
