"""Consumer discovery: preview, nearby restaurants, restaurant pages, search, dish pages and live calculation.

Every number comes from the engine; every filter and ranking decision is made here, never in the client.
"""
import base64
import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.errors import AppError, NotFound
from app.core.settings import get_settings
from app.models.business import Branch
from app.models.menus import MenuItem
from app.services.nutrition import engine
from app.services.nutrition import service as nutrition
from app.services.profile import service as profile
from app.services.profile.schemas import StatedFilters
from app.services.search import ranking, repository
from app.services.search.schemas import (Band, CalculateIn, Coverage, DishCard, DishNutritionOut, DishPage,
                                         ModifierGroupOpt, ModifierOpt, NearbyOut, PersonalLine, PreviewOut,
                                         PreviewRestaurant, RestaurantCard, RestaurantPage, SearchOut, Serving)
from app.services.trust import rules
from app.services.trust import service as trust

MEANING = {
    "verified": "Recipe and portion checked by an audit or lab test.",
    "declared": "Calculated from this outlet's own recipe.",
    "estimated": "Calculated from a typical recipe for this dish and region, not this outlet's own.",
    "no_data": "No recipe has been declared and no typical recipe matches.",
}


# ------------------------------------------------------------------ one dish, resolved

@dataclass
class Resolved:
    label: str
    note: str | None
    shown: dict | None            # rules.display_nutrients output
    values: dict | None           # eaten mids
    allergens: dict               # rules.allergen_display
    declared_allergens: tuple
    serving_id: uuid.UUID | None
    serving_label: str | None
    servings: list[Serving]
    recipe_version_id: uuid.UUID | None
    reference_id: uuid.UUID | None
    ingredients: list[str]
    updated_at: datetime | None


# Resolved nutrition per dish, kept briefly. Safe because recipe versions never change; anything that changes a
# label, a spread or reference data calls clear_cache(), and entries expire after CACHE_SECONDS regardless.
CACHE_SECONDS = 600   # all changes clear it explicitly; the timer only covers labels expiring by date
_cache: dict[tuple, tuple[float, "Resolved"]] = {}


def clear_cache() -> None:
    _cache.clear()


async def resolve(session: AsyncSession, item: MenuItem, branch: Branch, serving_id: uuid.UUID | None = None,
                  share: float = 1.0, modifier_ids: list[uuid.UUID] | tuple = ()) -> Resolved:
    import time
    key = (item.id, item.current_recipe_version_id, item.canonical_dish_id, branch.region, serving_id, share,
           tuple(sorted(str(m) for m in modifier_ids)))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    r = await _resolve(session, item, branch, serving_id, share, modifier_ids)
    if len(_cache) > 20000:
        _cache.clear()
    _cache[key] = (time.monotonic(), r)
    return r


