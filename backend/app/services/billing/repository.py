import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access import Entitlement, PaymentEvent, Subscription, TrialClaim  # noqa: F401
from app.models.business import Business

OPEN = ("created", "authenticated", "active", "pending")


async def add(session: AsyncSession, obj):
    session.add(obj)
    await session.flush()
    return obj


async def event(session: AsyncSession, key: str) -> PaymentEvent | None:
    return await session.scalar(select(PaymentEvent).where(PaymentEvent.idempotency_key == key))


async def subscription_by_provider_id(session: AsyncSession, provider_id: str) -> Subscription | None:
    return await session.scalar(select(Subscription).where(Subscription.provider_subscription_id == provider_id))


async def subscription_by_key(session: AsyncSession, key: str) -> Subscription | None:
    return await session.scalar(select(Subscription).where(Subscription.idempotency_key == key))


async def active_subscription(session: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    return await session.scalar(select(Subscription).where(Subscription.user_id == user_id, Subscription.business_id.is_(None),
                                                           Subscription.status.in_(OPEN))
                                .order_by(Subscription.created_at.desc()).limit(1))


async def business_subscription(session: AsyncSession, business_id: uuid.UUID) -> Subscription | None:
    return await session.scalar(select(Subscription).where(Subscription.business_id == business_id,
                                                           Subscription.status.in_(OPEN + ("cancelled",)))
                                .order_by(Subscription.created_at.desc()).limit(1))


async def entitlement(session: AsyncSession, user_id: uuid.UUID) -> Entitlement | None:
    return await session.scalar(select(Entitlement).where(Entitlement.user_id == user_id))


async def business(session: AsyncSession, business_id: uuid.UUID) -> Business | None:
    return await session.get(Business, business_id)


async def reconcilable(session: AsyncSession) -> list[Subscription]:
    return list(await session.scalars(select(Subscription).where(Subscription.status.in_(OPEN + ("cancelled",)))))
