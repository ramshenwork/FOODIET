"""Trial, subscriptions (diners and restaurants) and payment webhooks.

PAYMENTS_MODE=mock simulates Razorpay's webhook end to end; live creates real Razorpay subscriptions.
Either way the client never grants access: the server's record changes only through a verified webhook
(or the daily reconciliation), and the client polls GET /me/entitlement.
"""
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import keyed_hash
from app.core.settings import get_settings
from app.models.access import Entitlement, PaymentEvent, Subscription, TrialClaim
from app.services.billing import razorpay, repository
from app.services.billing.schemas import CancelOut, PlanOut, SubscribeIn, SubscribeOut
from app.services.events import service as events

PLAN_DAYS = {"monthly": 30, "yearly": 365}


def _require_payments() -> None:
    if not get_settings().PAYMENTS_ENABLED:
        raise AppError(409, "payments_off", "Payments aren't switched on while Foodiet is in testing.")


def _live() -> bool:
    return get_settings().PAYMENTS_MODE == "live"


async def _entitlement(session: AsyncSession, user_id: uuid.UUID) -> Entitlement:
    ent = await repository.entitlement(session, user_id)
    if ent is None:
        ent = await repository.add(session, Entitlement(user_id=user_id, level="preview", source="none"))
    return ent


async def start_trial(session: AsyncSession, user_id: uuid.UUID, device_id: str) -> None:
    _require_payments()
    from app.services.entitlement import repository as ent_repo
    from app.services.users import service as users
    user = await users.get(session, user_id)
    email_hash = keyed_hash(user.email)
    ent = await _entitlement(session, user_id)
    if ent.source != "none" or await ent_repo.trial_claimed(session, email_hash, device_id):
        raise AppError(409, "trial_used", "The free trial has already been used for this account or device.")
    await repository.add(session, TrialClaim(email_hash=email_hash, device_id=device_id, user_id=user_id))
    now = datetime.now(UTC)
    ent.level, ent.source, ent.period_end, ent.grace_end = "trial", "trial", now + timedelta(days=get_settings().TRIAL_DAYS), None
    await events.track(session, "trial_started", user_id)


async def _start(session: AsyncSession, *, user_id: uuid.UUID | None, business_id: uuid.UUID | None, plan: str,
                 cycle: str, plan_id: str | None, key: str | None, email: str | None, description: str) -> tuple[Subscription, dict | None]:
    """Create the subscription in Razorpay (live) or simulate a successful first charge (mock)."""
    s = get_settings()
    if _live():
        if not plan_id:
            raise AppError(503, "plan_not_configured", "This plan isn't available yet.")
        notes = {"user_id": str(user_id)} if user_id else {"business_id": str(business_id)}
        try:
            r = await razorpay.create_subscription(plan_id, cycle, notes)
        except razorpay.RazorpayError as e:
            raise AppError(502, "payment_provider_error", "Payments are unavailable right now. Try again shortly.") from e
        sub = await repository.add(session, Subscription(user_id=user_id, business_id=business_id, provider="razorpay",
                                                         provider_subscription_id=r["id"], plan=plan, status=r.get("status", "created"),
                                                         idempotency_key=key))
        checkout = {"key": s.RAZORPAY_KEY_ID, "subscription_id": r["id"], "name": s.APP_NAME, "description": description,
                    "prefill": {"email": email} if email else {}, "theme": {"color": "#FF7A1A"}}
        return sub, checkout
    sub = await repository.add(session, Subscription(user_id=user_id, business_id=business_id, provider="mock",
                                                     provider_subscription_id=f"mock_sub_{secrets.token_hex(8)}", plan=plan,
                                                     status="created", idempotency_key=key))
    await process_event(session, f"mock_evt_{secrets.token_hex(8)}", "subscription.charged", {
        "subscription": {"entity": {"id": sub.provider_subscription_id, "status": "active",
                                    "current_end": int((datetime.now(UTC) + timedelta(days=PLAN_DAYS[cycle])).timestamp())}}})
    return sub, None


