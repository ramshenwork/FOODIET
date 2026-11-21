import uuid

from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import cast, func, select
from geoalchemy2 import Geometry
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Branch, Brand, Business, Membership
from app.models.identity import User


async def membership(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID) -> Membership | None:
    return await session.scalar(select(Membership).where(Membership.user_id == user_id,
                                                         Membership.business_id == business_id))


async def businesses_for(session: AsyncSession, user_id: uuid.UUID) -> list[tuple[Business, str]]:
    rows = await session.execute(select(Business, Membership.role).join(Membership, Membership.business_id == Business.id)
                                 .where(Membership.user_id == user_id).order_by(Business.created_at))
    return [tuple(r) for r in rows.all()]


async def get(session: AsyncSession, business_id: uuid.UUID) -> Business | None:
    return await session.get(Business, business_id)


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def default_brand(session: AsyncSession, business_id: uuid.UUID) -> Brand | None:
    return await session.scalar(select(Brand).where(Brand.business_id == business_id).order_by(Brand.created_at).limit(1))


async def branches(session: AsyncSession, business_id: uuid.UUID) -> list[tuple[Branch, float | None, float | None]]:
    geom = cast(Branch.location, Geometry)
    rows = await session.execute(select(Branch, ST_Y(geom), ST_X(geom))
                                 .where(Branch.business_id == business_id, Branch.deleted_at.is_(None))
                                 .order_by(Branch.created_at))
    return [tuple(r) for r in rows.all()]


async def branch(session: AsyncSession, business_id: uuid.UUID, branch_id: uuid.UUID) -> Branch | None:
    return await session.scalar(select(Branch).where(Branch.id == branch_id, Branch.business_id == business_id,
                                                     Branch.deleted_at.is_(None)))


async def branch_for_member(session: AsyncSession, branch_id: uuid.UUID, user_id: uuid.UUID) -> Branch | None:
    """A branch only if the user is a member of its business (otherwise None -> 404)."""
    return await session.scalar(select(Branch).join(Membership, Membership.business_id == Branch.business_id)
                                .where(Branch.id == branch_id, Membership.user_id == user_id, Branch.deleted_at.is_(None)))


async def branch_by_code(session: AsyncSession, code: str) -> Branch | None:
    return await session.scalar(select(Branch).where(Branch.code == code, Branch.deleted_at.is_(None)))


async def count_branches(session: AsyncSession, business_id: uuid.UUID) -> int:
    return await session.scalar(select(func.count()).select_from(Branch)
                                .where(Branch.business_id == business_id, Branch.deleted_at.is_(None)))


async def code_taken(session: AsyncSession, code: str) -> bool:
    return (await session.scalar(select(Branch.id).where(Branch.code == code))) is not None


async def members(session: AsyncSession, business_id: uuid.UUID) -> list[tuple[Membership, str | None]]:
    rows = await session.execute(select(Membership, User.email).join(User, User.id == Membership.user_id)
                                 .where(Membership.business_id == business_id).order_by(Membership.created_at))
    return [tuple(r) for r in rows.all()]
