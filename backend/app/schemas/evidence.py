"""Evidence schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ChainOfCustodyResponse(BaseModel):
    id: uuid.UUID
    action: str
    performed_by_name: str
    ip_address: Optional[str] = None
    notes: Optional[str] = None
    hash_at_time: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    sha256_hash: str
    description: Optional[str] = None
    tags: Optional[str] = None
    is_immutable: bool
    uploaded_by: Optional[uuid.UUID] = None
    created_at: datetime
    custody_chain: List[ChainOfCustodyResponse] = []
    download_url: Optional[str] = None

    model_config = {"from_attributes": True}


class EvidenceListResponse(BaseModel):
    items: List[EvidenceResponse]
    total: int


class EvidenceUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    sha256_hash: str
    file_size: int
    created_at: datetime
