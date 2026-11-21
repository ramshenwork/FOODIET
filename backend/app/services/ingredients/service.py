"""Ingredient catalogue and nutrient profiles; turns rows into engine inputs."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ingredients import Ingredient, NutrientProfile
from app.models.nutrition import NUTRIENTS
from app.services.ingredients import repository
from app.services.ingredients.schemas import IngredientHit
from app.services.nutrition.engine import IngredientData


def _per_100g(p: NutrientProfile | None) -> dict:
    return {n: (getattr(p, n) if p is not None else None) for n in NUTRIENTS}


def to_engine(ing: Ingredient, profile: NutrientProfile | None) -> IngredientData:
    return IngredientData(
        id=str(ing.id), name=ing.name, state=ing.state, per_100g=_per_100g(profile), category=ing.category,
        allergens=tuple(ing.allergen_flags or ()),
        licence_cleared=bool(profile and profile.licence_status == "cleared"),
    )


async def engine_inputs(session: AsyncSession, ids: list[uuid.UUID]) -> dict[str, IngredientData]:
    return {str(i.id): to_engine(i, p) for i, p in await repository.with_profiles(session, ids)}


async def search(session: AsyncSession, q: str, limit: int = 20) -> list[IngredientHit]:
    q = q.strip()
    if len(q) < 2:
        return []
    return [IngredientHit(id=i.id, name=i.name, state=i.state, category=i.category, allergens=i.allergen_flags or [],
                          data_complete=p is not None and all(getattr(p, n) is not None for n in NUTRIENTS),
                          licence_cleared=bool(p and p.licence_status == "cleared"))
            for i, p in await repository.search(session, q, limit)]


# ------------------------------------------------------------------ admin (reference data)

from app.core.errors import AppError, NotFound  # noqa: E402
from app.services.ingredients.schemas import IngredientAdmin, IngredientIn, ProfileIn  # noqa: E402

ALLERGENS = {"milk", "egg", "fish", "crustacean", "tree_nut", "peanut", "gluten", "soy", "sesame", "mustard",
             "celery", "sulphite", "lupin", "mollusc"}


def _admin_out(i: Ingredient, p: NutrientProfile | None) -> IngredientAdmin:
    prof = None if p is None else ProfileIn(**{n: getattr(p, n) for n in NUTRIENTS}, source=p.source,
                                            source_version=p.source_version, licence_status=p.licence_status)
    return IngredientAdmin(id=i.id, name=i.name, category=i.category, state=i.state, allergens=i.allergen_flags or [],
                           profile=prof)


async def admin_list(session: AsyncSession, q: str | None, licence: str | None, limit: int = 200) -> list[IngredientAdmin]:
    return [_admin_out(i, p) for i, p in await repository.admin_list(session, q, licence, limit)]


def _check_allergens(names: list[str]) -> list[str]:
    unknown = set(names) - ALLERGENS
    if unknown:
        raise AppError(422, "allergen_unknown", f"Unknown allergen: {', '.join(sorted(unknown))}.")
    return sorted(set(names))


async def admin_save(session: AsyncSession, body: IngredientIn, ingredient_id: uuid.UUID | None = None) -> IngredientAdmin:
    """Create or update an ingredient and its nutrient profile. Values left empty stay unknown (never zero)."""
    from app.services.nutrition import service as nutrition
    if ingredient_id:
        ing = await session.get(Ingredient, ingredient_id)
        if ing is None:
            raise NotFound("Ingredient not found")
    else:
        if await repository.by_name(session, body.name):
            raise AppError(409, "ingredient_exists", "An ingredient with that name already exists.")
        ing = await repository.add(session, Ingredient(name=body.name, state=body.state))
    ing.name, ing.category, ing.state, ing.allergen_flags = body.name, body.category, body.state, _check_allergens(body.allergens)
    prof = await repository.profile_for(session, ing.id)
    if prof is None:
        prof = await repository.add(session, NutrientProfile(ingredient_id=ing.id, source=body.profile.source))
    for k, v in body.profile.model_dump().items():
        setattr(prof, k, v)
    await session.flush()
    await nutrition.invalidate_cache(session)
    return _admin_out(ing, prof)


async def set_licence(session: AsyncSession, ids: list[uuid.UUID], status: str) -> int:
    profiles = await repository.profiles_for(session, ids)
    from app.services.search.service import clear_cache
    clear_cache()
    for p in profiles:
        p.licence_status = status
    return len(profiles)