async def _resolve(session: AsyncSession, item: MenuItem, branch: Branch, serving_id: uuid.UUID | None = None,
                   share: float = 1.0, modifier_ids: list[uuid.UUID] | tuple = ()) -> Resolved:
    """Declared recipe > Estimated reference for this dish and region > No data. Never another outlet's recipe."""
    t = trust.thresholds()
    from app.services.recipes import repository as recipes_repo
    from app.services.recipes import service as recipes
    if item.current_recipe_version_id:
        opts = await recipes_repo.servings(session, item.business_id, [item.id])
        chosen = next((o for o in opts if o.id == serving_id), None) if serving_id else (opts[0] if opts else None)
        if serving_id and chosen is None:
            raise AppError(422, "serving_unknown", "That serving isn't available for this dish.")
        mods = await recipes.to_engine_modifiers(session, item.business_id, list(modifier_ids)) if modifier_ids else []
        data = await nutrition.version_recipe_data(session, item.current_recipe_version_id)
        try:
            result = engine.calculate(data, chosen.weight_g if chosen else None, share if chosen else 1.0, mods,
                                      require_cleared=True)
        except engine.EngineError as e:
            if "not cleared" not in str(e):
                raise AppError(422, "calculation_invalid", str(e)) from e
            result = None
        if result is not None:
            effective = await trust.effective_for_version(session, item.current_recipe_version_id)
            values = result.eaten if result.eaten is not None else result.per_100g
            from app.services.aggregates import service as aggregates
            steps = await aggregates.heavier_steps(session, item.id, item.current_recipe_version_id)
            high = rules.widened_high_spread(effective.label, effective.spread, steps, t) if steps else None
            version = await nutrition.repository.version(session, item.current_recipe_version_id)
            recs = await trust.repository.records(session, item.current_recipe_version_id)
            updated = max([version.declared_at] + [r.verified_at for r in recs if r.verified_at])
            return Resolved(
                label=effective.label, note=effective.note,
                shown=rules.display_nutrients(values, effective, t, high_spread=high),
                values=values, allergens=rules.allergen_display(effective.label, result.allergens),
                declared_allergens=result.allergens, serving_id=chosen.id if chosen else None,
                serving_label=f"{chosen.label} ({chosen.weight_g:.0f} g)" if chosen else "per 100 g",
                servings=[Serving(id=o.id, label=o.label, weight_g=o.weight_g, selected=chosen is not None and o.id == chosen.id) for o in opts],
                recipe_version_id=item.current_recipe_version_id, reference_id=None,
                ingredients=[l.ingredient.name if l.ingredient else l.sub_recipe.name for l in data.lines],
                updated_at=updated)
    if modifier_ids:
        raise AppError(422, "modifiers_unavailable", "Options are only available for dishes with the restaurant's own recipe.")
    ref = await nutrition.reference_for(session, item.canonical_dish_id, branch.region)
    if ref is not None:
        try:
            res = await nutrition.calculate_reference(session, ref.id, share_fraction=share, require_cleared=True)
        except AppError:
            res = None
        if res is not None:
            effective = rules.effective_trust("estimated", t, datetime.now(), reference_spread=ref.spread)
            values = res.eaten if res.eaten is not None else res.per_100g
            data = await nutrition.reference_recipe_data(session, ref.id)
            label = f"Typical serving ({ref.serving_weight_g:.0f} g)" if ref.serving_weight_g else "per 100 g"
            return Resolved(
                label="estimated", note=None, shown=rules.display_nutrients(values, effective, t), values=values,
                allergens=rules.allergen_display("estimated", ()), declared_allergens=(), serving_id=None,
                serving_label=label, servings=[Serving(id=None, label=label, weight_g=ref.serving_weight_g, selected=True)],
                recipe_version_id=None, reference_id=ref.id,
                ingredients=[l.ingredient.name if l.ingredient else l.sub_recipe.name for l in data[1].lines], updated_at=None)
    return Resolved(label="no_data", note=None, shown=None, values=None, allergens=rules.allergen_display("no_data", ()),
                    declared_allergens=(), serving_id=None, serving_label=None, servings=[], recipe_version_id=None,
                    reference_id=None, ingredients=[], updated_at=None)


def _facts(item: MenuItem, r: Resolved, relevance: float = 1.0) -> ranking.Facts:
    n = (r.shown or {}).get("nutrients", {})
    e, p = n.get("energy_kcal"), n.get("protein_g")
    return ranking.Facts(
        diet_class=item.diet_class, diet_tags=frozenset(item.diet_tags or ()), label=r.label,
        allergen_status=r.allergens["status"], declared_allergens=frozenset(r.declared_allergens),
        energy_low=e["low"] if e else None, energy_high=e["high"] if e else None, protein_low=p["low"] if p else None,
        excluded_from_ranking=(r.shown or {}).get("excluded_from_ranking", True),
        price_inr=float(item.price_inr) if item.price_inr is not None else None, relevance=relevance)


# ------------------------------------------------------------------ the user's context

@dataclass
class Context:
    stated: StatedFilters
    rstated: ranking.Stated
    meal_budget_kcal: float | None
    meal_protein_g: float | None
    remaining_kcal: float | None
    weights: ranking.Weights


