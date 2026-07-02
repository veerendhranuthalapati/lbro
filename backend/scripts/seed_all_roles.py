#!/usr/bin/env python3
"""Seed 2 users per role (14 users total) with deterministic UUIDs.

Run from backend/:
    python scripts/seed_all_roles.py

Uses DATABASE_URL from environment (falls back to app config).
Skips any user whose email already exists.
"""
from __future__ import annotations
import asyncio, os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

USERS = [
    # (id,                                   role,                 email,                username,    full_name,                     password)
    ("83238b85-45b1-53ea-a540-455dc20cf4c5", "super_admin",        "sa1@lbro.local",     "sa1",       "Super Admin 1",               "LbroSA1!2026"),
    ("01327bc9-6360-5f72-8561-31e5390147bc", "super_admin",        "sa2@lbro.local",     "sa2",       "Super Admin 2",               "LbroSA2!2026"),
    ("f7510fe8-3599-53b5-8923-230211ee4c7e", "security_admin",     "secadm1@lbro.local", "secadm1",   "Security Admin 1",            "LbroSECADM1!2026"),
    ("f4c69328-9a87-59c1-88e2-fa2a619e2dc9", "security_admin",     "secadm2@lbro.local", "secadm2",   "Security Admin 2",            "LbroSECADM2!2026"),
    ("3433f6c5-005b-5100-b256-de210c1d386a", "incident_manager",   "im1@lbro.local",     "im1",       "Incident Manager 1",          "LbroIM1!2026"),
    ("23ea3a73-105a-504f-a949-ba138f0404ff", "incident_manager",   "im2@lbro.local",     "im2",       "Incident Manager 2",          "LbroIM2!2026"),
    ("3737d380-34eb-58a1-9ab2-e4dea8b98bd8", "soc_analyst",        "soc1@lbro.local",    "soc1",      "SOC Analyst 1",               "LbroSOC1!2026"),
    ("1dd19c56-e56d-5a2a-8779-deaa9394e79a", "soc_analyst",        "soc2@lbro.local",    "soc2",      "SOC Analyst 2",               "LbroSOC2!2026"),
    ("d704b750-97a7-5768-8d30-0b80310709e4", "compliance_officer", "co1@lbro.local",     "co1",       "Compliance Officer 1",        "LbroCO1!2026"),
    ("b85aaeb8-cd6b-56da-9a8e-c77c557a97d6", "compliance_officer", "co2@lbro.local",     "co2",       "Compliance Officer 2",        "LbroCO2!2026"),
    ("f703c973-fa03-592c-a4aa-f0a4f6466c52", "auditor",            "aud1@lbro.local",    "aud1",      "Auditor 1",                   "LbroAUD1!2026"),
    ("0405c4bb-e963-5e63-a879-7d7a120294cd", "auditor",            "aud2@lbro.local",    "aud2",      "Auditor 2",                   "LbroAUD2!2026"),
    ("b49a0822-6006-5e66-8590-411e6ba02dab", "viewer",             "view1@lbro.local",   "view1",     "Viewer 1",                    "LbroVIEW1!2026"),
    ("3f83fe58-2b2c-530c-ae65-366d61982a06", "viewer",             "view2@lbro.local",   "view2",     "Viewer 2",                    "LbroVIEW2!2026"),
]

async def main() -> None:
    import datetime
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
            print(f"  CREATE {role:<20} {email}")
            created += 1
        await session.commit()
    print(f"\nDone. Created: {created}, Skipped: {skipped}")

if __name__ == "__main__":
    asyncio.run(main())
