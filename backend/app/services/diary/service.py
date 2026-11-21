"""Meal diary. Each item stores a snapshot of what was shown when it was logged (fixed rule 5) plus the recipe
version or reference recipe it came from; later recipe changes never alter past entries."""
import uuid
from datetime import UTC, date, datetime, time, timedelta
from fractions import Fraction
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.models.activity import MealEntry, MealEntryItem
from app.services.diary import repository
from app.services.diary.schemas import DayOut, EntryIn, EntryItemOut, EntryOut, EntryUpdate, Ring
from app.services.events import service as events
from app.services.nutrition.engine import NUTRIENTS
from app.services.trust import rules
from app.services.trust import service as trust

TZ = ZoneInfo("Asia/Kolkata")


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, TZ)
    return start, start + timedelta(days=1)


def today() -> date:
    return datetime.now(TZ).date()


def share_display(share: float) -> str:
    named = {1.0: "Whole", 0.5: "Half", round(1 / 3, 4): "A third", 0.25: "A quarter", round(2 / 3, 4): "Two thirds"}
    if round(share, 4) in named:
        return named[round(share, 4)]
    f = Fraction(share).limit_denominator(12)
    return f"{f.numerator}/{f.denominator}"


async def _snapshot(session: AsyncSession, it) -> tuple[dict, uuid.UUID | None]:
    from app.services.search import service as search
    item, branch = await search._item_and_branch(session, it.menu_item_id)
    r = await search.resolve(session, item, branch, it.serving_option_id, it.share_fraction, it.modifier_ids)
    snap = {
        "name": item.display_name, "restaurant": branch.name, "branch_id": str(branch.id),
        "trust": {"label": r.label, "note": r.note}, "serving_label": r.serving_label,
        "nutrients": (r.shown or {}).get("nutrients"), "allergens": r.allergens,
        "recipe_version_id": str(r.recipe_version_id) if r.recipe_version_id else None,
        "reference_recipe_id": str(r.reference_id) if r.reference_id else None, "logged_share": it.share_fraction,
    }
    return snap, r.recipe_version_id


async def add_entry(session: AsyncSession, user_id: uuid.UUID, body: EntryIn, idempotency_key: str | None) -> EntryOut:
    key = f"{user_id}:{idempotency_key}" if idempotency_key else None
    if key and (existing := await repository.by_key(session, key)):
        return (await _entries_out(session, [existing]))[0]
    snaps = [await _snapshot(session, it) for it in body.items]
    branch_ids = {s["branch_id"] for s, _ in snaps}
    entry = await repository.add(session, MealEntry(
        user_id=user_id, branch_id=uuid.UUID(branch_ids.pop()) if len(branch_ids) == 1 else None,
        eaten_at=body.eaten_at or datetime.now(UTC), meal_type=body.meal_type, idempotency_key=key))
    for it, (snap, version_id) in zip(body.items, snaps):
        await repository.add(session, MealEntryItem(
            meal_entry_id=entry.id, menu_item_id=it.menu_item_id, recipe_version_id=version_id,
            serving_option_id=it.serving_option_id, component_label=it.component_label, share_fraction=it.share_fraction,
            modifiers=[str(m) for m in it.modifier_ids], nutrition_snapshot=snap))
    await events.track(session, "meal_logged", user_id, items=len(body.items))
    return (await _entries_out(session, [entry]))[0]


def _scaled(nutrients: dict | None, factor: float) -> dict | None:
    """Re-display a snapshot at a different share, without recalculating from today's recipe."""
    if nutrients is None:
        return None
    out = {}
    for n, v in nutrients.items():
        out[n] = None if v is None else rules.display_value(n, v["low"] * factor, v["mid"] * factor, v["high"] * factor,
                                                             v["display_mode"])
    return out


