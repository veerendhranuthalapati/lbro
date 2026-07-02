"""RBAC — expand role set to 7 production roles.

Revision ID: 002
Revises: 001
Create Date: 2026-07-02

Changes:
  - The `role` column in `users` is still a VARCHAR(50) — no structural change needed.
  - Adds a CHECK constraint that limits valid values to the 7 new role names.
  - Migrates any existing rows:
      admin     → super_admin
      analyst   → soc_analyst
      responder → incident_manager
      viewer    → viewer   (unchanged)
  - Adds index on `users.role` for permission lookups.
  - Seeds a SUPER_ADMIN from environment variables SEED_ADMIN_EMAIL /
    SEED_ADMIN_USERNAME / SEED_ADMIN_PASSWORD if they are set and no
    super_admin exists yet.  Safe to re-run (idempotent).
"""
from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_ROLES = (
    "super_admin",
    "security_admin",
    "incident_manager",
    "soc_analyst",
    "compliance_officer",
    "auditor",
    "viewer",
)

# Old role → new role mapping
ROLE_MIGRATION: dict[str, str] = {
    "admin":     "super_admin",
    "analyst":   "soc_analyst",
    "responder": "incident_manager",
    "viewer":    "viewer",
}


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Migrate existing roles to new names
    for old_role, new_role in ROLE_MIGRATION.items():
        if old_role != new_role:
            conn.execute(
                sa.text("UPDATE users SET role = :new WHERE role = :old"),
                {"new": new_role, "old": old_role},
            )

    # 2. Add CHECK constraint to enforce valid role values
    #    (Postgres supports ALTER TABLE … ADD CONSTRAINT; skip if already exists)
    try:
        op.create_check_constraint(
            "ck_users_role_valid",
            "users",
            f"role IN ({', '.join(repr(r) for r in VALID_ROLES)})",
        )
    except Exception:
        pass  # constraint may already exist (re-run safety)

    # 3. Add index on role column for authz lookup performance
    try:
        op.create_index("ix_users_role", "users", ["role"])
    except Exception:
        pass  # index may already exist

    # 4. Seed SUPER_ADMIN if env vars are provided and no super_admin exists yet
    _seed_super_admin(conn)


def _seed_super_admin(conn: sa.engine.Connection) -> None:
    email    = os.getenv("SEED_ADMIN_EMAIL")
    username = os.getenv("SEED_ADMIN_USERNAME", "superadmin")
    password = os.getenv("SEED_ADMIN_PASSWORD")
    full_name = os.getenv("SEED_ADMIN_FULL_NAME", "Super Admin")

    if not email or not password:
        return  # env vars not set — skip seeding

    # Skip if a super_admin already exists
    row = conn.execute(
        sa.text("SELECT id FROM users WHERE role = 'super_admin' LIMIT 1")
    ).fetchone()
    if row:
        return

    # Skip if this email already exists (prevent duplicates on re-run)
    row = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :email"), {"email": email}
    ).fetchone()
    if row:
        # Promote existing user to super_admin
        conn.execute(
            sa.text("UPDATE users SET role = 'super_admin' WHERE email = :email"),
            {"email": email},
        )
        return

    # Hash password via bcrypt (same as auth_service)
    try:
        import bcrypt
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    except ImportError:
        # passlib fallback
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = ctx.hash(password)

    import uuid as _uuid
    conn.execute(
        sa.text("""
            INSERT INTO users
                (id, email, username, full_name, hashed_password, role,
                 is_active, is_verified, mfa_enabled, failed_login_attempts,
                 created_at, updated_at)
            VALUES
                (:id, :email, :username, :full_name, :hashed_password, 'super_admin',
                 true, true, false, 0,
                 now(), now())
        """),
        {
            "id":              str(_uuid.uuid4()),
            "email":           email,
            "username":        username,
            "full_name":       full_name,
            "hashed_password": hashed,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove CHECK constraint
    try:
        op.drop_constraint("ck_users_role_valid", "users", type_="check")
    except Exception:
        pass

    # Remove index
    try:
        op.drop_index("ix_users_role", table_name="users")
    except Exception:
        pass

    # Revert roles to old names (best-effort; new roles that have no mapping become 'viewer')
    revert_map = {v: k for k, v in ROLE_MIGRATION.items() if k != v}
    revert_map.update({
        "security_admin":     "admin",
        "compliance_officer": "analyst",
        "auditor":            "viewer",
    })
    for new_role, old_role in revert_map.items():
        conn.execute(
            sa.text("UPDATE users SET role = :old WHERE role = :new"),
            {"old": old_role, "new": new_role},
        )
