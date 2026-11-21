"""Recipes, immutable versions, live preview, publishing, branch overrides, servings and modifiers."""
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.models.recipes import Modifier, ModifierGroup, Recipe, RecipeIngredient, RecipeVersion, ServingOption
from app.services.businesses import service as businesses
from app.services.events import service as events
from app.services.ingredients import service as ingredients
from app.services.nutrition import engine
from app.services.nutrition import service as nutrition
from app.services.ontology import service as ontology
from app.services.recipes import repository
from app.services.recipes.schemas import (Check, LineIn, LineOut, ModifierGroupIn, ModifierGroupOut, ModifierIn,
                                          ModifierOut, NutritionBlock, PreviewIn, PreviewOut, RecipeIn, RecipeOut,
                                          ServingIn, ServingOut, VersionIn, VersionOut)
from app.services.trust import rules
from app.services.trust import service as trust

# Household measures are approximate; quantities are converted to grams on the server only.
ML_PER_UNIT = {"ml": 1, "l": 1000, "tsp": 5, "tbsp": 15, "cup": 240, "katori": 150}
FAT_DENSITY = 0.92


def to_grams(quantity: float, unit: str, category: str | None) -> float:
    if unit == "g":
        return quantity
    if unit == "kg":
        return quantity * 1000
    density = FAT_DENSITY if category == "fat" else 1.0
    return quantity * ML_PER_UNIT[unit] * density


# ------------------------------------------------------------------ building engine input from unsaved lines

async def _resolve(session: AsyncSession, business_id: uuid.UUID, lines: list[LineIn],
                   recipe_id: uuid.UUID | None = None) -> tuple[list[engine.Line], list[dict]]:
    ing_ids = [l.ingredient_id for l in lines if l.ingredient_id]
    rows = await repository.ingredients(session, ing_ids)
    eng_ings = await ingredients.engine_inputs(session, ing_ids)
    eng_lines, stored = [], []
    for pos, l in enumerate(lines):
        if l.ingredient_id:
            ing = rows.get(l.ingredient_id)
            if ing is None:
                raise AppError(422, "ingredient_unknown", "One of the ingredients no longer exists.")
            grams = to_grams(l.quantity, l.unit, ing.category)
            if l.oil_retained_g is not None and l.oil_retained_g > grams:
                raise AppError(422, "oil_retained_too_high", f"Retained oil for {ing.name} is more than the oil added.")
            eng_lines.append(engine.Line(quantity_g=grams, ingredient=eng_ings[str(ing.id)], oil_retained_g=l.oil_retained_g))
            stored.append(dict(ingredient_id=ing.id, quantity_g=grams, oil_retained_g=l.oil_retained_g,
                               entered_quantity=l.quantity, entered_unit=l.unit, position=pos, name=ing.name))
        else:
            if recipe_id and l.sub_recipe_id == recipe_id:
                raise AppError(422, "sub_recipe_self", "A recipe can't use itself as a sub-recipe.")
            sub = await repository.recipe(session, business_id, l.sub_recipe_id)
            if sub is None or not sub.is_sub_recipe:
                raise AppError(422, "sub_recipe_unknown", "That sub-recipe isn't one of yours.")
            sub_v = await repository.latest_published(session, business_id, sub.id)
            if sub_v is None:
                raise AppError(422, "sub_recipe_unpublished", f"Publish the sub-recipe {sub.name!r} first.")
            if l.unit not in ("g", "kg"):
                raise AppError(422, "sub_recipe_unit", "Enter sub-recipe quantities in grams or kilograms.")
            grams = to_grams(l.quantity, l.unit, None)
            eng_lines.append(engine.Line(quantity_g=grams, sub_recipe=await nutrition.version_recipe_data(session, sub_v.id)))
            stored.append(dict(sub_recipe_version_id=sub_v.id, quantity_g=grams, oil_retained_g=None,
                               entered_quantity=l.quantity, entered_unit=l.unit, position=pos, name=sub.name))
    return eng_lines, stored