async def update_entry(session: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID, body: EntryUpdate) -> EntryOut:
    entry = await repository.entry(session, user_id, entry_id)
    if entry is None:
        raise NotFound("Diary entry not found")
    entry.meal_type = body.meal_type
    items = await repository.items(session, [entry.id])
    for it in items:
        if it.id in body.remove_item_ids:
            await repository.delete(session, it)
        elif it.id in body.shares:
            share = body.shares[it.id]
            if not 0 < share <= 1:
                raise AppError(422, "share_invalid", "Pick a share between a little and the whole serving.")
            it.share_fraction = share
    if len(body.remove_item_ids) and len(body.remove_item_ids) >= len(items):
        await repository.delete(session, entry)
        raise AppError(410, "entry_removed", "All items were removed, so the meal was deleted.")
    return (await _entries_out(session, [entry]))[0]


async def delete_entry(session: AsyncSession, user_id: uuid.UUID, entry_id: uuid.UUID) -> None:
    entry = await repository.entry(session, user_id, entry_id)
    if entry is None:
        raise NotFound("Diary entry not found")
    await repository.delete(session, entry)


def _item_nutrients(it: MealEntryItem) -> dict | None:
    snap = it.nutrition_snapshot or {}
    logged = snap.get("logged_share") or it.share_fraction
    return _scaled(snap.get("nutrients"), it.share_fraction / logged) if snap.get("nutrients") else None


async def _entries_out(session: AsyncSession, entries: list[MealEntry]) -> list[EntryOut]:
    items = await repository.items(session, [e.id for e in entries])
    out = []
    for e in entries:
        mine = [i for i in items if i.meal_entry_id == e.id]
        rows, total = [], 0.0
        for it in mine:
            snap = it.nutrition_snapshot or {}
            n = _item_nutrients(it)
            energy = (n or {}).get("energy_kcal")
            total += energy["mid"] if energy else 0
            rows.append(EntryItemOut(id=it.id, name=snap.get("name", "Dish"), restaurant=snap.get("restaurant"),
                                     component_label=it.component_label, serving_label=snap.get("serving_label"),
                                     share_fraction=it.share_fraction, share_display=share_display(it.share_fraction),
                                     trust=snap.get("trust", {"label": "no_data", "note": None}), energy=energy,
                                     protein=(n or {}).get("protein_g"), allergens=snap.get("allergens", {})))
        restaurants = {r.restaurant for r in rows if r.restaurant}
        out.append(EntryOut(id=e.id, meal_type=e.meal_type, eaten_at=e.eaten_at,
                            restaurant=restaurants.pop() if len(restaurants) == 1 else None, items=rows,
                            energy_display=f"about {round(total / 10) * 10:,.0f} kcal" if total else None))
    return out


def _sum(item_nutrients: list[dict | None]) -> dict:
    """Day totals. A nutrient unknown for any item is unknown for the day, never a partial sum shown as complete."""
    totals = {}
    for n in NUTRIENTS:
        lo = mid = hi = 0.0
        known = True
        for nutrients in item_nutrients:
            v = (nutrients or {}).get(n)
            if v is None:
                known = False
                break
            lo, mid, hi = lo + v["low"], mid + v["mid"], hi + v["high"]
        totals[n] = (lo, mid, hi) if known and item_nutrients else None
    return totals


async def day(session: AsyncSession, user_id: uuid.UUID, d: date, read_only: bool) -> DayOut:
    from app.services.profile import service as profile
    start, end = _day_bounds(d)
    entries = await repository.entries_between(session, user_id, start, end)
    out = await _entries_out(session, entries)
    item_rows = await repository.items(session, [e.id for e in entries])
    raw = _sum([_item_nutrients(i) for i in item_rows])
    t = trust.thresholds()
    totals = {}
    for n, v in raw.items():
        totals[n] = None if v is None else rules.display_value(n, *v, rules.display_mode(v[0], v[2], t) if v[0] > 0 else "single")
    targets = (await profile.stated(session, user_id)).targets
    rings = energy_value = caption = remaining = None
    if targets:
        def ring(label, n, target):
            v = raw[n]
            mid = v[1] if v else 0.0
            return Ring(label=label, display=f"{round(mid):,} / {target:,} g" if n != "energy_kcal" else f"{round(mid / 10) * 10:,} kcal",
                        fraction=mid / target if target else None)
        rings = {"energy": ring("Energy", "energy_kcal", targets.energy_kcal), "protein": ring("Protein", "protein_g", targets.protein_g),
                 "carbs": ring("Carbs", "carbs_g", targets.carbs_g), "fat": ring("Fat", "fat_g", targets.fat_g)}
        eaten = raw["energy_kcal"][1] if raw["energy_kcal"] else 0.0
        energy_value = round(eaten / 10) * 10
        caption = f"of {targets.energy_kcal:,} kcal"
        left = targets.energy_kcal - eaten
        remaining = (f"{round(left / 10) * 10:,.0f} kcal left today" if left >= 0
                     else f"{round(-left / 10) * 10:,.0f} kcal over today's estimate")
    return DayOut(date=d, entries=out, totals=totals, rings=rings, energy_value=energy_value, energy_caption=caption,
                  remaining_display=remaining, read_only=read_only)


