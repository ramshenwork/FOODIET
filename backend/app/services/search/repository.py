import uuid

from geoalchemy2 import Geography
from sqlalchemy import cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import OutletStats
from app.models.business import Branch
from app.models.menus import MenuItem
from app.models.ontology import CanonicalDish, DishAlias


def _point(lat: float, lng: float):
    return cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), Geography)


async def branches_near(session: AsyncSession, lat: float, lng: float, radius_km: float, limit: int = 60):
    here = _point(lat, lng)
    dist = func.ST_Distance(Branch.location, here)
    rows = await session.execute(select(Branch, dist).where(
        Branch.deleted_at.is_(None), Branch.location.is_not(None), func.ST_DWithin(Branch.location, here, radius_km * 1000))
        .order_by(dist).limit(limit))
    return [(b, d / 1000) for b, d in rows.all()]


async def branch(session: AsyncSession, branch_id: uuid.UUID) -> Branch | None:
    return await session.scalar(select(Branch).where(Branch.id == branch_id, Branch.deleted_at.is_(None)))


async def distance_km(session: AsyncSession, branch_id: uuid.UUID, lat: float, lng: float) -> float | None:
    d = await session.scalar(select(func.ST_Distance(Branch.location, _point(lat, lng))).where(Branch.id == branch_id))
    return None if d is None else d / 1000


async def published_items(session: AsyncSession, branch_ids: list[uuid.UUID]) -> list[MenuItem]:
    if not branch_ids:
        return []
    return list(await session.scalars(select(MenuItem).where(
        MenuItem.branch_id.in_(branch_ids), MenuItem.status == "published", MenuItem.deleted_at.is_(None))
        .order_by(MenuItem.display_name)))


async def published_item(session: AsyncSession, item_id: uuid.UUID) -> MenuItem | None:
    return await session.scalar(select(MenuItem).where(MenuItem.id == item_id, MenuItem.status == "published",
                                                       MenuItem.deleted_at.is_(None)))


async def text_matches(session: AsyncSession, q: str, branch_ids: list[uuid.UUID]) -> dict[uuid.UUID, float]:
    """Similarity of each published item to the query: its name, its dish name, or a dish alias."""
    if not branch_ids:
        return {}
    alias_sim = (select(DishAlias.canonical_dish_id, func.max(func.similarity(DishAlias.alias, q)).label("s"))
                 .group_by(DishAlias.canonical_dish_id).subquery())
    sim = func.greatest(func.similarity(MenuItem.display_name, q), func.coalesce(func.similarity(CanonicalDish.name, q), 0),
                        func.coalesce(alias_sim.c.s, 0))
    hit = or_(MenuItem.display_name.ilike(f"%{q}%"), CanonicalDish.name.ilike(f"%{q}%"), sim > 0.3)
    rows = await session.execute(
        select(MenuItem.id, sim).outerjoin(CanonicalDish, CanonicalDish.id == MenuItem.canonical_dish_id)
        .outerjoin(alias_sim, alias_sim.c.canonical_dish_id == MenuItem.canonical_dish_id)
        .where(MenuItem.branch_id.in_(branch_ids), MenuItem.status == "published", MenuItem.deleted_at.is_(None), hit))
    return {i: max(float(s or 0), 0.3) for i, s in rows.all()}


async def dish_cuisines(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    if not ids:
        return {}
    return dict((await session.execute(select(CanonicalDish.id, CanonicalDish.cuisine).where(CanonicalDish.id.in_(ids)))).all())


async def outlet_stats(session: AsyncSession, branch_id: uuid.UUID) -> OutletStats | None:
    return await session.scalar(select(OutletStats).where(OutletStats.branch_id == branch_id))