async def context(session: AsyncSession, user_id: uuid.UUID) -> Context:
    s = get_settings()
    st = await profile.stated(session, user_id)
    budget = protein = remaining = None
    if st.targets:
        from app.services.diary import service as diary
        eaten = await diary.eaten_today_kcal(session, user_id)
        remaining = st.targets.energy_kcal - eaten
        budget = max(0.0, min(st.targets.energy_kcal * s.MEAL_SHARE_OF_DAY, remaining))
        protein = st.targets.protein_g * s.MEAL_SHARE_OF_DAY
    return Context(stated=st, rstated=ranking.Stated(st.diet_type, frozenset(st.restrictions), frozenset(st.allergies)),
                   meal_budget_kcal=budget, meal_protein_g=protein, remaining_kcal=remaining,
                   weights=ranking.Weights(s.RANK_WEIGHT_CALORIE, s.RANK_WEIGHT_PROTEIN, s.RANK_WEIGHT_TRUST, s.RANK_WEIGHT_RELEVANCE))


def _fits_text(n: int) -> str:
    return "1 dish fits you" if n == 1 else f"{n} dishes fit you"


def _km(d: float | None) -> str | None:
    if d is None:
        return None
    return f"{round(d * 1000 / 50) * 50:.0f} m" if d < 1 else f"{d:.1f} km"


def _kcal_range(lo: float, hi: float) -> str:
    lo, hi = round(lo / 10) * 10, round(hi / 10) * 10
    return f"{lo:,} kcal" if lo == hi else f"{lo:,} to {hi:,} kcal"


def _card(item: MenuItem, branch: Branch, r: Resolved, ctx: Context, dist: float | None, ranked: bool) -> DishCard:
    n = (r.shown or {}).get("nutrients", {})
    f = _facts(item, r)
    warn = None
    if ranking.allergen_unknown_for(f, ctx.rstated):
        warn = "Allergen status unknown"
    return DishCard(id=item.id, name=item.display_name, restaurant_id=branch.id, restaurant_name=branch.name,
                    distance_display=_km(dist), price_inr=f.price_inr, diet_class=item.diet_class,
                    trust={"label": r.label, "note": r.note}, energy=n.get("energy_kcal"), protein=n.get("protein_g"),
                    fits=ranking.fits_budget(f, ctx.meal_budget_kcal) and ranked, allergen_warning=warn, ranked=ranked)


async def _branch_dishes(session: AsyncSession, branch: Branch, items: list[MenuItem], ctx: Context, dist: float | None,
                         relevance: dict | None = None):
    """Returns (ranked dish cards, other cards, facts for ranked)."""
    ranked, other = [], []
    for item in items:
        r = await resolve(session, item, branch)
        f = _facts(item, r, (relevance or {}).get(item.id, 1.0))
        if not ranking.passes_hard_filters(f, ctx.rstated):
            continue  # hard filters: never shown in results or rankings
        if ranking.rankable(f, ctx.rstated):
            ranked.append((ranking.score(f, ctx.meal_budget_kcal, ctx.meal_protein_g, ctx.weights), item, r, f))
        else:
            other.append(_card(item, branch, r, ctx, dist, False))
    ranked.sort(key=lambda x: -x[0])
    return [_card(i, branch, r, ctx, dist, True) for _, i, r, _ in ranked], other, [f for *_, f in ranked]


async def _typical_band(session: AsyncSession, branch: Branch, items: list[MenuItem]) -> Band | None:
    s = get_settings()
    stats = await repository.outlet_stats(session, branch.id)
    if (stats and stats.kcal_p25 is not None and stats.sample_meals >= s.OUTLET_BAND_MIN_MEALS
            and stats.sample_users >= s.OUTLET_BAND_MIN_USERS):
        return Band(display=_kcal_range(stats.kcal_p25, stats.kcal_p75),
                    label=f"what our users eat here, from {stats.sample_meals} meals", source="logged")
    cuisines = await repository.dish_cuisines(session, [i.canonical_dish_id for i in items if i.canonical_dish_id])
    mains, staples = [], []
    for i in items:
        r = await resolve(session, i, branch)   # served from the short cache filled by _branch_dishes
        e = (r.shown or {}).get("nutrients", {}).get("energy_kcal")
        if e:
            (staples if cuisines.get(i.canonical_dish_id) == "Staple" else mains).append(e)
    if not mains:
        return None
    lo = statistics.median(m["low"] for m in mains) + (statistics.median(x["low"] for x in staples) if staples else 0)
    hi = statistics.median(m["high"] for m in mains) + (statistics.median(x["high"] for x in staples) if staples else 0)
    return Band(display=_kcal_range(lo, hi), label="estimated from menu", source="modelled")


