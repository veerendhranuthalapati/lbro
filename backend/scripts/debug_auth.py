#!/usr/bin/env python3
"""Debug login issues: check lockout status, test password verification, reset if needed."""
from __future__ import annotations
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_USERS = [
    ("admin@yourcompany.com", "ChangeMe123!"),
    ("sa1@lbro.local",        "LbroSA1!2026"),
    ("soc1@lbro.local",       "LbroSOC1!2026"),
]

async def main():
    from app.database import engine
    from app.core.security import verify_password
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.user import User
    from datetime import datetime, timezone

    async with AsyncSession(engine) as session:
        # Show all users + lockout status
        result = await session.execute(select(User).order_by(User.created_at))
        users = result.scalars().all()
        print(f"\n{'Email':<30} {'Role':<20} {'Active':<7} {'Attempts':<9} {'Locked?'}")
        print("-" * 85)
        now = datetime.now(timezone.utc)
        for u in users:
            locked = u.locked_until and u.locked_until > now
            locked_str = f"YES until {u.locked_until.strftime('%H:%M:%S')}" if locked else "no"
            print(f"{u.email:<30} {u.role:<20} {str(u.is_active):<7} {u.failed_login_attempts or 0:<9} {locked_str}")

        # Test password verification for key accounts
        print("\n-- Password verification test --")
        for email, password in TEST_USERS:
            result = await session.execute(select(User).where(User.email == email))
            u = result.scalar_one_or_none()
            if not u:
                print(f"  {email}: NOT FOUND")
                continue
            ok = verify_password(password, u.hashed_password)
            print(f"  {email}: {'OK' if ok else 'FAIL'} (attempts={u.failed_login_attempts or 0})")

        # Reset all lockouts + failed attempt counters
        print("\n-- Resetting all lockouts --")
        for u in users:
            u.failed_login_attempts = 0
            u.locked_until = None
        await session.commit()
        print("Done. All accounts unlocked.")

if __name__ == "__main__":
    asyncio.run(main())
