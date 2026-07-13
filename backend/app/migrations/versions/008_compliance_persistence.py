"""Compliance persistence — add compliance_obligations and compliance_assessments tables.

Revision ID: 008_compliance_persistence
Revises: 007
Create Date: 2026-07-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "008_compliance_persistence"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compliance_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("framework", sa.String(50), nullable=False),
        sa.Column("control_id", sa.String(100), nullable=False),
        sa.Column("control_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="not_started"),
        sa.Column("evidence_reference", sa.Text, nullable=True),
        sa.Column("score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("recommendations", sa.Text, nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_compliance_obligations_project_id",
        "compliance_obligations",
        ["project_id"],
    )

    op.create_table(
        "compliance_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("framework", sa.String(50), nullable=False),
        sa.Column("overall_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_controls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("compliant_controls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assessment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_compliance_assessments_project_id",
        "compliance_assessments",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_compliance_assessments_project_id", table_name="compliance_assessments")
    op.drop_table("compliance_assessments")
    op.drop_index("ix_compliance_obligations_project_id", table_name="compliance_obligations")
    op.drop_table("compliance_obligations")
