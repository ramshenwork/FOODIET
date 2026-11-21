from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import AiUsage


async def add(session: AsyncSession, row: AiUsage) -> None:
    session.add(row)
    await session.flush()


async def spend_since(session: AsyncSession, since: datetime) -> float:
    return float(await session.scalar(select(func.coalesce(func.sum(AiUsage.cost_inr), 0)).where(AiUsage.created_at >= since)))