def _block(result: engine.Result, effective: rules.EffectiveTrust) -> NutritionBlock:
    t = trust.thresholds()

    def shown(values):
        return rules.display_nutrients(values, effective, t)["nutrients"] if values is not None else None

    per_100 = rules.display_nutrients(result.per_100g, effective, t)
    return NutritionBlock(per_batch=shown(result.per_batch), per_100g=per_100["nutrients"],
                          per_serving=shown(result.per_serving), serving_weight_g=result.serving_weight_g,
                          trust={"label": effective.label, "note": effective.note}, display_mode=per_100["display_mode"],
                          allergens=list(result.allergens))


def _calc(recipe: engine.RecipeData, serving_g: float | None) -> engine.Result:
    try:
        return engine.calculate(recipe, serving_g)
    except engine.EngineError as e:
        raise AppError(422, "recipe_invalid", str(e)) from e


async def _context(session: AsyncSession, business_id: uuid.UUID, recipe_id: uuid.UUID | None,
                   dish_id: uuid.UUID | None) -> tuple[tuple | None, list[float]]:
    """Expected kcal band (from a linked canonical dish) and the serving weights of items using the recipe."""
    weights: list[float] = []
    if recipe_id:
        items = await repository.items_following(session, business_id, recipe_id)
        dish_id = dish_id or next((i.canonical_dish_id for i in items if i.canonical_dish_id), None)
        weights = [s.weight_g for s in await repository.servings(session, business_id, [i.id for i in items])]
    return await ontology.expected_kcal_range(session, dish_id), weights


def _licence_flag(result: engine.Result) -> list[rules.Flag]:
    if not result.uncleared_sources:
        return []
    return [rules.Flag("licence_not_cleared",
                       "Some ingredient data isn't cleared for publication yet: " + ", ".join(result.uncleared_sources),
                       {"ingredients": list(result.uncleared_sources)})]


async def preview(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, body: PreviewIn,
                  recipe_id: uuid.UUID | None = None) -> PreviewOut:
    """Live nutrition for an unsaved recipe. Nothing is stored."""
    await businesses.require(session, user_id, business_id, "edit_recipes")
    eng_lines, _ = await _resolve(session, business_id, body.lines, recipe_id)
    recipe = engine.RecipeData(id="preview", name="preview", lines=tuple(eng_lines), cooked_yield_g=body.cooked_yield_g,
                               cooking_method=body.cooking_method)
    result = _calc(recipe, body.serving_weight_g)
    band, weights = await _context(session, business_id, recipe_id, body.canonical_dish_id)
    flags = trust.check(result, band, weights + ([body.serving_weight_g] if body.serving_weight_g else []))
    t = trust.thresholds()
    effective = rules.EffectiveTrust("declared", t.spread_declared, None)
    return PreviewOut(nutrition=_block(result, effective), checks=[Check(rule=f.rule, message=f.message) for f in flags],
                      licence_cleared=not result.uncleared_sources,
                      can_publish=not flags and not result.uncleared_sources)


# ------------------------------------------------------------------ recipes

async def _recipe_out(session: AsyncSession, r: Recipe) -> RecipeOut:
    vs = await repository.versions(session, r.business_id, r.id)
    pub = next((v for v in reversed(vs) if v.status == "published"), None)
    items = await repository.items_following(session, r.business_id, r.id)
    return RecipeOut(id=r.id, name=r.name, is_sub_recipe=r.is_sub_recipe, scope="branch" if r.branch_id else "brand",
                     branch_id=r.branch_id, overrides_recipe_id=r.overrides_recipe_id,
                     latest_version=vs[-1].version_number if vs else None, latest_status=vs[-1].status if vs else None,
                     published_version_id=pub.id if pub else None, used_by_items=len(items))


async def create_recipe(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, body: RecipeIn) -> RecipeOut:
    await businesses.require(session, user_id, business_id, "edit_recipes")
    from app.services.businesses import repository as biz_repo
    brand = await biz_repo.default_brand(session, business_id)
    r = await repository.add(session, Recipe(business_id=business_id, brand_id=brand.id if brand else None,
                                             name=body.name, is_sub_recipe=body.is_sub_recipe))
    return await _recipe_out(session, r)


