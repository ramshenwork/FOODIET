"""Nightly statistics, learned preferences, the "heavier than expected" signal, and restaurant insights.

Restaurants see aggregate statistics only, and only above a minimum number of people (fixed rule 15).
Learned preferences are shown to the user and never override what they stated (fixed rule 10).
"""
import math
import statistics
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.models.activity import DishStats, OutletStats
from app.models.profile import LearnedPreference
from app.services.aggregates import repository
from app.services.aggregates.schemas import DemandInsight, DishInsight, InsightsOut


def _entry_energy(items) -> float | None:
    from app.services.diary.service import _item_nutrients
    total = 0.0
    for it in items:
        e = (_item_nutrients(it) or {}).get("energy_kcal")
        if e is None:
            return None
        total += e["mid"]
    return total


def _rate(yes: int, n: int) -> float | None:
    return yes / n if n else None


async def recompute(session: AsyncSession, now: datetime | None = None) -> dict:
    """Rebuild dish_stats and outlet_stats from diary entries, check-ins and views."""
    now = now or datetime.now(UTC)
    entries = await repository.entries_since(session, now - timedelta(days=180))
    items = await repository.items_for(session, [e.id for e in entries])
    checkins = {c.meal_entry_id: c for c in await repository.checkins_for(session, [e.id for e in entries])}
    by_entry = defaultdict(list)
    for it in items:
        by_entry[it.meal_entry_id].append(it)

    # Outlets: energy per person per meal (25th-75th percentile), recommend rate.
    outlet = defaultdict(lambda: {"kcal": [], "users": set(), "rec": [0, 0]})
    for e in entries:
        if e.branch_id is None:
            continue
        o = outlet[e.branch_id]
        kcal = _entry_energy(by_entry[e.id])
        if kcal is not None:
            o["kcal"].append(kcal)
        if e.user_id:
            o["users"].add(e.user_id)
        c = checkins.get(e.id)
        if c and c.recommend is not None:
            o["rec"][0] += c.recommend
            o["rec"][1] += 1
    for branch_id, o in outlet.items():
        st = await repository.outlet_stats(session, branch_id) or await repository.add(session, OutletStats(branch_id=branch_id))
        st.sample_meals, st.sample_users = len(o["kcal"]), len(o["users"])
        if len(o["kcal"]) >= 4:
            q = statistics.quantiles(o["kcal"], n=4)
            st.kcal_p25, st.kcal_p75 = q[0], q[2]
        st.recommend_rate, st.band_source, st.computed_at = _rate(*o["rec"]), "logged", now

    # Dishes: sample size, recommend rate, heavier-than-expected users on the current version, views.
    views = Counter(str((ev.properties or {}).get("item_id")) for ev in
                    await repository.events(session, "dish_viewed", now - timedelta(days=7)))
    entry_by_id = {e.id: e for e in entries}
    dish = defaultdict(lambda: {"meals": 0, "users": set(), "rec": [0, 0], "heavier": defaultdict(set)})
    for it in items:
        if it.menu_item_id is None:
            continue
        d, e = dish[it.menu_item_id], entry_by_id[it.meal_entry_id]
        d["meals"] += 1
        if e.user_id:
            d["users"].add(e.user_id)
        c = checkins.get(e.id)
        if c and c.recommend is not None:
            d["rec"][0] += c.recommend
            d["rec"][1] += 1
        if c and c.felt == "heavier" and e.user_id and it.recipe_version_id:
            d["heavier"][it.recipe_version_id].add(e.user_id)
    for item in await repository.all_items(session):
        d = dish.get(item.id)
        if d is None and not views.get(str(item.id)):
            continue
        st = await repository.dish_stats(session, item.id) or await repository.add(session, DishStats(menu_item_id=item.id))
        st.views_7d = views.get(str(item.id), 0)
        st.computed_at = now
        if d:
            st.sample_meals, st.sample_users, st.recommend_rate = d["meals"], len(d["users"]), _rate(*d["rec"])
            st.heavier_version_id = item.current_recipe_version_id
            st.heavier_users = len(d["heavier"].get(item.current_recipe_version_id, set()))
    learned = await recompute_learned(session)
    from app.services.search.service import clear_cache
    clear_cache()   # heavier-than-expected widening may have changed
    return {"outlets": len(outlet), "dishes": len(dish), "learned_users": learned}


async def heavier_steps(session: AsyncSession, item_id: uuid.UUID, version_id: uuid.UUID | None) -> int:
    """How many widening steps "heavier than expected" check-ins have earned for this dish's current version."""
    st = await repository.dish_stats(session, item_id)
    if st is None or version_id is None or st.heavier_version_id != version_id:
        return 0
    return st.heavier_users // max(get_settings().HEAVIER_USERS_PER_STEP, 1)


# ------------------------------------------------------------------ learned preferences

