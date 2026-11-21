"""Menus, categories, menu items, imports, the dashboard summary, and per-item nutrition display."""
import csv
import io
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.errors import AppError, NotFound
from app.models.business import Branch
from app.models.menus import Menu, MenuCategory, MenuImport, MenuItem
from app.services.businesses import service as businesses
from app.services.menus import repository
from app.services.menus.schemas import (CategoryIn, CategoryOut, ConfirmOut, DashboardOut, ImportOut, ImportRow,
                                        ImportUpdate, ItemIn, ItemNutrition, ItemOut, ItemUpdate, MenuOut)
from app.services.nutrition import engine
from app.services.nutrition import service as nutrition
from app.services.ontology import service as ontology
from app.services.trust import rules
from app.services.trust import service as trust

DIET_WORDS = {"veg": "veg", "vegetarian": "veg", "v": "veg", "egg": "egg", "eggetarian": "egg",
              "non-veg": "non_veg", "nonveg": "non_veg", "non veg": "non_veg", "non_veg": "non_veg", "nv": "non_veg"}


# ------------------------------------------------------------------ nutrition shown for one menu item

async def item_nutrition(session: AsyncSession, item: MenuItem, branch: Branch) -> ItemNutrition:
    """Declared (outlet recipe) > Estimated (reference recipe for this dish and region) > No data.
    One outlet's recipe is never used for another outlet's dish (fixed rule 7)."""
    t = trust.thresholds()
    if item.current_recipe_version_id:
        from app.services.recipes import repository as recipes_repo
        servings = await recipes_repo.servings(session, item.business_id, [item.id])
        serving = servings[0] if servings else None
        data = await nutrition.version_recipe_data(session, item.current_recipe_version_id)
        try:
            result = engine.calculate(data, serving.weight_g if serving else None, require_cleared=True)
        except engine.EngineError:
            result = None
        if result is not None:
            effective = await trust.effective_for_version(session, item.current_recipe_version_id)
            values = result.per_serving if result.per_serving is not None else result.per_100g
            from app.services.aggregates import service as aggregates
            steps = await aggregates.heavier_steps(session, item.id, item.current_recipe_version_id)
            high = rules.widened_high_spread(effective.label, effective.spread, steps, t) if steps else None
            shown = rules.display_nutrients(values, effective, t, high_spread=high)
            n = shown["nutrients"]
            return ItemNutrition(trust={"label": effective.label, "note": effective.note}, display_mode=shown["display_mode"],
                                 energy=n["energy_kcal"], protein=n["protein_g"], carbs=n["carbs_g"], fat=n["fat_g"],
                                 serving_label=f"{serving.label} ({serving.weight_g:.0f} g)" if serving else "per 100 g",
                                 allergens=rules.allergen_display(effective.label, result.allergens))
    ref = await nutrition.reference_for(session, item.canonical_dish_id, branch.region)
    if ref is not None:
        try:
            est = await nutrition.estimated_nutrition(session, ref.id, require_cleared=True)
            n = est.nutrients
            dump = lambda v: v.model_dump() if v else None  # noqa: E731
            return ItemNutrition(trust=est.trust, display_mode=est.display_mode, energy=dump(n["energy_kcal"]),
                                 protein=dump(n["protein_g"]), carbs=dump(n["carbs_g"]), fat=dump(n["fat_g"]),
                                 serving_label=f"typical serving ({est.serving_weight_g:.0f} g)" if est.serving_weight_g else "per 100 g",
                                 allergens=est.allergens)
        except AppError:
            pass  # reference data not cleared for publication: fall through to No data
    return ItemNutrition(trust={"label": "no_data", "note": None}, display_mode=None, energy=None, protein=None,
                         carbs=None, fat=None, serving_label=None, allergens=rules.allergen_display("no_data", ()))


