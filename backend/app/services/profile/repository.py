import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Allergy, ConsentRecord, ConsumerProfile, LearnedPreference, Restriction, WeightLog


async def profile(session: AsyncSession, user_id: uuid.UUID) -> ConsumerProfile | None:
    return await session.scalar(select(ConsumerProfile).where(ConsumerProfile.user_id == user_id))


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def restrictions(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    return [r.type for r in await session.scalars(select(Restriction).where(Restriction.user_id == user_id))]


async def allergies(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    return [a.type for a in await session.scalars(select(Allergy).where(Allergy.user_id == user_id))]


async def replace_lists(session: AsyncSession, user_id: uuid.UUID, restrictions_in: list[str], allergies_in: list[str]) -> None:
    await session.execute(delete(Restriction).where(Restriction.user_id == user_id))
    await session.execute(delete(Allergy).where(Allergy.user_id == user_id))
    for r in restrictions_in:
        session.add(Restriction(user_id=user_id, type=r))
    for a in allergies_in:
        session.add(Allergy(user_id=user_id, type=a))
    await session.flush()


async def consents(session: AsyncSession, user_id: uuid.UUID) -> list[ConsentRecord]:
    return list(await session.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user_id)
                                      .order_by(ConsentRecord.granted_at)))


async def weight_log(session: AsyncSession, user_id: uuid.UUID) -> list[WeightLog]:
    return list(await session.scalars(select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.logged_on)))


async def delete_health_data(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(delete(Restriction).where(Restriction.user_id == user_id))
    await session.execute(delete(Allergy).where(Allergy.user_id == user_id))
    await session.execute(delete(WeightLog).where(WeightLog.user_id == user_id))


async def delete_all(session: AsyncSession, user_id: uuid.UUID) -> None:
    await delete_health_data(session, user_id)
    for model in (LearnedPreference, ConsentRecord, ConsumerProfile):
        await session.execute(delete(model).where(model.user_id == user_id))


async def now_withdraw(session: AsyncSession, user_id: uuid.UUID, purpose: str, at: datetime) -> None:
    for c in await consents(session, user_id):
        if c.purpose == purpose and c.withdrawn_at is None:
            c.withdrawn_at = at
