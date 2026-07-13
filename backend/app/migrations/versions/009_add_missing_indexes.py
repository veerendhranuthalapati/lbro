"""Add missing indexes on FK columns used in filters and joins.

Revision ID: 009_add_missing_indexes
Revises: 008_compliance_persistence
Create Date: 2026-07-13

Indexes added:
  ix_incidents_assigned_to          — used in list/filter queries in IncidentService
  ix_incidents_created_by           — used in ownership queries
  ix_notification_recipients_notification_id — high-frequency join on notification load
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "009_add_missing_indexes"
down_revision: Union[str, None] = "008_compliance_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_incidents_assigned_to",
        "incidents",
        ["assigned_to"],
    )
    op.create_index(
        "ix_incidents_created_by",
        "incidents",
        ["created_by"],
    )
    op.create_index(
        "ix_notification_recipients_notification_id",
        "notification_recipients",
        ["notification_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_assigned_to", table_name="incidents")
    op.drop_index("ix_incidents_created_by", table_name="incidents")
    op.drop_index(
        "ix_notification_recipients_notification_id",
        table_name="notification_recipients",
    )
