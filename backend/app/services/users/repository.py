import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import User


async def by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def create(session: AsyncSession, email: str, role: str) -> User:
    user = User(email=email, role=role)
    session.add(user)
    await session.flush()
    return user


async def admin_list(session: AsyncSession, q: str | None, role: str | None, limit: int) -> list[User]:
    stmt = select(User).where(User.status != "deleted")
    if q:
        stmt = stmt.where(User.email.ilike(f"%{q}%"))
    if role:
        stmt = stmt.where(User.role == role)
    return list(await session.scalars(stmt.order_by(User.created_at.desc()).limit(limit)))
