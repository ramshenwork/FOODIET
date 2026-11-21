import uuid

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Dispute, Report
from app.models.business import Branch, Business
from app.models.menus import MenuItem
from app.models.nutrition import PlausibilityFlag, TrustRecord
from app.models.recipes import Recipe, RecipeVersion


async def held_versions(session: AsyncSession, limit: int) -> list[tuple[RecipeVersion, Recipe, Business]]:
    rows = await session.execute(
        select(RecipeVersion, Recipe, Business).join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .join(Business, Business.id == RecipeVersion.business_id)
        .where(RecipeVersion.status == "held").order_by(RecipeVersion.declared_at).limit(limit))
    return [tuple(r) for r in rows.all()]


async def flags(session: AsyncSession, version_id: uuid.UUID) -> list[PlausibilityFlag]:
    return list(await session.scalars(select(PlausibilityFlag).where(PlausibilityFlag.recipe_version_id == version_id)
                                      .order_by(PlausibilityFlag.created_at)))


async def flag(session: AsyncSession, flag_id: uuid.UUID) -> PlausibilityFlag | None:
    return await session.get(PlausibilityFlag, flag_id)


async def version(session: AsyncSession, version_id: uuid.UUID) -> RecipeVersion | None:
    return await session.get(RecipeVersion, version_id)


async def recipe(session: AsyncSession, recipe_id: uuid.UUID) -> Recipe | None:
    return await session.get(Recipe, recipe_id)


async def previous_published(session: AsyncSession, v: RecipeVersion) -> RecipeVersion | None:
    return await session.scalar(select(RecipeVersion).where(
        RecipeVersion.recipe_id == v.recipe_id, RecipeVersion.status == "published",
        RecipeVersion.version_number < v.version_number).order_by(RecipeVersion.version_number.desc()).limit(1))


async def newer_published(session: AsyncSession, v: RecipeVersion) -> RecipeVersion | None:
    return await session.scalar(select(RecipeVersion).where(
        RecipeVersion.recipe_id == v.recipe_id, RecipeVersion.status == "published",
        RecipeVersion.version_number > v.version_number).limit(1))


async def disputes_for_flags(session: AsyncSession, flag_ids: list[uuid.UUID]) -> list[tuple[Dispute, str]]:
    if not flag_ids:
        return []
    rows = await session.execute(select(Dispute, Business.name).join(Business, Business.id == Dispute.business_id)
                                 .where(Dispute.flag_id.in_(flag_ids)).order_by(Dispute.created_at))
    return [tuple(r) for r in rows.all()]


async def disputes(session: AsyncSession, status: str | None, limit: int) -> list[tuple[Dispute, str]]:
    q = select(Dispute, Business.name).join(Business, Business.id == Dispute.business_id)
    if status:
        q = q.where(Dispute.status == status)
    rows = await session.execute(q.order_by((Dispute.status == "open").desc(), Dispute.created_at).limit(limit))
    return [tuple(r) for r in rows.all()]


async def dispute(session: AsyncSession, dispute_id: uuid.UUID) -> Dispute | None:
    return await session.get(Dispute, dispute_id)


async def reports(session: AsyncSession, status: str | None, limit: int):
    # Allergen concerns first, then menu and portion reports; open before closed.
    priority = case((Report.type == "allergen_concern", 0), else_=1)
    q = (select(Report, MenuItem.display_name, Business.name, Branch.name)
         .join(MenuItem, MenuItem.id == Report.menu_item_id)
         .join(Business, Business.id == MenuItem.business_id)
         .join(Branch, Branch.id == MenuItem.branch_id))
    if status:
        q = q.where(Report.status == status)
    q = q.order_by(case((Report.status.in_(("open", "reviewing")), 0), else_=1), priority, Report.created_at).limit(limit)
    return [tuple(r) for r in (await session.execute(q)).all()]


async def report(session: AsyncSession, report_id: uuid.UUID) -> Report | None:
    return await session.get(Report, report_id)


async def verified_records(session: AsyncSession, limit: int):
    rows = await session.execute(
        select(TrustRecord, RecipeVersion, Recipe, Business).join(RecipeVersion, RecipeVersion.id == TrustRecord.recipe_version_id)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id).join(Business, Business.id == RecipeVersion.business_id)
        .where(TrustRecord.label == "verified", TrustRecord.revoked_at.is_(None))
        .order_by(TrustRecord.expires_at).limit(limit))
    return [tuple(r) for r in rows.all()]


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def published_versions(session: AsyncSession, q: str | None, limit: int):
    from sqlalchemy import or_
    stmt = (select(RecipeVersion, Recipe, Business).join(Recipe, Recipe.id == RecipeVersion.recipe_id)
            .join(Business, Business.id == RecipeVersion.business_id).where(RecipeVersion.status == "published"))
    if q:
        stmt = stmt.where(or_(Recipe.name.ilike(f"%{q}%"), Business.name.ilike(f"%{q}%")))
    rows = await session.execute(stmt.order_by(Business.name, Recipe.name, RecipeVersion.version_number.desc()).limit(limit))
    return [tuple(r) for r in rows.all()]
