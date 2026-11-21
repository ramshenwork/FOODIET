import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Checkin, MealEntry, Report


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def pending_entries(session: AsyncSession, user_id: uuid.UUID, start: datetime, end: datetime) -> list[MealEntry]:
    done = select(Checkin.meal_entry_id)
    return list(await session.scalars(select(MealEntry).where(
        MealEntry.user_id == user_id, MealEntry.branch_id.is_not(None), MealEntry.eaten_at >= start,
        MealEntry.eaten_at <= end, MealEntry.id.not_in(done)).order_by(MealEntry.eaten_at.desc())))


async def entry(session: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> MealEntry | None:
    return await session.scalar(select(MealEntry).where(MealEntry.id == entry_id, MealEntry.user_id == user_id))


async def checkin_for(session: AsyncSession, entry_id: uuid.UUID) -> Checkin | None:
    return await session.scalar(select(Checkin).where(Checkin.meal_entry_id == entry_id))


async def open_report(session: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID, type_: str) -> Report | None:
    return await session.scalar(select(Report).where(Report.user_id == user_id, Report.menu_item_id == item_id,
                                                     Report.type == type_, Report.status.in_(("open", "reviewing"))))
