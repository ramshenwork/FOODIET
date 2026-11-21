"""Alembic environment. The database URL comes from .env (or ALEMBIC_DATABASE_URL for tests)."""
import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  registers all tables
from app.core.database import Base
from app.core.settings import get_settings

target_metadata = Base.metadata
URL = os.environ.get("ALEMBIC_DATABASE_URL") or get_settings().DATABASE_URL

# PostGIS owns these tables; never let autogenerate drop them.
IGNORED_TABLES = {"spatial_ref_sys"}


def include_object(obj, name, type_, reflected, compare_to):
    return not (type_ == "table" and name in IGNORED_TABLES)


def _run(connection):
    context.configure(connection=connection, target_metadata=target_metadata,
                      include_object=include_object, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def main():
    engine = create_async_engine(URL)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(main())
