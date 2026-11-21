"""Test-server start-up (Render free plan has no pre-deploy step): migrate, then seed an empty database
with the placeholder reference data, the demo restaurants and the test admin. Never runs in production."""
import asyncio
import subprocess
import sys

from sqlalchemy import text

from app.core import database
from app.core.settings import get_settings


async def seed_if_empty() -> None:
    from jobs import dev_clear_placeholders, dev_seed_demo, make_admin, seed_reference
    async with database.sessionmaker()() as s:
        if await s.scalar(text("SELECT count(*) FROM ingredients")):
            print("staging_boot: data present, nothing to seed")
            return
    await seed_reference.main()
    await dev_clear_placeholders.main()
    await dev_seed_demo.main()
    for email in sorted(get_settings().test_signin_emails):
        if email.startswith("admin"):
            await make_admin.main(email)
    print("staging_boot: seeded")


if __name__ == "__main__":
    s = get_settings()
    if s.APP_ENV not in ("development", "staging"):
        sys.exit("Refusing: staging_boot only runs with APP_ENV=development or staging.")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    asyncio.run(seed_if_empty())
