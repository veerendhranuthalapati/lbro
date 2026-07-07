"""Revoked JWT token model.

Stores the `jti` (JWT ID) of tokens that have been explicitly revoked via logout.
Tokens are removed automatically once their `expires_at` passes (via periodic cleanup).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    # jti is a UUID string — use as primary key for O(1) lookup
    jti: Mapped[str] = mapped_column(String(36), primary_key=True)

    # When the original JWT expires — used for periodic cleanup
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
