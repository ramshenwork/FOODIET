import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Checkin, DishStats, Event, MealEntry, MealEntryItem, OutletStats
from app.models.business import Branch
from app.models.menus import MenuItem
from app.models.ontology import CanonicalDish
from app.models.profile import ConsentRecord, LearnedPreference


async def entries_since(session: AsyncSession, since: datetime) -> list[MealEntry]:
    return list(await session.scalars(select(MealEntry).where(MealEntry.eaten_at >= since)))


async def items_for(session: AsyncSession, entry_ids: list[uuid.UUID]) -> list[MealEntryItem]:
    if not entry_ids:
        return []
    return list(await session.scalars(select(MealEntryItem).where(MealEntryItem.meal_entry_id.in_(entry_ids))))


async def checkins_for(session: AsyncSession, entry_ids: list[uuid.UUID]) -> list[Checkin]:
    if not entry_ids:
        return []
    return list(await session.scalars(select(Checkin).where(Checkin.meal_entry_id.in_(entry_ids))))


async def events(session: AsyncSession, name: str, since: datetime) -> list[Event]:
    return list(await session.scalars(select(Event).where(Event.name == name, Event.created_at >= since)))


async def all_items(session: AsyncSession) -> list[MenuItem]:
    return list(await session.scalars(select(MenuItem).where(MenuItem.deleted_at.is_(None))))


async def dish_stats(session: AsyncSession, item_id: uuid.UUID) -> DishStats | None:
    return await session.scalar(select(DishStats).where(DishStats.menu_item_id == item_id))


async def outlet_stats(session: AsyncSession, branch_id: uuid.UUID) -> OutletStats | None:
    return await session.scalar(select(OutletStats).where(OutletStats.branch_id == branch_id))


async def branches(session: AsyncSession) -> list[Branch]:
    return list(await session.scalars(select(Branch).where(Branch.deleted_at.is_(None))))


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def dish_cuisine(session: AsyncSession) -> dict[uuid.UUID, tuple[str, str | None]]:
    rows = await session.execute(select(MenuItem.id, CanonicalDish.name, CanonicalDish.cuisine)
                                 .join(CanonicalDish, CanonicalDish.id == MenuItem.canonical_dish_id))
    return {i: (n, c) for i, n, c in rows.all()}


async def consented_users(session: AsyncSession, purpose: str) -> set[uuid.UUID]:
    rows = await session.scalars(select(ConsentRecord.user_id).where(ConsentRecord.purpose == purpose,
                                                                     ConsentRecord.withdrawn_at.is_(None)))
    return set(rows)


async def learned(session: AsyncSession, user_id: uuid.UUID) -> list[LearnedPreference]:
    return list(await session.scalars(select(LearnedPreference).where(LearnedPreference.user_id == user_id)
                                      .order_by(LearnedPreference.weight.desc())))


async def delete_learned(session: AsyncSession, user_id: uuid.UUID, keep_suppressed: bool = True) -> None:
    q = delete(LearnedPreference).where(LearnedPreference.user_id == user_id)
    if keep_suppressed:
        q = q.where(LearnedPreference.weight >= 0)
    await session.execute(q)
