import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import MealEntry, MealEntryItem


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def by_key(session: AsyncSession, key: str) -> MealEntry | None:
    return await session.scalar(select(MealEntry).where(MealEntry.idempotency_key == key))


async def entries_between(session: AsyncSession, user_id: uuid.UUID, start: datetime, end: datetime) -> list[MealEntry]:
    return list(await session.scalars(select(MealEntry).where(MealEntry.user_id == user_id, MealEntry.eaten_at >= start,
                                                              MealEntry.eaten_at < end).order_by(MealEntry.eaten_at)))


async def items(session: AsyncSession, entry_ids: list[uuid.UUID]) -> list[MealEntryItem]:
    if not entry_ids:
        return []
    return list(await session.scalars(select(MealEntryItem).where(MealEntryItem.meal_entry_id.in_(entry_ids))
                                      .order_by(MealEntryItem.created_at)))


async def entry(session: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> MealEntry | None:
    return await session.scalar(select(MealEntry).where(MealEntry.id == entry_id, MealEntry.user_id == user_id))


async def delete(session: AsyncSession, obj) -> None:
    await session.delete(obj)
    await session.flush()


async def all_for_user(session: AsyncSession, user_id: uuid.UUID) -> list[MealEntry]:
    return list(await session.scalars(select(MealEntry).where(MealEntry.user_id == user_id).order_by(MealEntry.eaten_at)))