async def _items_out(session: AsyncSession, items: list[MenuItem], branch: Branch) -> list[ItemOut]:
    dishes = await repository.dish_names(session, [i.canonical_dish_id for i in items if i.canonical_dish_id])
    recipes = await repository.recipe_names(session, [i.recipe_id for i in items if i.recipe_id])
    return [ItemOut(id=i.id, branch_id=i.branch_id, category_id=i.category_id, display_name=i.display_name,
                    description=i.description, price_inr=float(i.price_inr) if i.price_inr is not None else None,
                    diet_class=i.diet_class, status=i.status, diet_tags=i.diet_tags or [], canonical_dish_id=i.canonical_dish_id,
                    canonical_dish_name=dishes.get(i.canonical_dish_id), recipe_id=i.recipe_id,
                    recipe_name=recipes.get(i.recipe_id), current_recipe_version_id=i.current_recipe_version_id,
                    nutrition=await item_nutrition(session, i, branch)) for i in items]


# ------------------------------------------------------------------ menus

async def _menu(session: AsyncSession, business_id: uuid.UUID, branch_id: uuid.UUID) -> Menu:
    menu = await repository.menu_for_branch(session, business_id, branch_id)
    if menu is None:
        menu = await repository.add(session, Menu(business_id=business_id, branch_id=branch_id, name="Menu"))
    return menu


async def get_menu(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, branch_id: uuid.UUID) -> MenuOut:
    await businesses.require(session, user_id, business_id)
    branch = await businesses.branch_for_business(session, business_id, branch_id)
    return await menu_out(session, business_id, branch)


async def menu_out(session: AsyncSession, business_id: uuid.UUID, branch: Branch, published_only: bool = False) -> MenuOut:
    menu = await _menu(session, business_id, branch.id)
    cats = await repository.categories(session, business_id, menu.id)
    items = await _items_out(session, await repository.items_for_branch(session, business_id, branch.id, published_only), branch)
    cat_ids = {c.id for c in cats}
    return MenuOut(id=menu.id, branch_id=branch.id, name=menu.name,
                   categories=[CategoryOut(id=c.id, name=c.name, position=c.position,
                                           items=[i for i in items if i.category_id == c.id]) for c in cats],
                   uncategorised=[i for i in items if i.category_id not in cat_ids])


async def add_category(session, user_id, business_id, branch_id, body: CategoryIn) -> CategoryOut:
    await businesses.require(session, user_id, business_id, "edit_menu")
    await businesses.branch_for_business(session, business_id, branch_id)
    menu = await _menu(session, business_id, branch_id)
    c = await repository.add(session, MenuCategory(business_id=business_id, menu_id=menu.id, name=body.name,
                                                   position=body.position))
    return CategoryOut(id=c.id, name=c.name, position=c.position, items=[])


DIET_TAGS = {"jain", "no_onion_garlic", "vrat", "halal"}


async def _check_links(session, business_id, branch_id, category_id, recipe_id, dish_id=None, tags=()):
    if set(tags) - DIET_TAGS:
        raise AppError(422, "diet_tag_unknown", "Diet tags can be: jain, no_onion_garlic, vrat, halal.")
    if dish_id and not await repository.dish_names(session, [dish_id]):
        raise AppError(422, "dish_unknown", "That dish isn't in the catalogue.")
    if category_id:
        c = await repository.category(session, business_id, category_id)
        menu = await repository.menu_for_branch(session, business_id, branch_id)
        if c is None or menu is None or c.menu_id != menu.id:
            raise AppError(422, "category_unknown", "That category isn't on this branch's menu.")
    if recipe_id:
        r = await repository.recipe(session, business_id, recipe_id)
        if r is None or r.is_sub_recipe:
            raise AppError(422, "recipe_unknown", "Link a dish recipe from your own recipes (not a sub-recipe).")
        if r.branch_id and r.branch_id != branch_id:
            raise AppError(422, "recipe_other_branch", "That recipe is another branch's override.")


async def _follow(session, business_id, item: MenuItem) -> None:
    """Point the item at its recipe's latest published version."""
    from app.services.recipes import repository as recipes_repo
    if item.recipe_id is None:
        item.current_recipe_version_id = None
        return
    v = await recipes_repo.latest_published(session, business_id, item.recipe_id)
    item.current_recipe_version_id = v.id if v else None


async def add_item(session, user_id, business_id, body: ItemIn) -> ItemOut:
    await businesses.require(session, user_id, business_id, "edit_menu")
    branch = await businesses.branch_for_business(session, business_id, body.branch_id)
    await _check_links(session, business_id, branch.id, body.category_id, body.recipe_id, body.canonical_dish_id, body.diet_tags)
    item = await repository.add(session, MenuItem(business_id=business_id, branch_id=branch.id, status="draft",
                                                  **body.model_dump(exclude={"branch_id"})))
    await _follow(session, business_id, item)
    return (await _items_out(session, [item], branch))[0]