async def recompute_learned(session: AsyncSession) -> int:
    """Only for users who consented. A preference the user removed stays suppressed (weight -1)."""
    users = await repository.consented_users(session, "learned_preferences")
    if not users:
        return 0
    since = datetime.now(UTC) - timedelta(days=90)
    entries = [e for e in await repository.entries_since(session, since) if e.user_id in users]
    items = await repository.items_for(session, [e.id for e in entries])
    owner = {e.id: e.user_id for e in entries}
    dishes = await repository.dish_cuisine(session)
    per_user = defaultdict(lambda: {"cuisine": Counter(), "dish": Counter()})
    for it in items:
        u = owner[it.meal_entry_id]
        name, cuisine = dishes.get(it.menu_item_id, ((it.nutrition_snapshot or {}).get("name"), None))
        if cuisine:
            per_user[u]["cuisine"][cuisine] += 1
        if name:
            per_user[u]["dish"][name] += 1
    for u in users:
        suppressed = {(p.kind, p.value) for p in await repository.learned(session, u) if p.weight < 0}
        await repository.delete_learned(session, u)
        counts = per_user.get(u)
        if not counts:
            continue
        for kind in ("cuisine", "dish"):
            total = sum(counts[kind].values())
            for value, n in counts[kind].most_common(5):
                if (kind, value) not in suppressed and n >= 2:
                    session.add(LearnedPreference(user_id=u, kind=kind, value=value, weight=round(n / total, 3)))
    await session.flush()
    return len(users)


# ------------------------------------------------------------------ restaurant insights

def _km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _search_label(props: dict) -> str:
    parts = [f"'{props['q']}'" if props.get("q") else "dishes"]
    if props.get("max_kcal"):
        parts.append(f"under {props['max_kcal']:.0f} kcal")
    if props.get("min_protein"):
        parts.append(f"with {props['min_protein']:.0f} g+ protein")
    if props.get("max_price"):
        parts.append(f"under ₹{props['max_price']:.0f}")
    if props.get("diet"):
        parts.append({"veg": "(veg)", "egg": "(egg)", "non_veg": ""}.get(props["diet"], ""))
    return " ".join(p for p in parts if p)


async def insights(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID) -> InsightsOut:
    from app.services.businesses import repository as biz_repo
    from app.services.businesses import service as businesses
    from app.services.menus import repository as menus_repo
    await businesses.require(session, user_id, business_id)
    s = get_settings()
    minimum = s.INSIGHTS_MIN_USERS
    biz = await biz_repo.get(session, business_id)
    detailed = businesses.paid_features(biz)
    items = await menus_repo.items_for_business(session, business_id)
    stats = {i.id: await repository.dish_stats(session, i.id) for i in items}
    total_views = sum(st.views_7d for st in stats.values() if st)

    # Check-in feelings and recommend rate across this business's meals, last 30 days.
    since = datetime.now(UTC) - timedelta(days=30)
    branch_rows = await biz_repo.branches(session, business_id)
    branch_ids = {b.id for b, _, _ in branch_rows}
    entries = [e for e in await repository.entries_since(session, since) if e.branch_id in branch_ids]
    checks = await repository.checkins_for(session, [e.id for e in entries])
    owners = {e.id: e.user_id for e in entries}
    people = {owners[c.meal_entry_id] for c in checks if owners.get(c.meal_entry_id)}
    if len(people) >= minimum:
        felt = Counter(c.felt for c in checks if c.felt)
        rec = [c.recommend for c in checks if c.recommend is not None]
        checkin_text = (f"{len(checks)} check-ins from {len(people)} people: {felt['as_expected']} as expected, "
                        f"{felt['lighter']} lighter, {felt['heavier']} heavier")
        rate = f"{sum(rec) / len(rec):.0%} would recommend" if rec else None
    else:
        checkin_text, rate = f"Shown once at least {minimum} people have checked in.", None

    dishes = []
    if detailed:
        for i in items:
            st = stats.get(i.id)
            if st is None:
                continue
            enough = st.sample_users >= minimum
            dishes.append(DishInsight(
                menu_item_id=i.id, name=i.display_name, views_7d=st.views_7d,
                recommend=(f"{st.recommend_rate:.0%} would recommend (from {st.sample_users} people)"
                           if enough and st.recommend_rate is not None else None),
                felt=(f"{st.heavier_users} people found it heavier than expected" if enough and st.heavier_users else None)))
        dishes.sort(key=lambda d: -d.views_7d)

    # Unmet demand: nearby searches that found nothing, grouped, only with enough distinct people.
    groups = defaultdict(set)
    counts = Counter()
    located = [(b.id, lat, lng) for b, lat, lng in branch_rows if lat is not None]
    for ev in await repository.events(session, "search", since):
        p = ev.properties or {}
        if p.get("results") != 0 or p.get("lat") is None:
            continue
        if not any(_km(p["lat"], p["lng"], lat, lng) <= 2.0 for _, lat, lng in located):
            continue
        key = _search_label(p)
        groups[key].add(ev.user_id)
        counts[key] += 1
    demand = [DemandInsight(display=f"{counts[k]} searches within 2 km for {k} found nothing", searches=counts[k])
              for k, users in groups.items() if len(users) >= minimum]
    demand.sort(key=lambda d: -d.searches)
    total_unmet = sum(d.searches for d in demand)
    summary = (f"{total_unmet} searches near you found nothing in {len(demand)} kinds of request" if demand
               else "No unmet demand to report yet.")
    return InsightsOut(plan=biz.plan, detailed=detailed, total_views_7d=total_views, checkins_30d=checkin_text,
                       recommend_rate=rate, dishes=dishes, unmet_demand=demand if detailed else [], unmet_summary=summary,
                       minimum_note=f"Figures appear only when at least {minimum} different people contribute. "
                                    "You never see who they are.")