async def subscribe(session: AsyncSession, user_id: uuid.UUID, body: SubscribeIn, idempotency_key: str | None) -> SubscribeOut:
    _require_payments()
    s = get_settings()
    key = f"{user_id}:{idempotency_key}" if idempotency_key else None
    if key and (existing := await repository.subscription_by_key(session, key)):
        return SubscribeOut(mode=existing.provider, subscription_id=existing.provider_subscription_id, checkout=None)
    if await repository.active_subscription(session, user_id):
        raise AppError(409, "already_subscribed", "You already have an active subscription.")
    ent = await _entitlement(session, user_id)
    if body.ref:
        from app.services.businesses import service as businesses
        branch = await businesses.branch_by_code(session, body.ref)
        if branch:
            ent.credited_branch_id = branch.id  # credited to the outlet whose QR page it started from
    from app.services.users import service as users
    user = await users.get(session, user_id)
    plan_id = s.RAZORPAY_PLAN_CONSUMER_MONTHLY if body.plan == "monthly" else s.RAZORPAY_PLAN_CONSUMER_YEARLY
    sub, checkout = await _start(session, user_id=user_id, business_id=None, plan=f"consumer_{body.plan}", cycle=body.plan,
                                 plan_id=plan_id, key=key, email=user.email, description=f"{body.plan.capitalize()} subscription")
    return SubscribeOut(mode=sub.provider if sub.provider == "mock" else "live", subscription_id=sub.provider_subscription_id,
                        checkout=checkout)


async def _cancel(session: AsyncSession, sub: Subscription) -> None:
    if sub.provider == "razorpay":
        try:
            await razorpay.cancel_subscription(sub.provider_subscription_id)
        except razorpay.RazorpayError as e:
            raise AppError(502, "payment_provider_error", "Couldn't reach the payment provider. Try again shortly.") from e
        sub.status = "cancelled"  # the webhook confirms; access continues to the period end either way
    else:
        await process_event(session, f"mock_evt_{secrets.token_hex(8)}", "subscription.cancelled",
                            {"subscription": {"entity": {"id": sub.provider_subscription_id, "status": "cancelled"}}})


async def cancel(session: AsyncSession, user_id: uuid.UUID) -> CancelOut:
    """Cancels renewal. Access continues until the end of the paid period, then the account is lapsed."""
    _require_payments()
    sub = await repository.active_subscription(session, user_id)
    if sub is None:
        raise AppError(409, "no_subscription", "There is no active subscription to cancel.")
    await _cancel(session, sub)
    ent = await repository.entitlement(session, user_id)
    if ent:
        ent.grace_end = None
    return CancelOut(access_until=ent.period_end.isoformat() if ent and ent.period_end else None)


# ------------------------------------------------------------------ restaurant paid plan

async def business_plan(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID) -> PlanOut:
    from app.services.businesses import service as businesses
    await businesses.require(session, user_id, business_id)
    biz = await repository.business(session, business_id)
    sub = await repository.business_subscription(session, business_id)
    return PlanOut(plan=biz.plan, mode="live" if _live() else "mock", subscription_id=sub.provider_subscription_id if sub else None,
                   checkout=None, renews_until=sub.current_period_end.isoformat() if sub and sub.current_period_end else None)


async def business_subscribe(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID) -> PlanOut:
    _require_payments()
    from app.services.businesses import service as businesses
    from app.services.users import service as users
    await businesses.require(session, user_id, business_id, "manage_team")   # owner only
    biz = await repository.business(session, business_id)
    if biz.plan == "paid" or await repository.business_subscription(session, business_id):
        raise AppError(409, "already_paid", "This restaurant is already on the paid plan.")
    user = await users.get(session, user_id)
    sub, checkout = await _start(session, user_id=None, business_id=business_id, plan="business_monthly", cycle="monthly",
                                 plan_id=get_settings().RAZORPAY_PLAN_BUSINESS_MONTHLY, key=None, email=user.email,
                                 description=f"{biz.name}: paid plan")
    out = await business_plan(session, user_id, business_id)
    out.checkout = checkout
    return out


async def business_cancel(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID) -> PlanOut:
    _require_payments()
    from app.services.businesses import service as businesses
    await businesses.require(session, user_id, business_id, "manage_team")
    sub = await repository.business_subscription(session, business_id)
    if sub is None or sub.status == "cancelled":
        raise AppError(409, "no_subscription", "There's no paid plan to cancel.")
    await _cancel(session, sub)
    return await business_plan(session, user_id, business_id)


# ------------------------------------------------------------------ webhooks

def verify_signature(raw: bytes, signature: str | None) -> bool:
    secret = get_settings().RAZORPAY_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def webhook(session: AsyncSession, raw: bytes, signature: str | None, event_id: str | None) -> dict:
    _require_payments()
    if not verify_signature(raw, signature):
        raise AppError(400, "bad_signature", "Webhook signature is invalid.")
    body = json.loads(raw)
    key = event_id or body.get("id") or hashlib.sha256(raw).hexdigest()
    return await process_event(session, key, body.get("event", ""), body.get("payload", {}), body)


