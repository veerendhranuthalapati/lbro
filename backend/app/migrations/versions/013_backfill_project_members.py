"""Backfill project_members for existing project owners.

Revision ID: 013_backfill_project_members
Revises: 012_hash_api_keys
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_backfill_project_members"
down_revision: Union[str, None] = "012_hash_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        rows = bind.execute(
            sa.text(
                "SELECT id, owner_id, created_at FROM projects WHERE owner_id IS NOT NULL"
            )
        ).fetchall()
        for project_id, owner_id, created_at in rows:
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM project_members "
                    "WHERE project_id = :pid AND user_id = :uid LIMIT 1"
                ),
                {"pid": str(project_id), "uid": str(owner_id)},
            ).fetchone()
            if exists:
                continue
            bind.execute(
                sa.text(
                    "INSERT INTO project_members (id, project_id, user_id, role, created_at) "
                    "VALUES (:id, :pid, :uid, 'admin', :created_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "pid": str(project_id),
                    "uid": str(owner_id),
                    "created_at": created_at,
                },
            )
    else:
        op.execute(
            sa.text(
                """
                INSERT INTO project_members (id, project_id, user_id, role, created_at)
                SELECT gen_random_uuid(), p.id, p.owner_id, 'admin', p.created_at
                FROM projects p
                WHERE p.owner_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM project_members pm
                    WHERE pm.project_id = p.id AND pm.user_id = p.owner_id
                  )
                """
            )
        )


def downgrade() -> None:
    pass
