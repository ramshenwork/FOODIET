"""Test-server start-up (Render free plan has no pre-deploy step): migrate, then bring the test data up to date:
placeholder reference data, demo restaurants and the test admin. Every step only adds what is missing,
so new demo data reaches an existing test database on the next deploy. Never runs in production."""
import asyncio
import subprocess
import sys

from sqlalchemy import select

from app.core import database
from app.core.settings import get_settings
from app.models.identity import User


async def seed() -> None:
    from jobs import dev_clear_placeholders, dev_seed_demo, make_admin, seed_reference
    await seed_reference.main((seed_reference.SEED, seed_reference.DEMO_SEED))
    await dev_clear_placeholders.main()
    await dev_seed_demo.main(more=True)
    async with database.sessionmaker()() as s:
        admins = set((await s.scalars(select(User.email).where(User.role == "admin"))).all())
    for email in sorted(get_settings().test_signin_emails - admins):
        if email.startswith("admin"):
            await make_admin.main(email)
    print("staging_boot: test data up to date")


if __name__ == "__main__":
    s = get_settings()
    if s.APP_ENV not in ("development", "staging"):
        sys.exit("Refusing: staging_boot only runs with APP_ENV=development or staging.")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    asyncio.run(seed())
