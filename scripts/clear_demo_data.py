#!/usr/bin/env python3
"""
LBRO Demo Data Cleaner
======================
Removes all rows created by the demo seeder without touching any
production/real data.

Demo data is identified by the email domain @lbro.demo.
All dependent rows are deleted in correct foreign-key order.

Usage:
  python scripts/clear_demo_data.py           # prompt before deleting
  python scripts/clear_demo_data.py --yes     # skip confirmation

Environment:
  DATABASE_URL  postgresql+asyncpg://user:pass@host/db
  (Falls back to backend/.env if not set in environment)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# ── Path setup ────────────────────────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
for _candidate in [os.path.join(_here, "..", "backend"), "/app"]:
    _candidate = os.path.normpath(_candidate)
    if os.path.isdir(os.path.join(_candidate, "app")):
        sys.path.insert(0, _candidate)
        break

_env_path = os.path.join(_here, "..", "backend", ".env")
if os.path.exists(_env_path):
    for _line in open(_env_path):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.compliance import ComplianceRecord
from app.models.evidence import Evidence, ChainOfCustody
from app.models.incident import Incident, IncidentAction
from app.models.notification import Notification, NotificationRecipient
from app.models.user import User


DEMO_EMAIL_DOMAIN = "lbro.demo"


async def _count_demo_data(db: AsyncSession) -> dict[str, int]:
    """Return a preview count of what would be deleted."""
    user_ids_result = await db.execute(
        select(User.id).where(User.email.like(f"%@{DEMO_EMAIL_DOMAIN}"))
    )
    user_ids = [r[0] for r in user_ids_result.all()]

    if not user_ids:
        return {}

    inc_ids_result = await db.execute(
        select(Incident.id).where(Incident.created_by.in_(user_ids))
    )
    inc_ids = [r[0] for r in inc_ids_result.all()]

    counts: dict[str, int] = {
        "Users": len(user_ids),
        "Incidents": len(inc_ids),
        "Audit logs": int(
            (await db.execute(
                text("SELECT COUNT(*) FROM audit_logs WHERE user_id = ANY(:ids)")
                .bindparams(ids=user_ids)
            )).scalar() or 0
        ),
    }

    if inc_ids:
        for table, col in [
            ("evidence",           "incident_id"),
            ("notifications",      "incident_id"),
            ("compliance_records", "incident_id"),
            ("incident_actions",   "incident_id"),
        ]:
            row = await db.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {col} = ANY(:ids)")
                .bindparams(ids=inc_ids)
            )
            label = table.replace("_", " ").capitalize()
            counts[label] = int(row.scalar() or 0)

    return counts


async def clear(skip_confirmation: bool = False) -> None:
    # Import wipe helper from seed script (avoids code duplication)
    sys.path.insert(0, _here)
    from seed_demo_data import _wipe_demo_data  # noqa: PLC0415

    async with AsyncSessionLocal() as db:
        print("━" * 64)
        print("  LBRO Demo Data Cleaner")
        print("━" * 64)
        print()

        counts = await _count_demo_data(db)
        if not counts:
            print("  No demo data found. Nothing to delete.")
            return

        print("  The following demo rows will be permanently deleted:")
        print()
        for label, n in counts.items():
            print(f"    {label:<22} {n:>6}")
        print()

        if not skip_confirmation:
            answer = input("  Type 'yes' to confirm deletion: ").strip().lower()
            if answer != "yes":
                print("  Aborted — no data deleted.")
                return
            print()

        removed = await _wipe_demo_data(db)

        print()
        print(f"  Done. Removed all data for {removed} demo users.")
        print("  Run 'python scripts/seed_demo_data.py' to re-seed.")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove LBRO demo data from PostgreSQL")
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip the confirmation prompt",
    )
    args = parser.parse_args()
    asyncio.run(clear(skip_confirmation=args.yes))
