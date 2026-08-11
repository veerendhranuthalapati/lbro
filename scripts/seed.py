#!/usr/bin/env python3
"""
Seed script — creates default admin, analyst, and viewer users for local dev.

Usage (local):  python scripts/seed.py           (from repo root)
Usage (Docker): python /scripts/seed.py          (scripts/ mounted at /scripts, PYTHONPATH=/app)

Idempotent — each user is checked individually before creation.
"""
from __future__ import annotations

import asyncio
import os
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

from app.core.api_keys import generate_user_api_key, mask_api_key_prefix
from app.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User


def _seed_user(email: str, username: str, full_name: str, password: str, role: str) -> tuple[User, str, str]:
    full_key, prefix, key_hash = generate_user_api_key()
    return User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
        is_verified=True,
        api_key_hash=key_hash,
        api_key_prefix=prefix,
    ), full_key, prefix


async def seed():
    async with AsyncSessionLocal() as db:
        created: list[tuple[str, str, str]] = []

        # ── Admin ──────────────────────────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == "admin@lbro.local"))
        if result.scalar_one_or_none():
            print("✓ Admin user already exists")
        else:
            user, full_key, prefix = _seed_user(
                "admin@lbro.local", "admin", "LBRO Administrator", "Admin123!", "admin"
            )
            db.add(user)
            created.append(("admin@lbro.local", "Admin123!", prefix))

        # ── Analyst ────────────────────────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == "analyst@lbro.local"))
        if result.scalar_one_or_none():
            print("✓ Analyst user already exists")
        else:
            user, full_key, prefix = _seed_user(
                "analyst@lbro.local", "analyst", "SOC Analyst", "Analyst123!", "analyst"
            )
            db.add(user)
            created.append(("analyst@lbro.local", "Analyst123!", prefix))

        # ── Viewer ─────────────────────────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == "viewer@lbro.local"))
        if result.scalar_one_or_none():
            print("✓ Viewer user already exists")
        else:
            user, full_key, prefix = _seed_user(
                "viewer@lbro.local", "viewer", "Demo Viewer", "ViewerPass1", "viewer"
            )
            db.add(user)
            created.append(("viewer@lbro.local", "ViewerPass1", prefix))

        await db.commit()

        if created:
            print("✓ Created users:")
            for email, password, prefix in created:
                print(f"  {email:<20} / {password:<12} (API key prefix: {mask_api_key_prefix(prefix)})")
            print()
            print("⚠  API keys were generated but not logged in full — rotate via POST /auth/api-key/rotate to obtain a key.")


if __name__ == "__main__":
    asyncio.run(seed())
