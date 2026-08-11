"""Hash API keys at rest — store prefix + HMAC hash only.

Revision ID: 012_hash_api_keys
"""
from __future__ import annotations

import hashlib
import hmac
import os

from alembic import op
import sqlalchemy as sa

revision = "012_hash_api_keys"
down_revision = "011_investigation_notes"
branch_labels = None
depends_on = None


def _hash_key(key: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def upgrade() -> None:
    secret = os.environ.get("SECRET_KEY", "dev-only-lbro-secret-key-not-for-production-use-abcdef1234567890abcdef")
    prefix_len = 16

    # ── projects ──────────────────────────────────────────────────────────────
    op.add_column("projects", sa.Column("api_key_hash", sa.String(64), nullable=True))
    op.add_column("projects", sa.Column("api_key_prefix", sa.String(16), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, api_key FROM projects WHERE api_key IS NOT NULL")).fetchall()
    for row in rows:
        key = row.api_key
        conn.execute(
            sa.text(
                "UPDATE projects SET api_key_hash = :h, api_key_prefix = :p WHERE id = :id"
            ),
            {"h": _hash_key(key, secret), "p": key[:prefix_len], "id": row.id},
        )

    op.alter_column("projects", "api_key_hash", nullable=False)
    op.alter_column("projects", "api_key_prefix", nullable=False)
    op.create_index("ix_projects_api_key_prefix", "projects", ["api_key_prefix"])

    op.drop_index("ix_projects_api_key", table_name="projects")
    op.drop_constraint("uq_projects_api_key", "projects", type_="unique")
    op.drop_column("projects", "api_key")

    op.create_unique_constraint("uq_projects_api_key_prefix_hash", "projects", ["api_key_prefix", "api_key_hash"])

    # ── users (legacy user API keys) ──────────────────────────────────────────
    op.add_column("users", sa.Column("api_key_hash", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("api_key_prefix", sa.String(16), nullable=True))

    user_rows = conn.execute(sa.text("SELECT id, api_key FROM users WHERE api_key IS NOT NULL")).fetchall()
    for row in user_rows:
        key = row.api_key
        conn.execute(
            sa.text(
                "UPDATE users SET api_key_hash = :h, api_key_prefix = :p WHERE id = :id"
            ),
            {"h": _hash_key(key, secret), "p": key[:prefix_len], "id": row.id},
        )

    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_api_key"))
    # users.api_key uses implicit UNIQUE (users_api_key_key) — no named ix_users_api_key
    op.execute(sa.text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_api_key_key"))
    op.drop_column("users", "api_key")
    op.create_index("ix_users_api_key_prefix", "users", ["api_key_prefix"], unique=False)


def downgrade() -> None:
    raise NotImplementedError("012_hash_api_keys downgrade not supported — rotate keys after rollback")
