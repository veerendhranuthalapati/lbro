"""Add ML classification retry counters for pending worker classification."""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_ml_classification_retry"
down_revision: Union[str, None] = "015_ml_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "incidents",
        sa.Column("ml_classification_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "incidents",
        sa.Column("ml_classification_next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incidents", "ml_classification_next_retry_at")
    op.drop_column("incidents", "ml_classification_attempts")
