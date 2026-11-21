import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingredients import Ingredient, NutrientProfile


async def search(session: AsyncSession, q: str, limit: int) -> list[tuple[Ingredient, NutrientProfile | None]]:
    sim = func.similarity(Ingredient.name, q)
    stmt = (select(Ingredient, NutrientProfile)
            .outerjoin(NutrientProfile, NutrientProfile.ingredient_id == Ingredient.id)
            .where(or_(Ingredient.name.ilike(f"%{q}%"), Ingredient.name.op("%")(q)))
            .order_by(Ingredient.name.ilike(f"{q}%").desc(), sim.desc(), Ingredient.name)
            .limit(limit))
    return [tuple(r) for r in (await session.execute(stmt)).all()]


async def with_profiles(session: AsyncSession, ids: list[uuid.UUID]) -> list[tuple[Ingredient, NutrientProfile | None]]:
    stmt = (select(Ingredient, NutrientProfile)
            .outerjoin(NutrientProfile, NutrientProfile.ingredient_id == Ingredient.id)
            .where(Ingredient.id.in_(ids)))
    return [tuple(r) for r in (await session.execute(stmt)).all()]


async def by_name(session: AsyncSession, name: str) -> Ingredient | None:
    return await session.scalar(select(Ingredient).where(Ingredient.name == name))


async def profile_for(session: AsyncSession, ingredient_id: uuid.UUID) -> NutrientProfile | None:
    return await session.scalar(select(NutrientProfile).where(NutrientProfile.ingredient_id == ingredient_id))


async def admin_list(session: AsyncSession, q: str | None, licence: str | None, limit: int):
    stmt = (select(Ingredient, NutrientProfile).outerjoin(NutrientProfile, NutrientProfile.ingredient_id == Ingredient.id))
    if q:
        stmt = stmt.where(Ingredient.name.ilike(f"%{q}%"))
    if licence:
        stmt = stmt.where(NutrientProfile.licence_status == licence)
    return [tuple(r) for r in (await session.execute(stmt.order_by(Ingredient.name).limit(limit))).all()]


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def profiles_for(session: AsyncSession, ids: list[uuid.UUID]) -> list[NutrientProfile]:
    return list(await session.scalars(select(NutrientProfile).where(NutrientProfile.ingredient_id.in_(ids))))