async def update_item(session, user_id, business_id, item_id, body: ItemUpdate) -> ItemOut:
    await businesses.require(session, user_id, business_id, "edit_menu")
    item = await repository.item(session, business_id, item_id)
    if item is None:
        raise NotFound("Menu item not found")
    branch = await businesses.branch_for_business(session, business_id, item.branch_id)
    await _check_links(session, business_id, branch.id, body.category_id, body.recipe_id, body.canonical_dish_id, body.diet_tags)
    relink = body.recipe_id != item.recipe_id
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    if relink:
        await _follow(session, business_id, item)
    return (await _items_out(session, [item], branch))[0]


async def delete_item(session, user_id, business_id, item_id) -> None:
    """Soft delete: old diary entries still resolve."""
    await businesses.require(session, user_id, business_id, "edit_menu")
    item = await repository.item(session, business_id, item_id)
    if item is None:
        raise NotFound("Menu item not found")
    item.deleted_at = datetime.now(UTC)


# ------------------------------------------------------------------ imports (nothing is published from an import)

def _parse_csv(data: bytes) -> list[dict]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise AppError(422, "csv_empty", "The CSV has no header row.")
    cols = {f.strip().lower(): f for f in reader.fieldnames if f}
    name_col = next((cols[c] for c in ("name", "dish", "item", "dish name", "item name") if c in cols), None)
    if name_col is None:
        raise AppError(422, "csv_no_name", "The CSV needs a 'name' column. Optional: price, category, diet, description.")
    pick = lambda row, *keys: next((row[cols[k]].strip() for k in keys if k in cols and row.get(cols[k])), None)  # noqa: E731
    rows = []
    for row in reader:
        name = (row.get(name_col) or "").strip()
        if not name:
            continue
        price = pick(row, "price", "price_inr", "rate", "mrp")
        try:
            price_val = float(price.replace("₹", "").replace(",", "")) if price else None
        except ValueError:
            price_val = None
        diet = (pick(row, "diet", "type", "veg/non-veg") or "").lower()
        rows.append({"name": name[:256], "price_inr": price_val, "category": (pick(row, "category", "section") or None),
                     "diet_class": DIET_WORDS.get(diet), "description": pick(row, "description", "desc")})
        if len(rows) >= 500:
            break
    return rows


def _import_out(imp: MenuImport) -> ImportOut:
    ex = imp.extraction_result or {}
    status = "confirmed" if imp.review_status == "reviewed" else ex.get("status", "ready")
    return ImportOut(id=imp.id, branch_id=imp.branch_id, file_type=imp.file_type, review_status=imp.review_status,
                     status=status, message=ex.get("message"), rows=[ImportRow(**r) for r in ex.get("rows", [])])


async def create_import(session, user_id, business_id, branch_id, filename: str, content_type: str, data: bytes) -> ImportOut:
    await businesses.require(session, user_id, business_id, "edit_menu")
    await businesses.branch_for_business(session, business_id, branch_id)
    if (content_type or "").startswith("application/vnd.ms-excel") or (filename or "").lower().endswith(".csv"):
        content_type = "text/csv"
    try:
        ext = storage.validate(content_type, data)
        path = await storage.put_private(data, ext)
    except storage.StorageError as e:
        raise AppError(422, "upload_invalid", str(e)) from e
    from app.services.ai import service as ai
    ai_ok, _ = (False, None) if ext == ".csv" else await ai.available(session)
    rows = None
    if ext == ".csv":
        rows = _parse_csv(data)
    elif ai_ok:
        media = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".pdf": "application/pdf"}[ext]
        try:
            rows = await ai.extract_menu(session, user_id, data, media)
        except Exception:  # provider trouble: keep the file, ask for a CSV or manual entry
            rows = None
    if rows is not None:
        for r in rows:
            match = await ontology.best_match(session, r["name"])
            if match:
                r["canonical_dish_id"], r["canonical_dish_name"] = str(match.id), match.name
        source = "csv" if ext == ".csv" else "ai"
        note = "" if source == "csv" else " These were read automatically, so check names and prices carefully."
        result = {"status": "ready", "rows": rows, "source": source,
                  "message": f"Found {len(rows)} dishes.{note} Check each row, then confirm to add them as drafts."}
    else:
        # Photo and PDF reading needs the AI provider, which is not configured yet (open owner decision).
        result = {"status": "needs_ai", "rows": [], "source": ext.lstrip("."),
                  "message": "Reading photos and PDFs automatically isn't switched on yet. "
                             "Upload a CSV, or add dishes by hand."}
    imp = await repository.add(session, MenuImport(business_id=business_id, branch_id=branch_id, file_path=path,
                                                   file_type=ext.lstrip("."), extraction_result=result))
    return _import_out(imp)


