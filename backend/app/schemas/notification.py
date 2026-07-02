"""Notification schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


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


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
