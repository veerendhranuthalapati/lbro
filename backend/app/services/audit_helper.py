"""Audit log helper for compliance / asset mutations."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User


async def write_audit(
    db: AsyncSession,
    *,
    user: User | None,
    project_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            user_email=user.email if user else "system@lbro",
            project_id=project_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
    )
