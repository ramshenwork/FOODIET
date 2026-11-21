"""Every query is scoped by business_id; callers pass the business the user was checked against."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Membership
from app.models.ingredients import Ingredient
from app.models.menus import MenuItem
from app.models.recipes import Modifier, ModifierGroup, Recipe, RecipeIngredient, RecipeVersion, ServingOption


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def recipe(session: AsyncSession, business_id: uuid.UUID, recipe_id: uuid.UUID) -> Recipe | None:
    return await session.scalar(select(Recipe).where(Recipe.id == recipe_id, Recipe.business_id == business_id))


async def recipe_for_member(session: AsyncSession, recipe_id: uuid.UUID, user_id: uuid.UUID) -> Recipe | None:
    return await session.scalar(select(Recipe).join(Membership, Membership.business_id == Recipe.business_id)
                                .where(Recipe.id == recipe_id, Membership.user_id == user_id))


async def recipes(session: AsyncSession, business_id: uuid.UUID) -> list[Recipe]:
    return list(await session.scalars(select(Recipe).where(Recipe.business_id == business_id).order_by(Recipe.name)))


async def versions(session: AsyncSession, business_id: uuid.UUID, recipe_id: uuid.UUID) -> list[RecipeVersion]:
    return list(await session.scalars(select(RecipeVersion).where(RecipeVersion.recipe_id == recipe_id,
                                                                  RecipeVersion.business_id == business_id)
                                      .order_by(RecipeVersion.version_number)))


async def version(session: AsyncSession, business_id: uuid.UUID, version_id: uuid.UUID) -> RecipeVersion | None:
    return await session.scalar(select(RecipeVersion).where(RecipeVersion.id == version_id,
                                                            RecipeVersion.business_id == business_id))


async def latest_published(session: AsyncSession, business_id: uuid.UUID, recipe_id: uuid.UUID) -> RecipeVersion | None:
    return await session.scalar(select(RecipeVersion).where(
        RecipeVersion.recipe_id == recipe_id, RecipeVersion.business_id == business_id,
        RecipeVersion.status == "published").order_by(RecipeVersion.version_number.desc()).limit(1))


async def next_version_number(session: AsyncSession, recipe_id: uuid.UUID) -> int:
    return (await session.scalar(select(func.max(RecipeVersion.version_number))
                                 .where(RecipeVersion.recipe_id == recipe_id)) or 0) + 1


async def lines(session: AsyncSession, version_id: uuid.UUID) -> list[RecipeIngredient]:
    return list(await session.scalars(select(RecipeIngredient).where(RecipeIngredient.recipe_version_id == version_id)
                                      .order_by(RecipeIngredient.position)))


async def ingredients(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, Ingredient]:
    return {i.id: i for i in await session.scalars(select(Ingredient).where(Ingredient.id.in_(ids)))}


async def items_following(session: AsyncSession, business_id: uuid.UUID, recipe_id: uuid.UUID,
                          branch_id: uuid.UUID | None = None) -> list[MenuItem]:
    q = select(MenuItem).where(MenuItem.business_id == business_id, MenuItem.recipe_id == recipe_id,
                               MenuItem.deleted_at.is_(None))
    if branch_id:
        q = q.where(MenuItem.branch_id == branch_id)
    return list(await session.scalars(q))


async def item(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID) -> MenuItem | None:
    return await session.scalar(select(MenuItem).where(MenuItem.id == item_id, MenuItem.business_id == business_id,
                                                       MenuItem.deleted_at.is_(None)))


async def item_for_member(session: AsyncSession, item_id: uuid.UUID, user_id: uuid.UUID) -> MenuItem | None:
    return await session.scalar(select(MenuItem).join(Membership, Membership.business_id == MenuItem.business_id)
                                .where(MenuItem.id == item_id, Membership.user_id == user_id, MenuItem.deleted_at.is_(None)))


async def servings(session: AsyncSession, business_id: uuid.UUID, item_ids: list[uuid.UUID]) -> list[ServingOption]:
    if not item_ids:
        return []
    return list(await session.scalars(select(ServingOption).where(ServingOption.business_id == business_id,
                                                                  ServingOption.menu_item_id.in_(item_ids))
                                      .order_by(ServingOption.is_default.desc(), ServingOption.created_at)))


async def serving(session: AsyncSession, business_id: uuid.UUID, serving_id: uuid.UUID) -> ServingOption | None:
    return await session.scalar(select(ServingOption).where(ServingOption.id == serving_id,
                                                            ServingOption.business_id == business_id))


async def groups(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID) -> list[ModifierGroup]:
    return list(await session.scalars(select(ModifierGroup).where(ModifierGroup.business_id == business_id,
                                                                  ModifierGroup.menu_item_id == item_id)
                                      .order_by(ModifierGroup.created_at)))


async def group(session: AsyncSession, business_id: uuid.UUID, group_id: uuid.UUID) -> ModifierGroup | None:
    return await session.scalar(select(ModifierGroup).where(ModifierGroup.id == group_id,
                                                            ModifierGroup.business_id == business_id))


async def modifiers(session: AsyncSession, business_id: uuid.UUID, group_ids: list[uuid.UUID]) -> list[Modifier]:
    if not group_ids:
        return []
    return list(await session.scalars(select(Modifier).where(Modifier.business_id == business_id,
                                                             Modifier.group_id.in_(group_ids)).order_by(Modifier.created_at)))


async def modifier(session: AsyncSession, business_id: uuid.UUID, modifier_id: uuid.UUID) -> Modifier | None:
    return await session.scalar(select(Modifier).where(Modifier.id == modifier_id, Modifier.business_id == business_id))


async def delete(session: AsyncSession, obj) -> None:
    await session.delete(obj)
    await session.flush()
