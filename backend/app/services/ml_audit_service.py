"""Structured audit entries for ML classification and containment decisions."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_ml_system_action(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    project_id: uuid.UUID | None,
    details: dict,
) -> None:
    """Record ML worker/API decisions with a fixed system identity (no user session)."""
    entry = AuditLog(
        user_id=None,
        user_email="system@lbro.ml",
        project_id=project_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )
    db.add(entry)
