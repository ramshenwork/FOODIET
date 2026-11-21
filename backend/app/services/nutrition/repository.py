import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition import ReferenceRecipe


async def reference(session: AsyncSession, ref_id: uuid.UUID) -> ReferenceRecipe | None:
    return await session.get(ReferenceRecipe, ref_id)


async def references(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, ReferenceRecipe]:
    rows = await session.scalars(select(ReferenceRecipe).where(ReferenceRecipe.id.in_(ids)))
    return {r.id: r for r in rows}


async def all_references(session: AsyncSession) -> list[ReferenceRecipe]:
    return list(await session.scalars(select(ReferenceRecipe).order_by(ReferenceRecipe.name)))


from app.models.nutrition import NutritionResult  # noqa: E402
from app.models.recipes import RecipeIngredient, RecipeVersion  # noqa: E402


async def version(session: AsyncSession, version_id: uuid.UUID) -> RecipeVersion | None:
    return await session.get(RecipeVersion, version_id)


async def version_lines(session: AsyncSession, version_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[RecipeIngredient]]:
    rows = await session.scalars(select(RecipeIngredient).where(RecipeIngredient.recipe_version_id.in_(version_ids))
                                 .order_by(RecipeIngredient.position))
    out: dict[uuid.UUID, list[RecipeIngredient]] = {v: [] for v in version_ids}
    for r in rows:
        out[r.recipe_version_id].append(r)
    return out


async def versions(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, RecipeVersion]:
    return {v.id: v for v in await session.scalars(select(RecipeVersion).where(RecipeVersion.id.in_(ids)))}


async def cached_result(session: AsyncSession, version_id: uuid.UUID | None, reference_id: uuid.UUID | None,
                        serving_option_id: uuid.UUID | None, modifier_key: str) -> NutritionResult | None:
    return await session.scalar(select(NutritionResult).where(
        NutritionResult.recipe_version_id.is_not_distinct_from(version_id),
        NutritionResult.reference_recipe_id.is_not_distinct_from(reference_id),
        NutritionResult.serving_option_id.is_not_distinct_from(serving_option_id),
        NutritionResult.modifier_key == modifier_key))


async def add_result(session: AsyncSession, row: NutritionResult) -> None:
    session.add(row)
    await session.flush()


async def references_for_dish(session: AsyncSession, dish_id: uuid.UUID) -> list[ReferenceRecipe]:
    return list(await session.scalars(select(ReferenceRecipe).where(ReferenceRecipe.canonical_dish_id == dish_id)))


from sqlalchemy import delete  # noqa: E402


async def delete_results(session: AsyncSession, reference_id: uuid.UUID | None = None) -> None:
    q = delete(NutritionResult)
    if reference_id is not None:
        q = q.where(NutritionResult.reference_recipe_id == reference_id)
    await session.execute(q)


async def reference_by_name(session: AsyncSession, name: str) -> ReferenceRecipe | None:
    return await session.scalar(select(ReferenceRecipe).where(ReferenceRecipe.name == name))
