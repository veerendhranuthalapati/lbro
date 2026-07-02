#!/usr/bin/env python3
"""Seed the first SUPER_ADMIN user.

Usage:
    SEED_ADMIN_EMAIL=admin@example.com \
    SEED_ADMIN_PASSWORD=ChangeMe123! \
    SEED_ADMIN_USERNAME=superadmin \
    python scripts/seed_super_admin.py

The script is idempotent:
  - If a user with the given email exists, their role is promoted to super_admin.
  - If a super_admin already exists, the script exits without changes.

Environment variables:
    SEED_ADMIN_EMAIL       (required) Email address for the super admin
    SEED_ADMIN_PASSWORD    (required) Plaintext password (will be bcrypt-hashed)
    SEED_ADMIN_USERNAME    (optional, default: superadmin) Username
    SEED_ADMIN_FULL_NAME   (optional, default: Super Admin) Display name
    DATABASE_URL           (optional) Overrides app config DATABASE_URL
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

# Ensure the backend package is importable when run from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    email     = os.environ.get("SEED_ADMIN_EMAIL")
    password  = os.environ.get("SEED_ADMIN_PASSWORD")
    username  = os.environ.get("SEED_ADMIN_USERNAME", "superadmin")
    full_name = os.environ.get("SEED_ADMIN_FULL_NAME", "Super Admin")

    if not email or not password:
        print("ERROR: SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD must be set.", file=sys.stderr)
        sys.exit(1)

    from app.database import engine
    from app.core.security import hash_password
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.user import User

    async with AsyncSession(engine) as session:
        # Check if a super_admin already exists
        result = await session.execute(
            select(User).where(User.role == "super_admin")
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Super admin already exists: {existing.email} — nothing to do.")
            return

        # Check if the target email already exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user:
            print(f"User {email} exists (role={user.role}), promoting to super_admin.")
            user.role = "super_admin"
        else:
            user = User(
                id=uuid.uuid4(),
                email=email,
                username=username,
                full_name=full_name,
                hashed_password=hash_password(password),
                role="super_admin",
                is_active=True,
                is_verified=True,
                mfa_enabled=False,
                failed_login_attempts=0,
            )
            session.add(user)
            print(f"Creating super_admin: {email}")

        await session.commit()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
