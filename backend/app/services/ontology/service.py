"""Canonical dishes: for search, matching and comparison only. They hold no nutrition."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology import CanonicalDish
from app.services.ontology import repository
from app.services.ontology.schemas import DishHit


async def search(session: AsyncSession, q: str, limit: int = 20) -> list[DishHit]:
    q = q.strip()
    if len(q) < 2:
        return []
    rows = await repository.search(session, q, limit)
    return [DishHit(id=d.id, name=d.name, cuisine=d.cuisine, region=d.region, diet_class=d.diet_class,
                    matched_alias=None if q.lower() in d.name.lower() else alias) for d, alias in rows]


async def expected_kcal_range(session: AsyncSession, dish_id: uuid.UUID | None) -> tuple[float, float] | None:
    """The plausibility band. Not served nutrition."""
    if dish_id is None:
        return None
    d = await session.get(CanonicalDish, dish_id)
    if d is None or d.expected_kcal_100g_low is None or d.expected_kcal_100g_high is None:
        return None
    return d.expected_kcal_100g_low, d.expected_kcal_100g_high


async def best_match(session: AsyncSession, text: str) -> DishHit | None:
    """Suggest a canonical dish for a menu line (trigram similarity on names and aliases). A suggestion only."""
    hits = await search(session, text, limit=1)
    return hits[0] if hits else None


# ------------------------------------------------------------------ admin (reference data)

from app.core.errors import AppError, NotFound  # noqa: E402
from app.services.ontology.schemas import AliasIn, DishAdmin, DishIn, VariantIn  # noqa: E402


async def _admin_out(session: AsyncSession, d: CanonicalDish) -> DishAdmin:
    return DishAdmin(id=d.id, name=d.name, cuisine=d.cuisine, region=d.region, diet_class=d.diet_class,
                     expected_kcal_100g_low=d.expected_kcal_100g_low, expected_kcal_100g_high=d.expected_kcal_100g_high,
                     aliases=[AliasIn(alias=a.alias, language=a.language, transliteration=a.transliteration)
                              for a in await repository.aliases(session, d.id)],
                     variants=[VariantIn(region=v.region, name=v.name) for v in await repository.variants(session, d.id)],
                     reference_recipes=await repository.reference_count(session, d.id))


async def admin_list(session: AsyncSession, q: str | None, limit: int = 200) -> list[DishAdmin]:
    return [await _admin_out(session, d) for d in await repository.admin_list(session, q, limit)]


async def admin_save(session: AsyncSession, body: DishIn, dish_id: uuid.UUID | None = None) -> DishAdmin:
    lo, hi = body.expected_kcal_100g_low, body.expected_kcal_100g_high
    if lo is not None and hi is not None and lo > hi:
        raise AppError(422, "range_inverted", "The low end of the expected range must be below the high end.")
    if dish_id:
        d = await session.get(CanonicalDish, dish_id)
        if d is None:
            raise NotFound("Dish not found")
    else:
        if await repository.by_name(session, body.name):
            raise AppError(409, "dish_exists", "A dish with that name already exists.")
        d = CanonicalDish(name=body.name)
        session.add(d)
    d.name, d.cuisine, d.region, d.diet_class = body.name, body.cuisine, (body.region or None), body.diet_class
    d.expected_kcal_100g_low, d.expected_kcal_100g_high = lo, hi
    await session.flush()
    await repository.replace_children(session, d.id, body.aliases, body.variants)
    return await _admin_out(session, d)
