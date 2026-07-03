#!/usr/bin/env python3
"""Seed 2 users per role (6 users total) with deterministic UUIDs.

Roles: admin / analyst / viewer

Run from backend/:
    python scripts/seed_all_roles.py

Skips any user whose email already exists (idempotent).

Credentials summary:
  admin1@lbro.local   / LbroADMIN1!2026   (admin)
  admin2@lbro.local   / LbroADMIN2!2026   (admin)
  analyst1@lbro.local / LbroANALYST1!2026 (analyst)
  analyst2@lbro.local / LbroANALYST2!2026 (analyst)
  viewer1@lbro.local  / LbroVIEWER1!2026  (viewer)
  viewer2@lbro.local  / LbroVIEWER2!2026  (viewer)
"""
from __future__ import annotations
import asyncio, os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Deterministic UUIDs derived via uuid5(NAMESPACE_DNS, "lbro.<role>.<n>")
USERS = [
    # (id,                                   role,      email,                  username,   full_name,    password)
    ("a1000000-0000-5000-8000-000000000001", "admin",   "admin1@lbro.local",    "admin1",   "Admin One",   "LbroADMIN1!2026"),
    ("a1000000-0000-5000-8000-000000000002", "admin",   "admin2@lbro.local",    "admin2",   "Admin Two",   "LbroADMIN2!2026"),
    ("a2000000-0000-5000-8000-000000000001", "analyst", "analyst1@lbro.local",  "analyst1", "Analyst One", "LbroANALYST1!2026"),
    ("a2000000-0000-5000-8000-000000000002", "analyst", "analyst2@lbro.local",  "analyst2", "Analyst Two", "LbroANALYST2!2026"),
    ("a3000000-0000-5000-8000-000000000001", "viewer",  "viewer1@lbro.local",   "viewer1",  "Viewer One",  "LbroVIEWER1!2026"),
    ("a3000000-0000-5000-8000-000000000002", "viewer",  "viewer2@lbro.local",   "viewer2",  "Viewer Two",  "LbroVIEWER2!2026"),
]


async def main() -> None:
    from app.database import engine
    from app.core.security import hash_password
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.user import User

    async with AsyncSession(engine) as session:
        created = skipped = 0
        for (uid, role, email, username, full_name, password) in USERS:
            result = await session.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                print(f"  SKIP  {email} (already exists)")
                skipped += 1
                continue
            user = User(
                id=uuid.UUID(uid),
                email=email,
                username=username,
                full_name=full_name,
                hashed_password=hash_password(password),
                role=role,
                is_active=True,
                is_verified=True,
                mfa_enabled=False,
                failed_login_attempts=0,
            )
            session.add(user)
            print(f"  CREATE {role:<10} {email}")
            created += 1
        await session.commit()
    print(f"\nDone. Created: {created}, Skipped: {skipped}")
    print("\nCredentials:")
    for (_, role, email, _, _, pw) in USERS:
        print(f"  {email:<30}  {pw}  [{role}]")


if __name__ == "__main__":
    asyncio.run(main())
