from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology import CanonicalDish, DishAlias


async def search(session: AsyncSession, q: str, limit: int) -> list[tuple[CanonicalDish, str | None]]:
    alias_match = (select(DishAlias.canonical_dish_id, func.min(DishAlias.alias).label("alias"))
                   .where(or_(DishAlias.alias.ilike(f"%{q}%"), DishAlias.alias.op("%")(q),
                              DishAlias.transliteration.ilike(f"%{q}%")))
                   .group_by(DishAlias.canonical_dish_id).subquery())
    name_hit = or_(CanonicalDish.name.ilike(f"%{q}%"), CanonicalDish.name.op("%")(q))
    stmt = (select(CanonicalDish, alias_match.c.alias)
            .outerjoin(alias_match, alias_match.c.canonical_dish_id == CanonicalDish.id)
            .where(or_(name_hit, alias_match.c.alias.is_not(None)))
            .order_by(CanonicalDish.name.ilike(f"{q}%").desc(), func.similarity(CanonicalDish.name, q).desc(),
                      CanonicalDish.name)
            .limit(limit))
    return [tuple(r) for r in (await session.execute(stmt)).all()]


async def by_name(session: AsyncSession, name: str) -> CanonicalDish | None:
    return await session.scalar(select(CanonicalDish).where(CanonicalDish.name == name))


from sqlalchemy import delete  # noqa: E402

from app.models.nutrition import ReferenceRecipe  # noqa: E402
from app.models.ontology import RegionalVariant  # noqa: E402


async def admin_list(session: AsyncSession, q: str | None, limit: int) -> list[CanonicalDish]:
    stmt = select(CanonicalDish)
    if q:
        stmt = stmt.where(CanonicalDish.name.ilike(f"%{q}%"))
    return list(await session.scalars(stmt.order_by(CanonicalDish.name).limit(limit)))


async def aliases(session: AsyncSession, dish_id) -> list[DishAlias]:
    return list(await session.scalars(select(DishAlias).where(DishAlias.canonical_dish_id == dish_id)))


async def variants(session: AsyncSession, dish_id) -> list[RegionalVariant]:
    return list(await session.scalars(select(RegionalVariant).where(RegionalVariant.canonical_dish_id == dish_id)))


async def reference_count(session: AsyncSession, dish_id) -> int:
    return len(list(await session.scalars(select(ReferenceRecipe.id).where(ReferenceRecipe.canonical_dish_id == dish_id))))


async def replace_children(session: AsyncSession, dish_id, aliases_in, variants_in) -> None:
    await session.execute(delete(DishAlias).where(DishAlias.canonical_dish_id == dish_id))
    await session.execute(delete(RegionalVariant).where(RegionalVariant.canonical_dish_id == dish_id))
    for a in aliases_in:
        session.add(DishAlias(canonical_dish_id=dish_id, **a.model_dump()))
    for v in variants_in:
        session.add(RegionalVariant(canonical_dish_id=dish_id, region=v.region.lower(), name=v.name))
    await session.flush()