def _personal(ranked_facts: list, ctx: Context) -> PersonalLine | None:
    if ctx.meal_budget_kcal is None:
        return None
    fits = [f for f in ranked_facts if ranking.fits_budget(f, ctx.meal_budget_kcal)]
    budget = f"{round(ctx.meal_budget_kcal / 10) * 10:,.0f} kcal"
    if not fits:
        return PersonalLine(display=f"No dishes here fit your {budget} meal budget", fit_count=0)
    word = "dish fits" if len(fits) == 1 else "dishes fit"
    return PersonalLine(display=f"{len(fits)} {word} your {budget} meal budget: "
                                f"{_kcal_range(min(f.energy_low for f in fits), max(f.energy_high for f in fits))}",
                        fit_count=len(fits))


# ------------------------------------------------------------------ endpoints

async def preview_nearby(session: AsyncSession, lat: float, lng: float) -> PreviewOut:
    """For signed-in users without a subscription: names and counts only. Never any nutrition (fixed rule 17)."""
    s = get_settings()
    near = await repository.branches_near(session, lat, lng, s.DISCOVERY_RADIUS_KM)
    items = await repository.published_items(session, [b.id for b, _ in near])
    out, declared_restaurants = [], 0
    for b, d in near:
        mine = [i for i in items if i.branch_id == b.id]
        declared = sum(1 for i in mine if i.current_recipe_version_id)
        declared_restaurants += declared > 0
        if mine:
            out.append(PreviewRestaurant(id=b.id, name=b.name, distance_display=_km(d), dish_names=[i.display_name for i in mine][:12],
                                         declared_dishes=declared, total_dishes=len(mine)))
    minimum = s.COVERAGE_MIN_RESTAURANTS or 1
    word = "restaurant" if declared_restaurants == 1 else "restaurants"
    return PreviewOut(coverage=Coverage(declared_restaurants=declared_restaurants, radius_km=s.DISCOVERY_RADIUS_KM,
                                        display=f"{declared_restaurants} {word} with declared recipes within {s.DISCOVERY_RADIUS_KM:g} km",
                                        waitlist=declared_restaurants < minimum),
                      restaurants=out)


async def nearby(session: AsyncSession, user_id: uuid.UUID, lat: float, lng: float) -> NearbyOut:
    rate_limit.check(f"discover:{user_id}", limit=120, window_seconds=60)
    ctx = await context(session, user_id)
    near = await repository.branches_near(session, lat, lng, get_settings().DISCOVERY_RADIUS_KM)
    items = await repository.published_items(session, [b.id for b, _ in near])
    cards = []
    for b, d in near:
        mine = [i for i in items if i.branch_id == b.id]
        if not mine:
            continue
        ranked, _, facts = await _branch_dishes(session, b, mine, ctx, d)
        p = _personal(facts, ctx)
        cards.append((p.fit_count if p else 0, d, RestaurantCard(
            id=b.id, name=b.name, distance_km=round(d, 2), distance_display=_km(d), cost_for_one_inr=b.cost_for_one_inr,
            typical_meal=await _typical_band(session, b, mine), fit_count=p.fit_count if p else 0,
            fit_display=_fits_text(p.fit_count) if p else "Set your goal to see fits")))
    cards.sort(key=lambda c: (-c[0], c[1]))
    budget = f"{round(ctx.meal_budget_kcal / 10) * 10:,.0f} kcal per meal" if ctx.meal_budget_kcal is not None else None
    return NearbyOut(restaurants=[c for *_, c in cards], meal_budget_display=budget)


