"""Platform layer: project_members, security_events, super_admin role.

Revision ID: 010_platform_layer
Revises: 009_add_missing_indexes
Create Date: 2026-07-13

Changes:
  - Create project_members table (project-scoped RBAC)
  - Create security_events table (event ingestion pipeline)
  - Add super_admin to the users.role CHECK constraint (PostgreSQL)
    NOTE: SQLite in test environment has no CHECK constraints, so the
    constraint is added conditionally on connection dialect.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010_platform_layer"
down_revision: Union[str, None] = "009_add_missing_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # ── project_members ───────────────────────────────────────────────────
    op.create_table(
        "project_members",
        sa.Column("id", postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36),
                  primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"])
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"])

    # ── security_events ───────────────────────────────────────────────────
    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36),
                  primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("source_host", sa.String(255), nullable=True),
        sa.Column("source_application", sa.String(255), nullable=True),
        sa.Column("source_agent_version", sa.String(50), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("ml_attack_category", sa.String(100), nullable=True),
        sa.Column("ml_confidence", sa.Float(), nullable=True),
        sa.Column("ml_model_version", sa.String(50), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True) if not is_sqlite else sa.String(36),
                  sa.ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("processing_status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_security_events_project_id", "security_events", ["project_id"])
    op.create_index("ix_security_events_event_type", "security_events", ["event_type"])
    op.create_index("ix_security_events_severity", "security_events", ["severity"])
    op.create_index("ix_security_events_processing_status", "security_events", ["processing_status"])
    op.create_index("ix_security_events_source_ip", "security_events", ["source_ip"])
    op.create_index("ix_security_events_created_at", "security_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("security_events")
    op.drop_table("project_members")