async def list_recipes(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID) -> list[RecipeOut]:
    await businesses.require(session, user_id, business_id)
    return [await _recipe_out(session, r) for r in await repository.recipes(session, business_id)]


async def _recipe_checked(session, user_id, business_id, recipe_id, permission="view") -> Recipe:
    await businesses.require(session, user_id, business_id, permission)
    r = await repository.recipe(session, business_id, recipe_id)
    if r is None:
        raise NotFound("Recipe not found")
    return r


async def get_recipe(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, recipe_id: uuid.UUID) -> RecipeOut:
    return await _recipe_out(session, await _recipe_checked(session, user_id, business_id, recipe_id))


async def _version_out(session: AsyncSession, v: RecipeVersion) -> VersionOut:
    lines = await repository.lines(session, v.id)
    names = {i.id: i.name for i in (await repository.ingredients(session, [l.ingredient_id for l in lines if l.ingredient_id])).values()}
    sub_versions = await nutrition.repository.versions(session, [l.sub_recipe_version_id for l in lines if l.sub_recipe_version_id])
    sub_recipes = {vid: await repository.recipe(session, v.business_id, v.recipe_id) for vid, v in sub_versions.items()}
    out_lines = [LineOut(ingredient_id=l.ingredient_id, sub_recipe_version_id=l.sub_recipe_version_id,
                         sub_recipe_id=sub_recipes[l.sub_recipe_version_id].id if l.sub_recipe_version_id else None,
                         name=names.get(l.ingredient_id) or (f"{sub_recipes[l.sub_recipe_version_id].name} "
                                                             f"(v{sub_versions[l.sub_recipe_version_id].version_number})"
                                                             if l.sub_recipe_version_id else "?"),
                         quantity_g=l.quantity_g,
                         entered_quantity=l.entered_quantity, entered_unit=l.entered_unit, oil_retained_g=l.oil_retained_g)
                 for l in lines]
    items = await repository.items_following(session, v.business_id, v.recipe_id)
    servings = await repository.servings(session, v.business_id, [i.id for i in items])
    result = _calc(await nutrition.version_recipe_data(session, v.id), servings[0].weight_g if servings else None)
    effective = (await trust.effective_for_version(session, v.id) if v.status == "published"
                 else rules.EffectiveTrust("declared", trust.thresholds().spread_declared, "Not published"))
    checks = [Check(id=f["id"], rule=f["rule"], message=f["message"] or f["rule"], resolution=f["resolution"],
                    resolution_note=f["resolution_note"]) for f in await trust.flags_for(session, v.id)]
    return VersionOut(id=v.id, recipe_id=v.recipe_id, version_number=v.version_number, status=v.status,
                      cooking_method=v.cooking_method, cooked_yield_g=v.cooked_yield_g,
                      servings_per_batch=v.servings_per_batch, declared_at=v.declared_at, lines=out_lines,
                      checks=checks, nutrition=_block(result, effective))


async def list_versions(session, user_id, business_id, recipe_id) -> list[VersionOut]:
    r = await _recipe_checked(session, user_id, business_id, recipe_id)
    return [await _version_out(session, v) for v in await repository.versions(session, business_id, r.id)]


