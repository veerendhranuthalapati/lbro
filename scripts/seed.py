#!/usr/bin/env python3
"""
Seed script — creates default admin user and sample incident for local dev.

Usage (local):  python scripts/seed.py           (from repo root)
Usage (Docker): python /scripts/seed.py          (scripts/ mounted at /scripts, PYTHONPATH=/app)
"""
from __future__ import annotations

import asyncio
import os
import secrets
import sys

# ── Python path setup: works both locally and inside the Docker API image ─────
_here = os.path.dirname(os.path.abspath(__file__))
for _candidate in [
    os.path.join(_here, "..", "backend"),   # local: repo_root/backend/
    "/app",                                  # Docker: PYTHONPATH=/app already but be explicit
]:
    _candidate = os.path.normpath(_candidate)
    if os.path.isdir(os.path.join(_candidate, "app")):
        sys.path.insert(0, _candidate)
        break

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User


async def seed():
    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(select(User).where(User.email == "admin@lbro.local"))
        if result.scalar_one_or_none():
            print("✓ Admin user already exists")
            return

        # Generate cryptographically random API keys — never use hardcoded values
        admin_api_key = f"lbro-admin-{secrets.token_urlsafe(32)}"
        analyst_api_key = f"lbro-analyst-{secrets.token_urlsafe(32)}"

        admin = User(
            email="admin@lbro.local",
            username="admin",
            full_name="LBRO Administrator",
            hashed_password=hash_password("Admin123!"),
            role="admin",
            is_active=True,
            is_verified=True,
            api_key=admin_api_key,
        )
        db.add(admin)

        analyst = User(
            email="analyst@lbro.local",
            username="analyst",
            full_name="SOC Analyst",
            hashed_password=hash_password("Analyst123!"),
            role="analyst",
            is_active=True,
            is_verified=True,
            api_key=analyst_api_key,
        )
        db.add(analyst)

        await db.commit()
        print("✓ Created users:")
        print(f"  admin@lbro.local   / Admin123!   (API key: {admin_api_key})")
        print(f"  analyst@lbro.local / Analyst123! (API key: {analyst_api_key})")
        print()
        print("⚠  Save these API keys — they will not be shown again.")


if __name__ == "__main__":
    asyncio.run(seed())
