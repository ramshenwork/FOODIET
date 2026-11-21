"""Stated profile, targets, restrictions, allergies, and consent. Nothing here is ever inferred."""
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.settings import get_settings
from app.models.profile import ConsentRecord, ConsumerProfile
from app.services.events import service as events
from app.services.nutrition import engine
from app.services.profile import repository
from app.services.profile.schemas import (ALLERGIES, RESTRICTIONS, ConsentIn, ProfileIn, ProfileOut, StatedFilters,
                                          Targets)

TARGET_NOTE = "Estimated targets, not medical advice."


def _f(v: str | None) -> float | None:
    return None if v in (None, "") else float(v)


async def _consented(session: AsyncSession, user_id: uuid.UUID, purpose: str) -> bool:
    return any(c.purpose == purpose and c.withdrawn_at is None for c in await repository.consents(session, user_id))


def _targets_from(p: ConsumerProfile) -> tuple[Targets | None, Targets | None]:
    s = get_settings()
    if not all([p.birth_year, p.sex_for_energy_estimate, p.height_cm, p.weight_kg, p.activity_level, p.goal]):
        return None, None
    if s.CALORIE_FLOOR_KCAL is None:
        return None, None
    age = date.today().year - p.birth_year
    t = engine.suggested_targets(p.sex_for_energy_estimate, _f(p.weight_kg), _f(p.height_cm), age, p.activity_level,
                                 p.goal, s.CALORIE_FLOOR_KCAL)
    suggested = Targets(energy_kcal=round(t["energy_kcal"]), protein_g=round(t["protein_g"]), carbs_g=round(t["carbs_g"]),
                        fat_g=round(t["fat_g"]), floor_applied=t["floor_applied"], note=TARGET_NOTE)
    if p.calorie_target is None:
        return suggested, suggested
    kcal = engine.clamp_user_target(_f(p.calorie_target), s.CALORIE_FLOOR_KCAL)
    protein = _f(p.protein_target_g) or t["protein_g"]
    fat = kcal * 0.30 / 9
    carbs = max(kcal - protein * 4 - fat * 9, 0) / 4
    chosen = Targets(energy_kcal=round(kcal), protein_g=round(protein), carbs_g=round(carbs), fat_g=round(fat),
                     floor_applied=kcal == s.CALORIE_FLOOR_KCAL, note=TARGET_NOTE)
    return suggested, chosen


async def get(session: AsyncSession, user_id: uuid.UUID) -> ProfileOut:
    p = await repository.profile(session, user_id)
    consents = {k: await _consented(session, user_id, k) for k in ("health_data", "learned_preferences")}
    floor = get_settings().CALORIE_FLOOR_KCAL
    if p is None:
        return ProfileOut(complete=False, birth_year=None, sex_for_energy_estimate=None, height_cm=None, weight_kg=None,
                          activity_level=None, goal=None, diet_type=None, restrictions=[], allergies=[], cuisines=[],
                          spice_level=None, budget_per_meal_inr=None, suggested=None, targets=None,
                          calorie_floor_kcal=floor, consents=consents)
    suggested, targets = _targets_from(p)
    return ProfileOut(
        complete=targets is not None and p.diet_type is not None, birth_year=p.birth_year,
        sex_for_energy_estimate=p.sex_for_energy_estimate, height_cm=_f(p.height_cm), weight_kg=_f(p.weight_kg),
        activity_level=p.activity_level, goal=p.goal, diet_type=p.diet_type,
        restrictions=sorted(await repository.restrictions(session, user_id)),
        allergies=sorted(await repository.allergies(session, user_id)),
        cuisines=[c for c in (p.cuisines or "").split(",") if c], spice_level=p.spice_level,
        budget_per_meal_inr=p.budget_per_meal_inr, suggested=suggested, targets=targets, calorie_floor_kcal=floor,
        consents=consents)


async def save(session: AsyncSession, user_id: uuid.UUID, body: ProfileIn) -> ProfileOut:
    s = get_settings()
    age = date.today().year - body.birth_year
    if age < 18:
        raise AppError(403, "under_18", "You need to be 18 or older to use this service.")
    if not body.health_data_consent:
        raise AppError(422, "consent_required", "We need your consent to store body measurements and allergies.")
    if set(body.restrictions) - RESTRICTIONS or set(body.allergies) - ALLERGIES:
        raise AppError(422, "unknown_option", "One of the restrictions or allergies isn't recognised.")
    if body.calorie_target is not None and s.CALORIE_FLOOR_KCAL is not None and body.calorie_target < s.CALORIE_FLOOR_KCAL:
        raise AppError(422, "below_floor", f"Daily energy targets can't go below {s.CALORIE_FLOOR_KCAL} kcal.")
    if not await _consented(session, user_id, "health_data"):
        await repository.add(session, ConsentRecord(user_id=user_id, purpose="health_data", granted_at=datetime.now(UTC)))
    p = await repository.profile(session, user_id) or await repository.add(session, ConsumerProfile(user_id=user_id))
    p.birth_year, p.sex_for_energy_estimate = body.birth_year, body.sex_for_energy_estimate
    p.height_cm, p.weight_kg = str(body.height_cm), str(body.weight_kg)
    p.activity_level, p.goal, p.diet_type = body.activity_level, body.goal, body.diet_type
    p.cuisines, p.spice_level, p.budget_per_meal_inr = ",".join(body.cuisines), body.spice_level, body.budget_per_meal_inr
    p.calorie_target = None if body.calorie_target is None else str(body.calorie_target)
    p.protein_target_g = None if body.protein_target_g is None else str(body.protein_target_g)
    await repository.replace_lists(session, user_id, sorted(set(body.restrictions)), sorted(set(body.allergies)))
    from app.services.users import service as users
    user = await users.get(session, user_id)
    user.date_of_birth_confirmed_18 = True
    await events.track(session, "profile_saved", user_id)
    return await get(session, user_id)


