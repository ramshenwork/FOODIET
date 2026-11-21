from datetime import datetime

from sqlalchemy import CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import JSONB, TS, fk


class Entitlement(TableBase):
    __tablename__ = "entitlements"
    __table_args__ = (
        CheckConstraint("level IN ('preview','trial','subscriber','grace','lapsed')", name="level"),
        CheckConstraint("source IN ('none','trial','razorpay','store')", name="source"),
        UniqueConstraint("user_id"),
    )
    user_id = fk("users.id", ondelete="CASCADE")
    level: Mapped[str] = mapped_column(String(16), default="preview")
    source: Mapped[str] = mapped_column(String(16), default="none")
    period_end: Mapped[datetime | None] = mapped_column(TS)
    grace_end: Mapped[datetime | None] = mapped_column(TS)
    credited_branch_id = fk("branches.id", nullable=True)  # subscription started from a QR page


class TrialClaim(TableBase):
    """One trial per email and per device."""
    __tablename__ = "trial_claims"
    email_hash: Mapped[str] = mapped_column(String(64), unique=True)
    device_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    user_id = fk("users.id", nullable=True, ondelete="SET NULL")


class Subscription(TableBase):
    __tablename__ = "subscriptions"
    user_id = fk("users.id", nullable=True, ondelete="SET NULL")
    business_id = fk("businesses.id", nullable=True, ondelete="SET NULL")
    provider: Mapped[str] = mapped_column(String(16), default="razorpay")
    provider_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    plan: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    current_period_end: Mapped[datetime | None] = mapped_column(TS)


class PaymentEvent(TableBase):
    """Raw webhook payloads; the provider's event id makes processing idempotent."""
    __tablename__ = "payment_events"
    provider: Mapped[str] = mapped_column(String(16))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    processed_at: Mapped[datetime | None] = mapped_column(TS)


class WaitlistEntry(TableBase):
    """Shown instead of a purchase button where coverage is thin."""
    __tablename__ = "waitlist"
    email: Mapped[str] = mapped_column(String(320))
    area: Mapped[str | None] = mapped_column(String(256))
