"""Async SQLAlchemy engine, session dependency, and the shared declarative base."""
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.core.settings import get_settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class TableBase(Base):
    """Every table has a UUID id, created_at and updated_at."""
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


_engine = None
_sessionmaker = None


def _init(url: str | None = None):
    global _engine, _sessionmaker
    _engine = create_async_engine(url or get_settings().DATABASE_URL, pool_pre_ping=True)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


def configure(url: str) -> None:
    """Point the app at another database (used by tests)."""
    _init(url)


def sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        _init()
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