async def set_consent(session: AsyncSession, user_id: uuid.UUID, body: ConsentIn) -> ProfileOut:
    """Withdrawing consent stops processing and deletes the derived data."""
    now = datetime.now(UTC)
    if body.granted:
        if not await _consented(session, user_id, body.purpose):
            await repository.add(session, ConsentRecord(user_id=user_id, purpose=body.purpose, granted_at=now))
    else:
        await repository.now_withdraw(session, user_id, body.purpose, now)
        if body.purpose == "health_data":
            await repository.delete_health_data(session, user_id)
            p = await repository.profile(session, user_id)
            if p:
                p.height_cm = p.weight_kg = p.calorie_target = p.protein_target_g = None
                p.carb_target_g = p.fat_target_g = None
        else:
            from sqlalchemy import delete
            from app.models.profile import LearnedPreference
            await session.execute(delete(LearnedPreference).where(LearnedPreference.user_id == user_id))
    await events.audit(session, user_id, "consent_" + ("granted" if body.granted else "withdrawn"), "consent", body.purpose)
    return await get(session, user_id)


async def stated(session: AsyncSession, user_id: uuid.UUID) -> StatedFilters:
    p = await repository.profile(session, user_id)
    out = await get(session, user_id)
    return StatedFilters(user_id=user_id, diet_type=out.diet_type, restrictions=set(out.restrictions),
                         allergies=set(out.allergies), targets=out.targets,
                         budget_per_meal_inr=p.budget_per_meal_inr if p else None)


async def export(session: AsyncSession, user_id: uuid.UUID) -> dict:
    prof = await get(session, user_id)
    return {"profile": prof.model_dump(mode="json"),
            "consents": [{"purpose": c.purpose, "granted_at": c.granted_at.isoformat(),
                          "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None}
                         for c in await repository.consents(session, user_id)],
            "weight_log": [{"date": w.logged_on.isoformat(), "weight_kg": w.weight_kg}
                           for w in await repository.weight_log(session, user_id)]}


async def delete_all(session: AsyncSession, user_id: uuid.UUID) -> None:
    await repository.delete_all(session, user_id)


# ------------------------------------------------------------------ food fingerprint

async def fingerprint(session: AsyncSession, user_id: uuid.UUID):
    """Everything learned about the user, each item removable. Shown to the user; never used to override
    their stated diet, restrictions or allergies, and never used to infer health conditions or religion."""
    from collections import Counter
    from app.services.aggregates import repository as agg_repo
    from app.services.diary import repository as diary_repo
    from app.services.diary.service import _item_nutrients
    from app.services.profile.schemas import FingerprintOut, LearnedOut
    consented = await _consented(session, user_id, "learned_preferences")
    note = "Learned from your diary. It only affects what you see here, never your filters."
    if not consented:
        return FingerprintOut(consented=False, learned=[], top_cuisines=[], avg_protein_eating_out=None, most_repeated=[],
                              note="Turn this on to see what we learn from your diary. You can remove anything, any time.")
    learned = [p for p in await agg_repo.learned(session, user_id) if p.weight >= 0]
    entries = [e for e in await diary_repo.all_for_user(session, user_id) if e.branch_id]
    items = await diary_repo.items(session, [e.id for e in entries])
    proteins, names = [], Counter()
    by_entry = {}
    for it in items:
        n = _item_nutrients(it) or {}
        by_entry.setdefault(it.meal_entry_id, []).append(n.get("protein_g"))
        names[(it.nutrition_snapshot or {}).get("name")] += 1
    for vals in by_entry.values():
        if all(v is not None for v in vals):
            proteins.append(sum(v["mid"] for v in vals))
    avg = f"About {round(sum(proteins) / len(proteins))} g protein per meal out" if proteins else None
    return FingerprintOut(
        consented=True,
        learned=[LearnedOut(id=p.id, kind=p.kind, value=p.value,
                            display=f"{'You often eat' if p.kind == 'dish' else 'You often choose'} {p.value}") for p in learned],
        top_cuisines=[p.value for p in learned if p.kind == "cuisine"][:3], avg_protein_eating_out=avg,
        most_repeated=[n for n, c in names.most_common(3) if n and c > 1], note=note)


async def remove_learned(session: AsyncSession, user_id: uuid.UUID, pref_id: uuid.UUID) -> None:
    """Removed preferences stay suppressed, so the nightly job doesn't learn them again."""
    from app.services.aggregates import repository as agg_repo
    from app.core.errors import NotFound
    p = next((x for x in await agg_repo.learned(session, user_id) if x.id == pref_id), None)
    if p is None:
        raise NotFound("Not found")
    p.weight = -1
