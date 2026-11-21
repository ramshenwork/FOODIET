"""DEVELOPMENT ONLY: mark placeholder nutrient profiles as cleared so publishing can be tried locally.

Refuses to run unless APP_ENV=development. Real data must be licensed and cleared by an admin (phase 4).
Run from backend/:  ../.venv/bin/python -m jobs.dev_clear_placeholders
"""
import asyncio

from sqlalchemy import update

from app.core import database
from app.core.settings import get_settings
from app.models.ingredients import NutrientProfile


async def clear(session) -> int:
    if get_settings().APP_ENV != "development":
        raise SystemExit("Refusing: this command only runs with APP_ENV=development.")
    res = await session.execute(update(NutrientProfile).where(NutrientProfile.source == "placeholder")
                                .values(licence_status="cleared", source_version="placeholder-DEV-CLEARED"))
    return res.rowcount


async def main():
    async with database.sessionmaker()() as s:
        n = await clear(s)
        await s.commit()
    print(f"Marked {n} placeholder profiles as cleared in this development database.")


if __name__ == "__main__":
    asyncio.run(main())