async def eaten_today_kcal(session: AsyncSession, user_id: uuid.UUID) -> float:
    start, end = _day_bounds(today())
    entries = await repository.entries_between(session, user_id, start, end)
    total = 0.0
    for it in await repository.items(session, [e.id for e in entries]):
        e = (_item_nutrients(it) or {}).get("energy_kcal")
        total += e["mid"] if e else 0
    return total


async def export(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    entries = await repository.all_for_user(session, user_id)
    return [e.model_dump(mode="json") for e in await _entries_out(session, entries)]


async def anonymise(session: AsyncSession, user_id: uuid.UUID) -> None:
    """On account deletion: diary rows that feed aggregates are kept without the person."""
    for e in await repository.all_for_user(session, user_id):
        e.user_id, e.idempotency_key = None, None


# ------------------------------------------------------------------ weekly trends

async def trends(session: AsyncSession, user_id: uuid.UUID, weeks: int = 8):
    from app.services.diary.schemas import TrendsOut, WeekPoint
    from app.services.profile import service as profile
    targets = (await profile.stated(session, user_id)).targets
    t = today()
    this_monday = t - timedelta(days=t.weekday())
    start = this_monday - timedelta(weeks=weeks - 1)
    s, _ = _day_bounds(start)
    _, e = _day_bounds(t)
    entries = await repository.entries_between(session, user_id, s, e)
    items = await repository.items(session, [x.id for x in entries])
    day_of = {x.id: x.eaten_at.astimezone(TZ).date() for x in entries}
    per_day: dict[date, list] = {}
    for it in items:
        per_day.setdefault(day_of[it.meal_entry_id], []).append(_item_nutrients(it))
    points = []
    for w in range(weeks):
        ws = start + timedelta(weeks=w)
        days = [d for d in per_day if ws <= d < ws + timedelta(days=7)]
        energy, protein = [], []
        for d in days:
            tot = _sum(per_day[d])
            if tot["energy_kcal"]:
                energy.append(tot["energy_kcal"][1])
            if tot["protein_g"]:
                protein.append(tot["protein_g"][1])
        points.append(WeekPoint(week_start=ws, label=ws.strftime("%-d %b"), days_logged=len(days),
                                avg_energy_kcal=round(sum(energy) / len(energy) / 10) * 10 if energy else None,
                                avg_protein_g=round(sum(protein) / len(protein)) if protein else None,
                                energy_target=targets.energy_kcal if targets else None,
                                protein_target=targets.protein_g if targets else None))
    cur, prev = points[-1], points[-2] if len(points) > 1 else None
    recap = None
    if cur.days_logged:
        lines = [f"You logged {cur.days_logged} day{'s' if cur.days_logged != 1 else ''} this week."]
        if cur.avg_energy_kcal is not None:
            lines.append(f"Average {cur.avg_energy_kcal:,} kcal on logged days"
                         + (f", against a target of {cur.energy_target:,}." if cur.energy_target else "."))
        if cur.avg_protein_g is not None and prev and prev.avg_protein_g:
            diff = cur.avg_protein_g - prev.avg_protein_g
            lines.append(f"Protein {'up' if diff >= 0 else 'down'} {abs(diff)} g a day from last week." if diff
                         else "Protein the same as last week.")
        recap = {"title": "Your week", "lines": lines}
    return TrendsOut(weeks=points, recap=recap)
