"""Trust labels, ranges and checks, configured from .env. The rules themselves live in rules.py."""
from datetime import UTC, datetime

from app.core.settings import get_settings
from app.services.nutrition.engine import Result
from app.services.trust import rules


def thresholds() -> rules.Thresholds:
    s = get_settings()
    return rules.Thresholds(
        spread_verified=s.SPREAD_VERIFIED, spread_declared=s.SPREAD_DECLARED, spread_estimated=s.SPREAD_ESTIMATED,
        ratio_band=s.DISPLAY_RATIO_BAND, ratio_range=s.DISPLAY_RATIO_RANGE, ratio_exclude=s.DISPLAY_RATIO_EXCLUDE,
        hysteresis=s.DISPLAY_HYSTERESIS, expiry_days=s.VERIFICATION_EXPIRY_DAYS,
        energy_margin=s.PLAUSIBILITY_ENERGY_MARGIN, yield_min=s.PLAUSIBILITY_YIELD_MIN, yield_max=s.PLAUSIBILITY_YIELD_MAX,
        max_fat_share=s.PLAUSIBILITY_MAX_FAT_SHARE, protein_min_ratio=s.PLAUSIBILITY_PROTEIN_MIN_RATIO,
        max_energy_change=s.PLAUSIBILITY_MAX_ENERGY_CHANGE, heavier_step=s.HEAVIER_WIDEN_STEP,
    )


def estimated_display(values: dict, reference_spread: float | None, previous_mode: str | None = None) -> dict:
    """Display fields for values calculated from a platform reference recipe."""
    t = thresholds()
    trust = rules.effective_trust("estimated", t, datetime.now(UTC), reference_spread=reference_spread)
    out = rules.display_nutrients(values, trust, t, previous_mode=previous_mode)
    out["trust"] = {"label": trust.label, "note": trust.note}
    out["allergens"] = rules.allergen_display(trust.label, ())
    return out


def check(result: Result, expected_kcal_100g: tuple[float, float] | None, serving_weights_g=(),
          previous_energy_100g: float | None = None) -> list[rules.Flag]:
    return rules.plausibility_checks(result, thresholds(), expected_kcal_100g, tuple(serving_weights_g),
                                     previous_energy_100g)


# ------------------------------------------------------------------ records

import uuid  # noqa: E402
from datetime import timedelta  # noqa: E402

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.models.nutrition import PlausibilityFlag, TrustRecord  # noqa: E402
from app.services.trust import repository  # noqa: E402


async def record_declared(session: AsyncSession, version_id: uuid.UUID, now: datetime | None = None) -> None:
    from app.services.search.service import clear_cache
    clear_cache()
    now = now or datetime.now(UTC)
    await repository.add(session, TrustRecord(recipe_version_id=version_id, label="declared", verified_at=now,
                                              expires_at=now + timedelta(days=thresholds().expiry_days)))


async def record_flags(session: AsyncSession, version_id: uuid.UUID, flags: list[rules.Flag]) -> None:
    for f in flags:
        await repository.add(session, PlausibilityFlag(recipe_version_id=version_id, rule=f.rule,
                                                       detail={**f.detail, "message": f.message}))


async def reconfirm(session: AsyncSession, version_id: uuid.UUID, now: datetime | None = None) -> datetime:
    from app.services.search.service import clear_cache
    clear_cache()
    now = now or datetime.now(UTC)
    declared = [r for r in await repository.records(session, version_id) if r.label == "declared"]
    if not declared:
        await record_declared(session, version_id, now)
    else:
        declared[-1].verified_at = now
        declared[-1].expires_at = now + timedelta(days=thresholds().expiry_days)
    return now + timedelta(days=thresholds().expiry_days)


async def effective_for_version(session: AsyncSession, version_id: uuid.UUID, now: datetime | None = None) -> rules.EffectiveTrust:
    now = now or datetime.now(UTC)
    recs = await repository.records(session, version_id)
    verified = [r for r in recs if r.label == "verified"]
    declared = [r for r in recs if r.label == "declared"]
    confirmed = declared[-1].verified_at if declared else None
    if verified:
        return rules.effective_trust("verified", thresholds(), now, verified_expires_at=verified[-1].expires_at,
                                     declared_confirmed_at=confirmed)
    return rules.effective_trust("declared", thresholds(), now, declared_confirmed_at=confirmed)


async def open_flag_count(session: AsyncSession, version_ids: list[uuid.UUID]) -> int:
    return len(await repository.open_flags(session, version_ids))


async def flags_for(session: AsyncSession, version_id: uuid.UUID) -> list[dict]:
    return [{"id": f.id, "rule": f.rule, "message": f.detail.get("message"), "resolution": f.resolution,
             "resolution_note": f.resolution_note} for f in await repository.flags_for(session, version_id)]


async def expiring_soon(session: AsyncSession, version_ids: list[uuid.UUID], days: int = 14) -> int:
    return len(await repository.expiring(session, version_ids, datetime.now(UTC) + timedelta(days=days)))