async def restaurant(session: AsyncSession, user_id: uuid.UUID, branch_id: uuid.UUID, lat: float | None, lng: float | None) -> RestaurantPage:
    rate_limit.check(f"discover:{user_id}", limit=120, window_seconds=60)
    b = await repository.branch(session, branch_id)
    if b is None:
        raise NotFound("Restaurant not found")
    ctx = await context(session, user_id)
    items = await repository.published_items(session, [b.id])
    dist = await repository.distance_km(session, b.id, lat, lng) if lat is not None and lng is not None else None
    ranked, other, facts = await _branch_dishes(session, b, items, ctx, dist)
    declared = sum(1 for i in items if i.current_recipe_version_id)
    stats = await repository.outlet_stats(session, b.id)
    s = get_settings()
    rec = None
    if stats and stats.recommend_rate is not None and stats.sample_users >= s.OUTLET_BAND_MIN_USERS:
        rec = f"{stats.recommend_rate:.0%} would recommend"
    return RestaurantPage(id=b.id, name=b.name, address=b.address, distance_display=_km(dist), cost_for_one_inr=b.cost_for_one_inr,
                          typical_meal=await _typical_band(session, b, items), personal=_personal(facts, ctx), recommend_rate=rec,
                          declared_share=f"{declared} of {len(items)} dishes have the restaurant's own recipe",
                          dishes=ranked, other_dishes=other)


def _cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _offset(cursor: str | None) -> int:
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor.encode()).decode())) if cursor else 0
    except Exception:
        return 0


async def search(session: AsyncSession, user_id: uuid.UUID, lat: float, lng: float, q: str | None, max_kcal: float | None,
                 min_protein: float | None, max_price: float | None, max_km: float | None, trust_labels: set[str],
                 limit: int, cursor: str | None) -> SearchOut:
    """One page at a time; there is no bulk export of nutrition."""
    rate_limit.check(f"discover:{user_id}", limit=120, window_seconds=60)
    s = get_settings()
    ctx = await context(session, user_id)
    radius = min(max_km or s.DISCOVERY_RADIUS_KM, 15.0)
    near = await repository.branches_near(session, lat, lng, radius)
    dist = {b.id: d for b, d in near}
    branches = {b.id: b for b, _ in near}
    relevance = await repository.text_matches(session, q.strip(), list(branches)) if q and q.strip() else None
    items = await repository.published_items(session, list(branches))
    if relevance is not None:
        items = [i for i in items if i.id in relevance]
    scored = []
    for item in items:
        b = branches[item.branch_id]
        r = await resolve(session, item, b)
        f = _facts(item, r, (relevance or {}).get(item.id, 1.0))
        if not ranking.passes_hard_filters(f, ctx.rstated):
            continue
        if trust_labels and r.label not in trust_labels:
            continue
        if max_price is not None and (f.price_inr is None or f.price_inr > max_price):
            continue
        if max_kcal is not None and (f.energy_high is None or f.energy_high > max_kcal):
            continue
        if min_protein is not None and (f.protein_low is None or f.protein_low < min_protein):
            continue
        ok = ranking.rankable(f, ctx.rstated)
        sc = ranking.score(f, ctx.meal_budget_kcal, ctx.meal_protein_g, ctx.weights) if ok else -1
        scored.append((ok, sc, dist[b.id], item, b, r))
    scored.sort(key=lambda x: (not x[0], -x[1], x[2]))
    start = _offset(cursor)
    if start:   # paging deep through results is how bulk copying looks
        from app.core import abuse
        await abuse.note_access(session, user_id, "search_page", f"{q}|{max_kcal}|{min_protein}|{max_price}|{start}")
    if start == 0:  # demand insights: rounded to about 1 km, never the exact location
        from app.services.events import service as events
        await events.track(session, "search", user_id, lat=round(lat, 2), lng=round(lng, 2), q=(q or "").strip().lower()[:64] or None,
                           max_kcal=max_kcal, min_protein=min_protein, max_price=max_price, diet=ctx.stated.diet_type,
                           results=len(scored))
    page = scored[start:start + limit]
    dishes = [_card(i, b, r, ctx, d, ok) for ok, _, d, i, b, r in page]
    rest_ids = []
    for *_, b, _ in scored:
        if b.id not in rest_ids:
            rest_ids.append(b.id)
    restaurants = [RestaurantCard(id=bid, name=branches[bid].name, distance_km=round(dist[bid], 2),
                                  distance_display=_km(dist[bid]), cost_for_one_inr=branches[bid].cost_for_one_inr,
                                  typical_meal=None, fit_count=sum(1 for ok, _, _, i, b, r in scored if b.id == bid and ok
                                                                   and ranking.fits_budget(_facts(i, r), ctx.meal_budget_kcal)),
                                  fit_display="") for bid in rest_ids[:10]] if start == 0 else []
    for c in restaurants:
        c.fit_display = _fits_text(c.fit_count)
    nxt = _cursor(start + limit) if start + limit < len(scored) else None
    return SearchOut(dishes=dishes, restaurants=restaurants, next_cursor=nxt)


