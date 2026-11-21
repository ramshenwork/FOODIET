"""Access levels. The effective level is always computed here, on the server, from stored dates."""
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.models.access import Entitlement
from app.services.entitlement import repository
from app.services.entitlement.schemas import EntitlementOut, Paywall


IST = ZoneInfo("Asia/Kolkata")
FULL = {"free", "trial", "subscriber", "grace"}   # must match core.access.FULL_ACCESS


def effective_level(ent: Entitlement | None, now: datetime | None = None) -> str:
    if not get_settings().PAYMENTS_ENABLED:
        return "free"  # testing build: everything unlocked, no trials or subscriptions
    now = now or datetime.now(UTC)
    if ent is None or ent.level == "preview":
        return "preview"
    if ent.level == "lapsed":
        return "lapsed"
    if ent.period_end and now < ent.period_end:
        return ent.level  # trial or subscriber within its period
    if ent.level in ("subscriber", "grace") and ent.grace_end and now < ent.grace_end:
        return "grace"
    return "lapsed"


async def access_level(session: AsyncSession, user_id: uuid.UUID) -> str:
    return effective_level(await repository.get(session, user_id))


async def _trial_available(session: AsyncSession, user_id: uuid.UUID, device_id: str | None = None) -> bool:
    from app.services.users.service import email_hash_for
    ent = await repository.get(session, user_id)
    if ent is not None and ent.source != "none":
        return False
    return not await repository.trial_claimed(session, await email_hash_for(session, user_id), device_id)


DISPLAY = {
    "free": ("Free while we test", "Everything is unlocked while Foodiet is in testing."),
    "preview": ("See what's in every dish", "Restaurant and dish names are free to browse. Nutrition needs a subscription."),
    "trial": ("Free trial", "Everything is unlocked during your trial."),
    "subscriber": ("Subscribed", "Everything is unlocked."),
    "grace": ("Payment retrying", "Your last payment didn't go through. Everything stays unlocked while it retries."),
    "lapsed": ("Your access has ended", "Your diary is still here to read and export. Subscribe to see nutrition again."),
}


def capabilities(level: str, trial_available: bool) -> dict:
    full = level in FULL
    return {"nutrition": full, "diary_write": full, "diary_read": full or level == "lapsed",
            "start_trial": trial_available and level == "preview", "subscribe": level in ("preview", "lapsed", "trial"),
            "billing": level != "free"}


async def get_entitlement(session: AsyncSession, user_id: uuid.UUID) -> EntitlementOut:
    ent = await repository.get(session, user_id)
    level = effective_level(ent)
    trial = level != "free" and await _trial_available(session, user_id)
    title, detail = DISPLAY[level]
    cancelled = await _cancelled(session, user_id)
    can = capabilities(level, trial)
    can["cancel"] = level != "free" and bool(ent and ent.source == "razorpay" and level in ("subscriber", "grace") and not cancelled)
    period = None
    if ent and ent.period_end and level in FULL:
        word = "Ends" if cancelled or ent.source == "trial" else "Renews"
        period = f"{word} {ent.period_end.astimezone(IST).strftime('%-d %b %Y')}"
    return EntitlementOut(
        can=can, display={"title": title, "detail": detail, "period": period},
        level=level,
        source=ent.source if ent else "none",
        period_end=ent.period_end if ent else None,
        grace_end=ent.grace_end if ent else None,
        trial_available=trial,
        cancelled=cancelled,
    )


async def _cancelled(session: AsyncSession, user_id: uuid.UUID) -> bool:
    from sqlalchemy import select
    from app.models.access import Subscription
    latest = await session.scalar(select(Subscription).where(Subscription.user_id == user_id)
                                  .order_by(Subscription.created_at.desc()).limit(1))
    return bool(latest and latest.status == "cancelled")


async def paywall_for(session: AsyncSession, user_id: uuid.UUID, level: str) -> dict:
    available = await _trial_available(session, user_id)
    message = ("Start your free trial to see outlet-specific nutrition." if available
               else "Subscribe to see outlet-specific nutrition.")
    st = get_settings()
    return Paywall(level=level, trial_available=available, trial_days=st.TRIAL_DAYS, message=message,
                   price_monthly_inr=st.PRICE_CONSUMER_MONTHLY_INR, price_yearly_inr=st.PRICE_CONSUMER_YEARLY_INR).model_dump()


async def admin_overview(session: AsyncSession, limit: int = 200) -> dict:
    """Trial claims and subscriptions for the admin Accounts screen. Email addresses are stored hashed."""
    from sqlalchemy import func, select
    from app.models.access import Subscription, TrialClaim
    claims = await session.scalar(select(func.count()).select_from(TrialClaim))
    recent = (await session.execute(select(TrialClaim.created_at, TrialClaim.device_id.is_not(None))
                                    .order_by(TrialClaim.created_at.desc()).limit(limit))).all()
    subs = (await session.scalars(select(Subscription).order_by(Subscription.created_at.desc()).limit(limit))).all()
    return {
        "trial_claims": claims,
        "recent_trial_claims": [{"claimed_at": c, "device_recorded": d} for c, d in recent],
        "subscriptions": [{"id": s.id, "plan": s.plan, "status": s.status, "provider": s.provider,
                           "current_period_end": s.current_period_end, "user_id": s.user_id, "business_id": s.business_id}
                          for s in subs],
    }