async def create_version(session: AsyncSession, user_id: uuid.UUID | None, business_id: uuid.UUID, recipe: Recipe,
                         body: VersionIn) -> VersionOut:
    """Creates a new immutable version. Published if every check passes; otherwise held for admin review."""
    eng_lines, stored = await _resolve(session, business_id, body.lines, recipe.id)
    engine_recipe = engine.RecipeData(id="new", name=recipe.name, lines=tuple(eng_lines),
                                      cooked_yield_g=body.cooked_yield_g, cooking_method=body.cooking_method)
    result = _calc(engine_recipe, None)
    band, weights = await _context(session, business_id, recipe.id, None)
    previous = await repository.latest_published(session, business_id, recipe.id)
    prev_e100 = None
    if previous:
        prev_e100 = _calc(await nutrition.version_recipe_data(session, previous.id), None).per_100g["energy_kcal"]
    flags = trust.check(result, band, weights, prev_e100) + _licence_flag(result)
    status = "held" if flags else "published"

    v = await repository.add(session, RecipeVersion(
        business_id=business_id, recipe_id=recipe.id, version_number=await repository.next_version_number(session, recipe.id),
        cooking_method=body.cooking_method, cooked_yield_g=body.cooked_yield_g, servings_per_batch=body.servings_per_batch,
        status=status, declared_by=user_id, declared_at=datetime.now(UTC)))
    for s in stored:
        s.pop("name")
        session.add(RecipeIngredient(business_id=business_id, recipe_version_id=v.id, **s))
    await session.flush()
    if flags:
        await trust.record_flags(session, v.id, flags)
    else:
        await publish_version(session, business_id, recipe, v)
    await events.audit(session, user_id, "recipe_version_created", "recipe_version", str(v.id), status=status)
    return await _version_out(session, v)


async def publish_version(session: AsyncSession, business_id: uuid.UUID, recipe: Recipe, v: RecipeVersion) -> None:
    """Restaurant-declared label; every menu item following this recipe moves to the new version.
    Older versions stay stored and linked to diary entries that used them. Also used by admin approval."""
    await trust.record_declared(session, v.id)
    for item in await repository.items_following(session, business_id, recipe.id):
        item.current_recipe_version_id = v.id
        await _store_item_results(session, business_id, item.id, v.id)


async def _store_item_results(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID, version_id: uuid.UUID):
    data = await nutrition.version_recipe_data(session, version_id)
    effective = await trust.effective_for_version(session, version_id)
    for s in await repository.servings(session, business_id, [item_id]):
        result = _calc(data, s.weight_g)
        e = result.per_serving["energy_kcal"]
        mode = rules.display_mode(e * (1 - effective.spread), e * (1 + effective.spread), trust.thresholds()) if e else None
        await nutrition.store_result(session, result, version_id=version_id, serving_option_id=s.id,
                                     spread=effective.spread, display_mode=mode)


async def new_version(session, user_id, business_id, recipe_id, body: VersionIn) -> VersionOut:
    r = await _recipe_checked(session, user_id, business_id, recipe_id, "edit_recipes")
    return await create_version(session, user_id, business_id, r, body)


async def new_version_by_recipe(session, user_id, recipe_id, body: VersionIn) -> VersionOut:
    """POST /recipes/{id}/versions: the business is found from the recipe; non-members get 404."""
    r = await repository.recipe_for_member(session, recipe_id, user_id)
    if r is None:
        raise NotFound("Recipe not found")
    await businesses.require(session, user_id, r.business_id, "edit_recipes")
    return await create_version(session, user_id, r.business_id, r, body)


async def override_for_branch(session, user_id, business_id, recipe_id, branch_id) -> RecipeOut:
    """A branch override creates a branch-owned recipe; the brand recipe and other branches are unchanged."""
    brand_recipe = await _recipe_checked(session, user_id, business_id, recipe_id, "edit_recipes")
    if brand_recipe.branch_id is not None:
        raise AppError(422, "already_branch", "This is already a branch recipe.")
    branch = await businesses.branch_for_business(session, business_id, branch_id)
    source = await repository.latest_published(session, business_id, recipe_id)
    if source is None:
        raise AppError(422, "nothing_to_override", "Publish the brand recipe before overriding it.")
    override = await repository.add(session, Recipe(
        business_id=business_id, brand_id=brand_recipe.brand_id, branch_id=branch.id, overrides_recipe_id=recipe_id,
        name=f"{brand_recipe.name} ({branch.name})", is_sub_recipe=brand_recipe.is_sub_recipe))
    lines = await repository.lines(session, source.id)
    copy = VersionIn(cooking_method=source.cooking_method, cooked_yield_g=source.cooked_yield_g,
                     servings_per_batch=source.servings_per_batch, lines=[
                         LineIn(ingredient_id=l.ingredient_id, quantity=l.quantity_g, unit="g", oil_retained_g=l.oil_retained_g)
                         if l.ingredient_id else
                         LineIn(sub_recipe_id=(await nutrition.repository.version(session, l.sub_recipe_version_id)).recipe_id,
                                quantity=l.quantity_g, unit="g")
                         for l in lines])
    for item in await repository.items_following(session, business_id, recipe_id, branch.id):
        item.recipe_id = override.id
    await create_version(session, user_id, business_id, override, copy)
    await events.audit(session, user_id, "branch_override_created", "recipe", str(override.id), branch=str(branch.id))
    return await _recipe_out(session, override)


