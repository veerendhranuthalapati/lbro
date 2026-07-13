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

from app.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User


async def seed():
    async with AsyncSessionLocal() as db:
        new_keys: list[str] = []

        # ── Admin ──────────────────────────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == "admin@lbro.local"))
        if result.scalar_one_or_none():
            print("✓ Admin user already exists")
        else:
            admin_api_key = "lbro-admin-" + secrets.token_urlsafe(32)
            db.add(User(
                email="admin@lbro.local",
                username="admin",
                full_name="LBRO Administrator",
                hashed_password=hash_password("Admin123!"),
                role="admin",
                is_active=True,
                is_verified=True,
                api_key=admin_api_key,
            ))
            new_keys.append("  admin@lbro.local   / Admin123!   (API key: " + admin_api_key + ")")

        # ── Analyst ────────────────────────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == "analyst@lbro.local"))
        if result.scalar_one_or_none():
            print("✓ Analyst user already exists")
        else:
            analyst_api_key = "lbro-analyst-" + secrets.token_urlsafe(32)
            db.add(User(
                email="analyst@lbro.local",
                username="analyst",
                full_name="SOC Analyst",
                hashed_password=hash_password("Analyst123!"),
                role="analyst",
                is_active=True,
                is_verified=True,
                api_key=analyst_api_key,
            ))
            new_keys.append("  analyst@lbro.local / Analyst123! (API key: " + analyst_api_key + ")")

        # ── Viewer ─────────────────────────────────────────────────────────────
        result = await db.execute(select(User).where(User.email == "viewer@lbro.local"))
        if result.scalar_one_or_none():
            print("✓ Viewer user already exists")
        else:
            viewer_api_key = "lbro-viewer-" + secrets.token_urlsafe(32)
            db.add(User(
                email="viewer@lbro.local",
                username="viewer",
                full_name="Demo Viewer",
                hashed_password=hash_password("ViewerPass1"),
                role="viewer",
                is_active=True,
                is_verified=True,
                api_key=viewer_api_key,
            ))
            new_keys.append("  viewer@lbro.local  / ViewerPass1 (API key: " + viewer_api_key + ")")

        await db.commit()

        if new_keys:
            print("✓ Created users:")
            for line in new_keys:
                print(line)
            print()
            print("⚠  Save these API keys — they will not be shown again.")


if __name__ == "__main__":
    asyncio.run(seed())
