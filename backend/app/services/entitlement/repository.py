import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import Entitlement, TrialClaim


async def get(session: AsyncSession, user_id: uuid.UUID) -> Entitlement | None:
    return await session.scalar(select(Entitlement).where(Entitlement.user_id == user_id))


async def trial_claimed(session: AsyncSession, email_hash: str | None, device_id: str | None) -> bool:
    conds = []
    if email_hash:
        conds.append(TrialClaim.email_hash == email_hash)
    if device_id:
        conds.append(TrialClaim.device_id == device_id)
    if not conds:
        return False
    return (await session.scalar(select(TrialClaim.id).where(or_(*conds)).limit(1))) is not None