async def _import_checked(session, user_id, business_id, import_id) -> MenuImport:
    await businesses.require(session, user_id, business_id, "edit_menu")
    imp = await repository.import_(session, business_id, import_id)
    if imp is None:
        raise NotFound("Import not found")
    return imp


async def get_import(session, user_id, business_id, import_id) -> ImportOut:
    return _import_out(await _import_checked(session, user_id, business_id, import_id))


async def update_import(session, user_id, business_id, import_id, body: ImportUpdate) -> ImportOut:
    imp = await _import_checked(session, user_id, business_id, import_id)
    if imp.review_status != "pending":
        raise AppError(409, "import_closed", "This import has already been confirmed.")
    imp.extraction_result = {**(imp.extraction_result or {}), "rows": [r.model_dump(mode="json") for r in body.rows]}
    return _import_out(imp)


async def confirm_import(session, user_id, business_id, import_id) -> ConfirmOut:
    """Creates draft menu items. Nothing is published from an import alone."""
    imp = await _import_checked(session, user_id, business_id, import_id)
    if imp.review_status != "pending":
        raise AppError(409, "import_closed", "This import has already been confirmed.")
    menu = await _menu(session, business_id, imp.branch_id)
    cats = {c.name.lower(): c for c in await repository.categories(session, business_id, menu.id)}
    created = 0
    for row in [ImportRow(**r) for r in (imp.extraction_result or {}).get("rows", [])]:
        if not row.include:
            continue
        cat = None
        if row.category:
            cat = cats.get(row.category.lower())
            if cat is None:
                cat = await repository.add(session, MenuCategory(business_id=business_id, menu_id=menu.id,
                                                                 name=row.category, position=len(cats)))
                cats[row.category.lower()] = cat
        await repository.add(session, MenuItem(
            business_id=business_id, branch_id=imp.branch_id, category_id=cat.id if cat else None,
            display_name=row.name, description=row.description, price_inr=row.price_inr, diet_class=row.diet_class,
            canonical_dish_id=row.canonical_dish_id, status="draft"))
        created += 1
    imp.review_status = "reviewed"
    return ConfirmOut(created=created)


# ------------------------------------------------------------------ dashboard

async def dashboard(session, user_id, business_id) -> DashboardOut:
    await businesses.require(session, user_id, business_id)
    items = await repository.items_for_business(session, business_id)
    versions = await repository.versions_for_business(session, business_id)
    from app.services.businesses import repository as biz_repo
    branches = {b.id: b for b, _, _ in await biz_repo.branches(session, business_id)}
    with_data = 0
    for i in items:
        n = await item_nutrition(session, i, branches[i.branch_id]) if i.branch_id in branches else None
        if n and n.trust["label"] != "no_data":
            with_data += 1
    declared = sum(1 for i in items if i.current_recipe_version_id)
    return DashboardOut(
        menu_items=len(items), published_dishes=sum(1 for i in items if i.status == "published"),
        awaiting_recipes=sum(1 for i in items if not i.current_recipe_version_id), with_declared_recipe=declared,
        menu_completion_pct=round(100 * with_data / len(items)) if items else 0,
        recipes_expiring_soon=await trust.expiring_soon(session, list({i.current_recipe_version_id for i in items
                                                                       if i.current_recipe_version_id})),
        open_flags=await trust.open_flag_count(session, [v.id for v in versions]),
        held_versions=sum(1 for v in versions if v.status == "held"),
        most_viewed=[])  # dish views arrive with the consumer area (phase 5)