async def process_event(session: AsyncSession, key: str, event: str, payload: dict, raw: dict | None = None) -> dict:
    """Applies one payment event exactly once (the event id is the idempotency key)."""
    if await repository.event(session, key):
        return {"status": "duplicate"}
    record = await repository.add(session, PaymentEvent(provider="mock" if key.startswith("mock_") else "razorpay",
                                                        idempotency_key=key, event_type=event,
                                                        payload=raw or {"event": event, "payload": payload}))
    entity = (payload.get("subscription") or {}).get("entity") or {}
    sub = await repository.subscription_by_provider_id(session, entity.get("id", ""))
    now = datetime.now(UTC)
    if sub is None:
        record.processed_at = now
        return {"status": "ignored"}
    end = datetime.fromtimestamp(entity["current_end"], UTC) if entity.get("current_end") else None
    if sub.business_id:
        await _apply_business(session, sub, event, end)
    elif sub.user_id:
        await _apply_consumer(session, sub, event, end, now)
    record.processed_at = now
    await events.audit(session, None, "payment_event", "subscription", sub.provider_subscription_id, event=event)
    return {"status": "processed"}


async def _apply_consumer(session: AsyncSession, sub: Subscription, event: str, end: datetime | None, now: datetime) -> None:
    ent = await _entitlement(session, sub.user_id)
    if event in ("subscription.activated", "subscription.charged"):
        end = end or now + timedelta(days=30)
        sub.status, sub.current_period_end = "active", end
        ent.level, ent.source, ent.period_end, ent.grace_end = "subscriber", "razorpay", end, None
    elif event == "subscription.pending":  # renewal failed; retries continue during grace
        sub.status = "pending"
        ent.level, ent.grace_end = "grace", now + timedelta(days=get_settings().GRACE_DAYS)
    elif event == "subscription.halted":
        sub.status, ent.level, ent.grace_end = "halted", "lapsed", None
    elif event == "subscription.cancelled":
        sub.status, ent.grace_end = "cancelled", None   # keeps access to period_end, then lapses
    elif event == "subscription.completed":
        sub.status, ent.level = "completed", "lapsed"


async def _apply_business(session: AsyncSession, sub: Subscription, event: str, end: datetime | None) -> None:
    biz = await repository.business(session, sub.business_id)
    if event in ("subscription.activated", "subscription.charged"):
        sub.status, sub.current_period_end, biz.plan = "active", end, "paid"
    elif event == "subscription.pending":
        sub.status = "pending"   # stays paid during Razorpay's retries
    elif event in ("subscription.halted", "subscription.completed"):
        sub.status, biz.plan = event.split(".")[1], "free"
    elif event == "subscription.cancelled":
        sub.status = "cancelled"   # paid until the period ends; the daily reconciliation then moves it to free


# ------------------------------------------------------------------ daily reconciliation

async def reconcile(session: AsyncSession, now: datetime | None = None) -> dict:
    """Compare our records with Razorpay and correct any mismatch; end cancelled plans at their period end."""
    if not get_settings().PAYMENTS_ENABLED:
        return {"skipped": "payments off"}
    now = now or datetime.now(UTC)
    fixed = checked = 0
    for sub in await repository.reconcilable(session):
        checked += 1
        if sub.provider == "razorpay":
            try:
                remote = await razorpay.fetch_subscription(sub.provider_subscription_id)
            except razorpay.RazorpayError:
                continue
            status = remote.get("status")
            event = {"active": "subscription.charged", "halted": "subscription.halted", "pending": "subscription.pending",
                     "cancelled": "subscription.cancelled", "completed": "subscription.completed"}.get(status)
            end = remote.get("current_end")
            mismatch = status != sub.status or (end and sub.current_period_end and int(sub.current_period_end.timestamp()) != end)
            if event and mismatch:
                await process_event(session, f"reconcile:{sub.id}:{status}:{end}", event,
                                    {"subscription": {"entity": {"id": sub.provider_subscription_id, "current_end": end}}})
                fixed += 1
        if sub.status == "cancelled" and sub.business_id and sub.current_period_end and sub.current_period_end <= now:
            biz = await repository.business(session, sub.business_id)
            if biz.plan != "free":
                biz.plan, sub.status = "free", "completed"
                fixed += 1
    return {"checked": checked, "fixed": fixed}