async def reconfirm(session: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID) -> datetime:
    item = await repository.item_for_member(session, item_id, user_id)
    if item is None:
        raise NotFound("Menu item not found")
    await businesses.require(session, user_id, item.business_id, "edit_recipes")
    if item.current_recipe_version_id is None:
        raise AppError(422, "no_recipe", "This dish has no published recipe to reconfirm.")
    expires = await trust.reconfirm(session, item.current_recipe_version_id)
    await events.audit(session, user_id, "recipe_reconfirmed", "menu_item", str(item.id))
    return expires


# ------------------------------------------------------------------ servings and modifiers

async def _item_checked(session, user_id, business_id, item_id, permission="view"):
    await businesses.require(session, user_id, business_id, permission)
    item = await repository.item(session, business_id, item_id)
    if item is None:
        raise NotFound("Menu item not found")
    return item


async def list_servings(session, user_id, business_id, item_id) -> list[ServingOut]:
    item = await _item_checked(session, user_id, business_id, item_id)
    return [ServingOut(id=s.id, label=s.label, weight_g=s.weight_g, unit=s.unit, is_default=s.is_default)
            for s in await repository.servings(session, business_id, [item.id])]


async def add_serving(session, user_id, business_id, item_id, body: ServingIn) -> ServingOut:
    from app.services.search.service import clear_cache
    clear_cache()
    item = await _item_checked(session, user_id, business_id, item_id, "edit_recipes")
    existing = await repository.servings(session, business_id, [item.id])
    if body.is_default or not existing:
        for s in existing:
            s.is_default = False
    s = await repository.add(session, ServingOption(business_id=business_id, menu_item_id=item.id, label=body.label,
                                                    weight_g=body.weight_g, unit=body.unit,
                                                    is_default=body.is_default or not existing))
    if item.current_recipe_version_id:
        await _store_item_results(session, business_id, item.id, item.current_recipe_version_id)
    return ServingOut(id=s.id, label=s.label, weight_g=s.weight_g, unit=s.unit, is_default=s.is_default)


async def delete_serving(session, user_id, business_id, serving_id) -> None:
    from app.services.search.service import clear_cache
    clear_cache()
    await businesses.require(session, user_id, business_id, "edit_recipes")
    s = await repository.serving(session, business_id, serving_id)
    if s is None:
        raise NotFound("Serving not found")
    await repository.delete(session, s)


def _modifier_out(m: Modifier, energy_change: str | None = None) -> ModifierOut:
    spec = m.spec or {}
    return ModifierOut(id=m.id, label=m.label, kind=m.kind, deltas=spec.get("deltas", []),
                       cooking_method=spec.get("cooking_method"), oil_retained_g=spec.get("oil_retained_g"),
                       cooked_yield_g=spec.get("cooked_yield_g"), energy_change_display=energy_change)


