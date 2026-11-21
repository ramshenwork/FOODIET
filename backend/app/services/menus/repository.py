import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menus import Menu, MenuCategory, MenuImport, MenuItem
from app.models.ontology import CanonicalDish
from app.models.recipes import Recipe, RecipeVersion


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def menu_for_branch(session: AsyncSession, business_id: uuid.UUID, branch_id: uuid.UUID) -> Menu | None:
    return await session.scalar(select(Menu).where(Menu.business_id == business_id, Menu.branch_id == branch_id)
                                .order_by(Menu.created_at).limit(1))


async def categories(session: AsyncSession, business_id: uuid.UUID, menu_id: uuid.UUID) -> list[MenuCategory]:
    return list(await session.scalars(select(MenuCategory).where(MenuCategory.business_id == business_id,
                                                                 MenuCategory.menu_id == menu_id)
                                      .order_by(MenuCategory.position, MenuCategory.name)))


async def category(session: AsyncSession, business_id: uuid.UUID, category_id: uuid.UUID) -> MenuCategory | None:
    return await session.scalar(select(MenuCategory).where(MenuCategory.id == category_id,
                                                           MenuCategory.business_id == business_id))


async def items_for_branch(session: AsyncSession, business_id: uuid.UUID, branch_id: uuid.UUID,
                           published_only: bool = False) -> list[MenuItem]:
    q = select(MenuItem).where(MenuItem.business_id == business_id, MenuItem.branch_id == branch_id,
                               MenuItem.deleted_at.is_(None))
    if published_only:
        q = q.where(MenuItem.status == "published")
    return list(await session.scalars(q.order_by(MenuItem.display_name)))


async def items_for_business(session: AsyncSession, business_id: uuid.UUID) -> list[MenuItem]:
    return list(await session.scalars(select(MenuItem).where(MenuItem.business_id == business_id,
                                                             MenuItem.deleted_at.is_(None))))


async def item(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID) -> MenuItem | None:
    return await session.scalar(select(MenuItem).where(MenuItem.id == item_id, MenuItem.business_id == business_id,
                                                       MenuItem.deleted_at.is_(None)))


async def dish_names(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict((await session.execute(select(CanonicalDish.id, CanonicalDish.name).where(CanonicalDish.id.in_(ids)))).all())


async def recipe(session: AsyncSession, business_id: uuid.UUID, recipe_id: uuid.UUID) -> Recipe | None:
    return await session.scalar(select(Recipe).where(Recipe.id == recipe_id, Recipe.business_id == business_id))


async def recipe_names(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict((await session.execute(select(Recipe.id, Recipe.name).where(Recipe.id.in_(ids)))).all())


async def versions_for_business(session: AsyncSession, business_id: uuid.UUID) -> list[RecipeVersion]:
    return list(await session.scalars(select(RecipeVersion).where(RecipeVersion.business_id == business_id)))


async def import_(session: AsyncSession, business_id: uuid.UUID, import_id: uuid.UUID) -> MenuImport | None:
    return await session.scalar(select(MenuImport).where(MenuImport.id == import_id, MenuImport.business_id == business_id))
