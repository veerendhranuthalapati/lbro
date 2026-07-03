"""Sanitize any remaining legacy roles to the 3-role model.

Revision ID: 004
Revises: 003
Create Date: 2026-07-03

This is a safety migration.  It converts any role value that is NOT one of
(admin, analyst, viewer) to its nearest 3-role equivalent.  This handles
databases that:
  - Applied migration 002 (7 roles) but skipped 003
  - Were seeded by seed_super_admin.py before it was fixed
  - Have any other legacy role string

Mapping:
  super_admin        -> admin
  security_admin     -> admin
  incident_manager   -> analyst
  soc_analyst        -> analyst
  compliance_officer -> analyst
  auditor            -> analyst   (analyst has VIEW_AUDIT; auditor's core permission)
  <anything else>    -> viewer    (safe fallback — read-only)

Idempotent: safe to run on an already-clean database.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_ROLES = ("admin", "analyst", "viewer")

LEGACY_MAP: dict[str, str] = {
    "super_admin":        "admin",
    "security_admin":     "admin",
    "incident_manager":   "analyst",
    "soc_analyst":        "analyst",
    "compliance_officer": "analyst",
    "auditor":            "analyst",
}


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Convert known legacy roles
    for old_role, new_role in LEGACY_MAP.items():
        conn.execute(
            sa.text("UPDATE users SET role = :new WHERE role = :old"),
            {"new": new_role, "old": old_role},
        )

    # 2. Convert any remaining unknown roles to viewer (safe fallback)
    placeholders = ", ".join(f"'{r}'" for r in VALID_ROLES)
    conn.execute(
        sa.text(f"UPDATE users SET role = 'viewer' WHERE role NOT IN ({placeholders})")
    )

    # 3. Ensure the CHECK constraint reflects only 3 valid roles
    try:
        op.drop_constraint("ck_users_role_valid", "users", type_="check")
    except Exception:
        pass

    try:
        op.create_check_constraint(
            "ck_users_role_valid",
            "users",
            "role IN ('admin', 'analyst', 'viewer')",
        )
    except Exception:
        pass


def downgrade() -> None:
    # No safe downgrade — removing legacy roles is a one-way operation.
    # Attempting to restore legacy role names would require data that is gone.
    pass