async def to_engine_modifiers(session: AsyncSession, business_id: uuid.UUID, modifier_ids: list[uuid.UUID]) -> list[engine.Modifier]:
    mods = [await repository.modifier(session, business_id, mid) for mid in modifier_ids]
    if any(m is None for m in mods):
        raise AppError(422, "modifier_unknown", "One of those options isn't available for this dish.")
    groups = {g.id: g for g in [await repository.group(session, business_id, m.group_id) for m in mods]}
    ing_ids = [uuid.UUID(str(d["ingredient_id"])) for m in mods for d in (m.spec or {}).get("deltas", [])]
    ings = await ingredients.engine_inputs(session, ing_ids)
    return [engine.Modifier(
        id=str(m.id), group_id=str(m.group_id), exclusive=groups[m.group_id].exclusive, kind=m.kind,
        deltas=tuple(engine.Delta(ings[str(d["ingredient_id"])], d["delta_g"]) for d in (m.spec or {}).get("deltas", [])),
        cooking_method=(m.spec or {}).get("cooking_method"), oil_retained_g=(m.spec or {}).get("oil_retained_g"),
        cooked_yield_g=(m.spec or {}).get("cooked_yield_g")) for m in mods]


async def list_groups(session, user_id, business_id, item_id) -> list[ModifierGroupOut]:
    item = await _item_checked(session, user_id, business_id, item_id)
    groups = await repository.groups(session, business_id, item.id)
    mods = await repository.modifiers(session, business_id, [g.id for g in groups])
    servings = await repository.servings(session, business_id, [item.id])
    base = data = None
    if item.current_recipe_version_id and servings:
        data = await nutrition.version_recipe_data(session, item.current_recipe_version_id)
        base = _calc(data, servings[0].weight_g).per_serving["energy_kcal"]
    out = []
    for g in groups:
        outs = []
        for m in [m for m in mods if m.group_id == g.id]:
            change = None
            if data is not None and base is not None:
                try:
                    em = await to_engine_modifiers(session, business_id, [m.id])
                    e = engine.calculate(data, servings[0].weight_g, modifiers=em).per_serving["energy_kcal"]
                    if e is not None:
                        diff = round((e - base) / 10) * 10
                        change = f"{'+' if diff > 0 else ''}{diff} kcal" if diff else "about the same"
                except engine.EngineError:
                    change = None
            outs.append(_modifier_out(m, change))
        out.append(ModifierGroupOut(id=g.id, name=g.name, exclusive=g.exclusive, modifiers=outs))
    return out


async def add_group(session, user_id, business_id, item_id, body: ModifierGroupIn) -> ModifierGroupOut:
    item = await _item_checked(session, user_id, business_id, item_id, "edit_recipes")
    g = await repository.add(session, ModifierGroup(business_id=business_id, menu_item_id=item.id, name=body.name,
                                                    exclusive=body.exclusive))
    return ModifierGroupOut(id=g.id, name=g.name, exclusive=g.exclusive, modifiers=[])


async def add_modifier(session, user_id, business_id, group_id, body: ModifierIn) -> ModifierOut:
    await businesses.require(session, user_id, business_id, "edit_recipes")
    g = await repository.group(session, business_id, group_id)
    if g is None:
        raise NotFound("Option group not found")
    if body.kind == "delta":
        found = await repository.ingredients(session, [d.ingredient_id for d in body.deltas])
        if len(found) != len({d.ingredient_id for d in body.deltas}):
            raise AppError(422, "ingredient_unknown", "One of the ingredients no longer exists.")
        spec = {"deltas": [{"ingredient_id": str(d.ingredient_id), "delta_g": d.delta_g} for d in body.deltas]}
    else:
        spec = {"cooking_method": body.cooking_method, "oil_retained_g": body.oil_retained_g,
                "cooked_yield_g": body.cooked_yield_g}
    m = await repository.add(session, Modifier(business_id=business_id, group_id=g.id, label=body.label,
                                               kind=body.kind, spec=spec))
    return _modifier_out(m)


async def delete_modifier(session, user_id, business_id, modifier_id) -> None:
    await businesses.require(session, user_id, business_id, "edit_recipes")
    m = await repository.modifier(session, business_id, modifier_id)
    if m is None:
        raise NotFound("Option not found")
    await repository.delete(session, m)
