"""Simplify from 7 roles to 3 roles (admin / analyst / viewer).

Revision ID: 003
Revises: 002
Create Date: 2026-07-02

Mapping:
  super_admin        -> admin
  security_admin     -> admin
  incident_manager   -> analyst
  soc_analyst        -> analyst
  compliance_officer -> analyst
  auditor            -> viewer
  viewer             -> viewer  (unchanged)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_ROLES = ("admin", "analyst", "viewer")

# Old 7-role values -> new 3-role values
ROLE_MIGRATION: dict[str, str] = {
    "super_admin":        "admin",
    "security_admin":     "admin",
    "incident_manager":   "analyst",
    "soc_analyst":        "analyst",
    "compliance_officer": "analyst",
    "auditor":            "viewer",
    "viewer":             "viewer",
}


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Drop existing CHECK constraint from migration 002 (ignore if absent)
    try:
        op.drop_constraint("ck_users_role_valid", "users", type_="check")
    except Exception:
        pass

    # 2. Migrate every old role value to its new 3-role equivalent
    for old_role, new_role in ROLE_MIGRATION.items():
        if old_role != new_role:
            conn.execute(
                sa.text("UPDATE users SET role = :new WHERE role = :old"),
                {"new": new_role, "old": old_role},
            )

    # 3. Add new CHECK constraint for the 3 valid roles
    try:
        op.create_check_constraint(
            "ck_users_role_valid",
            "users",
            f"role IN ({', '.join(repr(r) for r in VALID_ROLES)})",
        )
    except Exception:
        pass


def downgrade() -> None:
    conn = op.get_bind()

    # Remove 3-role constraint
    try:
        op.drop_constraint("ck_users_role_valid", "users", type_="check")
    except Exception:
        pass

    # Best-effort revert: admin -> super_admin, analyst -> soc_analyst
    revert = {"admin": "super_admin", "analyst": "soc_analyst"}
    for new_role, old_role in revert.items():
        conn.execute(
            sa.text("UPDATE users SET role = :old WHERE role = :new"),
            {"old": old_role, "new": new_role},
        )

    # Restore previous 7-role constraint
    try:
        op.create_check_constraint(
            "ck_users_role_valid",
            "users",
            "role IN ('super_admin','security_admin','incident_manager',"
            "'soc_analyst','compliance_officer','auditor','viewer')",
        )
    except Exception:
        pass
