"""007 — Projects

Create the projects table and add project_id foreign keys to incidents
and audit_logs.  A single "Default Project" is seeded and all existing
rows are assigned to it so that no data is lost on existing deployments.

Migration is intentionally additive and non-breaking:
  - project_id is NULLABLE — existing API integrations continue to work.
  - NULL project_id means "global / unscoped" and is treated as the
    Default Project by the application layer.

Revision ID: 007
Revises: 006
Create Date: 2026-07-08
"""

import secrets
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

# Fixed UUID for the seed "Default Project" so the migration is idempotent.
# Must be a uuid.UUID object (not a string) so asyncpg receives the correct type.
DEFAULT_PROJECT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    # ── 1. Create projects table ──────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("environment", sa.String(50), nullable=False, server_default="production"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("api_key", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
        sa.UniqueConstraint("api_key", name="uq_projects_api_key"),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_api_key", "projects", ["api_key"])

    # ── 2. Seed "Default Project" ─────────────────────────────────────────────
    default_api_key = "proj_" + secrets.token_urlsafe(32)
    op.execute(
        sa.text(
            """
            INSERT INTO projects (id, name, slug, description, environment, status, api_key)
            VALUES (
                :id,
                'Default Project',
                'default-project',
                'Auto-created migration project. All pre-existing incidents are assigned here.',
                'production',
                'active',
                :api_key
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(id=DEFAULT_PROJECT_ID, api_key=default_api_key)
    )

    # ── 3. Add project_id column to incidents ─────────────────────────────────
    op.add_column(
        "incidents",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_incidents_project_id", "incidents", ["project_id"])

    # ── 4. Backfill existing incidents → Default Project ─────────────────────
    op.execute(
        sa.text(
            "UPDATE incidents SET project_id = :pid WHERE project_id IS NULL"
        ).bindparams(pid=DEFAULT_PROJECT_ID)
    )

    # ── 5. Add project_id column to audit_logs ────────────────────────────────
    op.add_column(
        "audit_logs",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_audit_logs_project_id", "audit_logs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_project_id", "audit_logs")
    op.drop_column("audit_logs", "project_id")

    op.drop_index("ix_incidents_project_id", "incidents")
    op.drop_column("incidents", "project_id")

    op.drop_index("ix_projects_api_key", "projects")
    op.drop_index("ix_projects_status", "projects")
    op.drop_index("ix_projects_slug", "projects")
    op.drop_table("projects")
