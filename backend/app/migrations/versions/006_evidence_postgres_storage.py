"""006 — Evidence PostgreSQL storage

Store evidence binary data in PostgreSQL instead of S3.
Adds file_data BYTEA (deferred) column; makes s3_key/s3_bucket nullable for
backward compatibility with any existing S3-backed rows.

Revision ID: 006
Revises: 005
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make s3_key / s3_bucket nullable (new uploads won't use S3)
    op.alter_column("evidence", "s3_key",    existing_type=sa.Text(),         nullable=True)
    op.alter_column("evidence", "s3_bucket", existing_type=sa.String(255),    nullable=True)

    # Add file_data BYTEA column (nullable; populated on new uploads)
    op.add_column(
        "evidence",
        sa.Column("file_data", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence", "file_data")
    op.alter_column("evidence", "s3_key",    existing_type=sa.Text(),         nullable=False)
    op.alter_column("evidence", "s3_bucket", existing_type=sa.String(255),    nullable=False)