async def _dish_nutrition(session: AsyncSession, item: MenuItem, r: Resolved, ctx: Context, share: float,
                          modifier_ids: list) -> DishNutritionOut:
    n = (r.shown or {}).get("nutrients") or {k: None for k in engine.NUTRIENTS}
    e, p = n.get("energy_kcal"), n.get("protein_g")
    fit = None
    if ctx.remaining_kcal is not None and e:
        remaining = round(max(ctx.remaining_kcal, 0) / 10) * 10
        fits = e["high"] <= ctx.remaining_kcal
        fit = {"fits": fits, "display": f"Fits your remaining {remaining:,} kcal today" if fits
               else f"More than your remaining {remaining:,} kcal today"}
    ppr = None
    if p and item.price_inr and float(item.price_inr) > 0:
        # Value for money describes the whole dish at its menu price, whatever share is being eaten.
        ppr = f"{round(p['low'] / share / float(item.price_inr) * 100):,} g protein per ₹100"
    return DishNutritionOut(trust={"label": r.label, "note": r.note, "meaning": MEANING[r.label]},
                            display_mode=(r.shown or {}).get("display_mode"), nutrients=n, serving_label=r.serving_label,
                            share_fraction=share, modifier_ids=list(modifier_ids), fit=fit, protein_per_100_inr=ppr,
                            excluded_from_ranking=(r.shown or {}).get("excluded_from_ranking", True))


async def _item_and_branch(session: AsyncSession, item_id: uuid.UUID) -> tuple[MenuItem, Branch]:
    item = await repository.published_item(session, item_id)
    b = await repository.branch(session, item.branch_id) if item else None
    if item is None or b is None:
        raise NotFound("Dish not found")
    return item, b


async def dish_page(session: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID) -> DishPage:
    rate_limit.check(f"dish:{user_id}", limit=120, window_seconds=60)
    item, b = await _item_and_branch(session, item_id)
    ctx = await context(session, user_id)
    r = await resolve(session, item, b)
    groups = []
    if item.current_recipe_version_id:
        from app.services.recipes import repository as recipes_repo
        gs = await recipes_repo.groups(session, item.business_id, item.id)
        mods = await recipes_repo.modifiers(session, item.business_id, [g.id for g in gs])
        groups = [ModifierGroupOpt(id=g.id, name=g.name, exclusive=g.exclusive,
                                   modifiers=[ModifierOpt(id=m.id, label=m.label) for m in mods if m.group_id == g.id]) for g in gs]
    conflict = sorted(set(r.declared_allergens) & ctx.stated.allergies)
    from app.core import abuse
    from app.services.events import service as events
    await abuse.note_access(session, user_id, "dish", str(item.id))
    await events.track(session, "dish_viewed", user_id, item_id=str(item.id))
    return DishPage(id=item.id, name=item.display_name, description=item.description,
                    price_inr=float(item.price_inr) if item.price_inr is not None else None, diet_class=item.diet_class,
                    diet_tags=item.diet_tags or [], restaurant_id=b.id, restaurant_name=b.name,
                    nutrition=await _dish_nutrition(session, item, r, ctx, 1.0, []), servings=r.servings,
                    modifier_groups=groups, ingredients=r.ingredients,
                    ingredients_label="Restaurant's recipe" if r.recipe_version_id else "Typical recipe for this dish",
                    allergens=r.allergens, allergy_conflict=conflict, last_updated=r.updated_at)


