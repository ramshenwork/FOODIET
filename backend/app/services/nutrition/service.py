"""Runs the engine on stored recipes. Every number comes from engine.calculate (fixed rule 2)."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.models.nutrition import ReferenceRecipe
from app.services.ingredients import service as ingredients
from app.services.nutrition import engine, repository
from app.services.nutrition.schemas import EstimatedNutrition
from app.services.trust import service as trust


async def _collect(session: AsyncSession, root: ReferenceRecipe) -> tuple[dict, set]:
    """Load the reference recipe and every reference sub-recipe it uses; gather ingredient ids."""
    refs, ing_ids, frontier = {root.id: root}, set(), [root]
    while frontier:
        nxt = []
        for r in frontier:
            for line in r.ingredients:
                if "ingredient_id" in line:
                    ing_ids.add(uuid.UUID(line["ingredient_id"]))
                elif "sub_reference_id" in line:
                    sid = uuid.UUID(line["sub_reference_id"])
                    if sid not in refs:
                        nxt.append(sid)
        found = await repository.references(session, nxt) if nxt else {}
        missing = set(nxt) - set(found)
        if missing:
            raise AppError(500, "reference_broken", "A reference sub-recipe is missing.")
        refs.update(found)
        frontier = list(found.values())
    return refs, ing_ids


def _to_recipe(ref: ReferenceRecipe, refs: dict, ings: dict, building: tuple = ()) -> engine.RecipeData:
    if ref.id in building:
        raise engine.EngineError(f"Sub-recipe loop through {ref.name!r}.")
    lines = []
    for line in ref.ingredients:
        if "ingredient_id" in line:
            ing = ings.get(line["ingredient_id"])
            if ing is None:
                raise engine.EngineError(f"An ingredient of {ref.name!r} no longer exists.")
            lines.append(engine.Line(quantity_g=line["quantity_g"], ingredient=ing,
                                     oil_retained_g=line.get("oil_retained_g")))
        else:
            sub = refs[uuid.UUID(line["sub_reference_id"])]
            lines.append(engine.Line(quantity_g=line["quantity_g"],
                                     sub_recipe=_to_recipe(sub, refs, ings, building + (ref.id,)),
                                     oil_retained_g=line.get("oil_retained_g")))
    return engine.RecipeData(id=str(ref.id), name=ref.name, lines=tuple(lines), cooked_yield_g=ref.cooked_yield_g,
                             cooking_method=ref.cooking_method)


async def reference_recipe_data(session: AsyncSession, ref_id: uuid.UUID) -> tuple[ReferenceRecipe, engine.RecipeData]:
    ref = await repository.reference(session, ref_id)
    if ref is None:
        raise NotFound("Reference recipe not found")
    refs, ing_ids = await _collect(session, ref)
    ings = await ingredients.engine_inputs(session, list(ing_ids))
    return ref, _to_recipe(ref, refs, ings)


async def calculate_reference(session: AsyncSession, ref_id: uuid.UUID, serving_weight_g: float | None = None,
                              share_fraction: float = 1.0, require_cleared: bool = True) -> engine.Result:
    ref, recipe = await reference_recipe_data(session, ref_id)
    try:
        return engine.calculate(recipe, serving_weight_g or ref.serving_weight_g, share_fraction,
                                require_cleared=require_cleared)
    except engine.EngineError as e:
        raise AppError(422, "recipe_invalid", str(e)) from e


async def estimated_nutrition(session: AsyncSession, ref_id: uuid.UUID, serving_weight_g: float | None = None,
                              share_fraction: float = 1.0, require_cleared: bool = True) -> EstimatedNutrition:
    """Display-ready Estimated values for one serving (or per 100 g when the reference has no serving)."""
    ref = await repository.reference(session, ref_id)
    if ref is None:
        raise NotFound("Reference recipe not found")
    result = await calculate_reference(session, ref_id, serving_weight_g, share_fraction, require_cleared)
    values = result.eaten if result.eaten is not None else result.per_100g
    shown = trust.estimated_display(values, ref.spread)
    return EstimatedNutrition(reference_recipe_id=ref.id, reference_name=ref.name,
                              serving_weight_g=result.serving_weight_g, share_fraction=share_fraction, **shown)


# ------------------------------------------------------------------ restaurant recipe versions

from app.models.nutrition import NUTRIENTS, NutritionResult  # noqa: E402


async def version_recipe_data(session: AsyncSession, version_id: uuid.UUID) -> engine.RecipeData:
    """Engine input for a stored (immutable) recipe version, including its sub-recipe versions."""
    loaded, frontier, ing_ids = {}, [version_id], set()
    while frontier:
        vs = await repository.versions(session, frontier)
        if len(vs) != len(set(frontier)):
            raise AppError(500, "version_missing", "A recipe version is missing.")
        lines = await repository.version_lines(session, list(vs))
        nxt = []
        for vid, v in vs.items():
            loaded[vid] = (v, lines[vid])
            for l in lines[vid]:
                if l.ingredient_id:
                    ing_ids.add(l.ingredient_id)
                elif l.sub_recipe_version_id not in loaded:
                    nxt.append(l.sub_recipe_version_id)
        frontier = list(set(nxt))
    ings = await ingredients.engine_inputs(session, list(ing_ids))

    def build(vid, stack=()):
        if vid in stack:
            raise engine.EngineError("Sub-recipe loop.")
        v, lines = loaded[vid]
        out = []
        for l in lines:
            if l.ingredient_id:
                out.append(engine.Line(quantity_g=l.quantity_g, ingredient=ings[str(l.ingredient_id)],
                                       oil_retained_g=l.oil_retained_g))
            else:
                out.append(engine.Line(quantity_g=l.quantity_g, sub_recipe=build(l.sub_recipe_version_id, stack + (vid,))))
        return engine.RecipeData(id=str(vid), name=f"version {v.version_number}", lines=tuple(out),
                                 cooked_yield_g=v.cooked_yield_g, cooking_method=v.cooking_method)

    return build(version_id)


async def store_result(session: AsyncSession, result: engine.Result, *, version_id: uuid.UUID | None = None,
                       reference_id: uuid.UUID | None = None, serving_option_id: uuid.UUID | None = None,
                       spread: float, display_mode: str | None) -> None:
    """Cache an engine result (unrounded) keyed by version and sorted modifier set."""
    if await repository.cached_result(session, version_id, reference_id, serving_option_id, result.modifier_key):
        return
    values = result.per_serving if result.per_serving is not None else result.per_100g
    row = NutritionResult(recipe_version_id=version_id, reference_recipe_id=reference_id,
                          serving_option_id=serving_option_id, modifier_key=result.modifier_key,
                          engine_version=engine.ENGINE_VERSION, serving_weight_g=result.serving_weight_g,
                          display_mode=display_mode)
    for n in NUTRIENTS:
        mid = values[n]
        setattr(row, f"{n}_mid", mid)
        setattr(row, f"{n}_low", None if mid is None else mid * (1 - spread))
        setattr(row, f"{n}_high", None if mid is None else mid * (1 + spread))
    await repository.add_result(session, row)


async def reference_for(session: AsyncSession, dish_id: uuid.UUID | None, region: str | None) -> ReferenceRecipe | None:
    """The platform reference recipe for this dish and region: exact region first, then a generic one.
    A regional recipe is never used for another region (a Hyderabad biryani is not a Kolkata biryani)."""
    if dish_id is None:
        return None
    refs = await repository.references_for_dish(session, dish_id)
    exact = [r for r in refs if region and r.region == region]
    generic = [r for r in refs if r.region is None]
    return (exact or generic or [None])[0]


# ------------------------------------------------------------------ admin: cache and reference recipes

from app.services.nutrition.schemas import ReferenceAdmin, ReferenceIn  # noqa: E402


async def invalidate_cache(session: AsyncSession, reference_id: uuid.UUID | None = None) -> None:
    """Drop cached results after reference data changes; they are recalculated on request."""
    from app.services.search.service import clear_cache
    clear_cache()
    await repository.delete_results(session, reference_id)


async def _reference_out(session: AsyncSession, ref: ReferenceRecipe) -> ReferenceAdmin:
    from app.services.ontology import service as ontology
    from app.services.trust import service as trust
    energy, checks, cleared = None, [], False
    try:
        res = await calculate_reference(session, ref.id, require_cleared=False)
        e = res.per_100g["energy_kcal"]
        energy = None if e is None else f"{e:.0f} kcal per 100 g"
        band = await ontology.expected_kcal_range(session, ref.canonical_dish_id)
        checks = [{"rule": f.rule, "message": f.message} for f in
                  trust.check(res, band, [ref.serving_weight_g] if ref.serving_weight_g else [])]
        cleared = not res.uncleared_sources
    except AppError as e:
        checks = [{"rule": e.code, "message": e.message}]
    return ReferenceAdmin(id=ref.id, name=ref.name, canonical_dish_id=ref.canonical_dish_id, region=ref.region,
                          cooking_method=ref.cooking_method, cooked_yield_g=ref.cooked_yield_g,
                          serving_weight_g=ref.serving_weight_g, spread=ref.spread, notes=ref.notes,
                          lines=ref.ingredients, energy_100g=energy, checks=checks, licence_cleared=cleared)


async def admin_references(session: AsyncSession) -> list[ReferenceAdmin]:
    return [await _reference_out(session, r) for r in await repository.all_references(session)]


async def admin_reference(session: AsyncSession, ref_id: uuid.UUID) -> ReferenceAdmin:
    ref = await repository.reference(session, ref_id)
    if ref is None:
        raise NotFound("Reference recipe not found")
    return await _reference_out(session, ref)


async def admin_save_reference(session: AsyncSession, body: ReferenceIn, ref_id: uuid.UUID | None = None) -> ReferenceAdmin:
    if ref_id:
        ref = await repository.reference(session, ref_id)
        if ref is None:
            raise NotFound("Reference recipe not found")
    else:
        if await repository.reference_by_name(session, body.name):
            raise AppError(409, "reference_exists", "A reference recipe with that name already exists.")
        ref = ReferenceRecipe(name=body.name)
        session.add(ref)
    lines = []
    for l in body.lines:
        if l.sub_reference_id and l.sub_reference_id == ref_id:
            raise AppError(422, "sub_recipe_self", "A reference recipe can't use itself.")
        line = {"quantity_g": l.quantity_g}
        if l.ingredient_id:
            line["ingredient_id"] = str(l.ingredient_id)
        else:
            line["sub_reference_id"] = str(l.sub_reference_id)
        if l.oil_retained_g is not None:
            line["oil_retained_g"] = l.oil_retained_g
        lines.append(line)
    ref.name, ref.canonical_dish_id, ref.region = body.name, body.canonical_dish_id, (body.region or "").lower() or None
    ref.cooking_method, ref.cooked_yield_g, ref.serving_weight_g = body.cooking_method, body.cooked_yield_g, body.serving_weight_g
    ref.spread, ref.notes, ref.ingredients = body.spread, body.notes, lines
    await session.flush()
    try:  # validates ingredients exist and there is no sub-recipe loop
        await reference_recipe_data(session, ref.id)
    except engine.EngineError as e:
        raise AppError(422, "recipe_invalid", str(e)) from e
    await invalidate_cache(session, ref.id)
    return await _reference_out(session, ref)
