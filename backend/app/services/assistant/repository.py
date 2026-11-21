import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import AssistantMessage


async def add(session: AsyncSession, row: AssistantMessage) -> None:
    session.add(row)
    await session.flush()


async def since(session: AsyncSession, user_id: uuid.UUID, start: datetime) -> list[AssistantMessage]:
    return list(await session.scalars(select(AssistantMessage).where(AssistantMessage.user_id == user_id,
                                                                     AssistantMessage.created_at >= start)
                                      .order_by(AssistantMessage.created_at)))


async def questions_since(session: AsyncSession, user_id: uuid.UUID, start: datetime) -> int:
    return await session.scalar(select(func.count()).select_from(AssistantMessage).where(
        AssistantMessage.user_id == user_id, AssistantMessage.role == "user", AssistantMessage.created_at >= start))


async def all_for(session: AsyncSession, user_id: uuid.UUID) -> list[AssistantMessage]:
    return list(await session.scalars(select(AssistantMessage).where(AssistantMessage.user_id == user_id)
                                      .order_by(AssistantMessage.created_at)))


async def delete_all(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(delete(AssistantMessage).where(AssistantMessage.user_id == user_id))