async def calculate(session: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID, body: CalculateIn) -> DishNutritionOut:
    rate_limit.check(f"dish:{user_id}", limit=120, window_seconds=60)
    if not 0 < body.share_fraction <= 1:
        raise AppError(422, "share_invalid", "Pick a share between a little and the whole serving.")
    item, b = await _item_and_branch(session, item_id)
    ctx = await context(session, user_id)
    r = await resolve(session, item, b, body.serving_option_id, body.share_fraction, body.modifier_ids)
    return await _dish_nutrition(session, item, r, ctx, body.share_fraction, body.modifier_ids)


async def join_waitlist(session: AsyncSession, user_id: uuid.UUID, area: str) -> None:
    from app.models.access import WaitlistEntry
    from app.services.users import service as users
    user = await users.get(session, user_id)
    session.add(WaitlistEntry(email=user.email, area=area.strip()))
    await session.flush()


# ------------------------------------------------------------------ healthier swaps

async def swaps(session: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID):
    """Built from this outlet's real options and dishes, filtered by the user's stated diet and allergies.
    For a weight-gain goal, swaps that add protein come first; otherwise swaps that cut energy."""
    from app.services.search.schemas import Swap, SwapsOut
    rate_limit.check(f"dish:{user_id}", limit=120, window_seconds=60)
    item, b = await _item_and_branch(session, item_id)
    ctx = await context(session, user_id)
    goal = (await profile.get(session, user_id)).goal
    base = await resolve(session, item, b)
    base_e = ((base.shown or {}).get("nutrients") or {}).get("energy_kcal")
    base_p = ((base.shown or {}).get("nutrients") or {}).get("protein_g")
    out: list[tuple[float, Swap]] = []

    if item.current_recipe_version_id and base_e:
        from app.services.recipes import repository as recipes_repo
        groups = await recipes_repo.groups(session, item.business_id, item.id)
        for m in await recipes_repo.modifiers(session, item.business_id, [g.id for g in groups]):
            try:
                r = await resolve(session, item, b, modifier_ids=[m.id])
            except AppError:
                continue
            n = (r.shown or {}).get("nutrients") or {}
            e, p = n.get("energy_kcal"), n.get("protein_g")
            if not e:
                continue
            if set(r.declared_allergens) & ctx.stated.allergies:
                continue   # an option that adds a declared allergen is never suggested
            saved = base_e["mid"] - e["mid"]
            gained = (p["mid"] - base_p["mid"]) if p and base_p else 0
            if goal == "gain" and gained >= 1:
                out.append((gained * 10, Swap(kind="option", title=m.label, modifier_id=m.id,
                                              display=f"About {round(gained):,} g more protein")))
            elif saved >= 20:
                out.append((saved, Swap(kind="option", title=m.label, modifier_id=m.id,
                                        display=f"About {round(saved / 10) * 10:,} kcal less")))

    if base_e:
        items = await repository.published_items(session, [b.id])
        for other in items:
            if other.id == item.id:
                continue
            r = await resolve(session, other, b)
            f = _facts(other, r)
            if not ranking.passes_hard_filters(f, ctx.rstated) or not ranking.rankable(f, ctx.rstated):
                continue
            protein_ok = base_p is None or (f.protein_low or 0) >= 0.8 * base_p["low"]
            if f.energy_high <= 0.85 * base_e["high"] and protein_ok:
                e = r.shown["nutrients"]["energy_kcal"]
                out.append((base_e["high"] - f.energy_high, Swap(kind="dish", title=other.display_name, dish_id=other.id,
                                                                 display=f"{e['display']} instead of {base_e['display']}")))
    out.sort(key=lambda x: -x[0])
    note = ("Options change how this dish is made; ask for them when you order." if any(s.kind == "option" for _, s in out)
            else "Lighter dishes here that still fit your filters.")
    return SwapsOut(swaps=[s for _, s in out[:4]], note=note if out else "No healthier swaps here for this dish.")
