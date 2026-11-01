"""Alembic migration: ML provenance columns on events/incidents and project auto-contain opt-in."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015_ml_provenance"
down_revision: Union[str, None] = "014_project_invitations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("security_events", sa.Column("ml_source", sa.String(50), nullable=True))
    op.add_column("security_events", sa.Column("ml_feature_coverage", sa.Float(), nullable=True))
    op.add_column(
        "security_events",
        sa.Column("ml_needs_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "incidents",
        sa.Column(
            "ml_classification_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "allow_ml_auto_contain",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "allow_ml_auto_contain")
    op.drop_column("incidents", "ml_classification_status")
    op.drop_column("security_events", "ml_needs_review")
    op.drop_column("security_events", "ml_feature_coverage")
    op.drop_column("security_events", "ml_source")
