from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import JSONB, TS, business_fk, fk


class Business(TableBase):
    __tablename__ = "businesses"
    __table_args__ = (CheckConstraint("plan IN ('free','paid')", name="plan"),)
    name: Mapped[str] = mapped_column(String(256))
    plan: Mapped[str] = mapped_column(String(8), default="free")
    owner_user_id = fk("users.id")


class Brand(TableBase):
    __tablename__ = "brands"
    business_id = business_fk()
    name: Mapped[str] = mapped_column(String(256))


class Branch(TableBase):
    __tablename__ = "branches"
    business_id = business_fk()
    brand_id = fk("brands.id", nullable=True)
    name: Mapped[str] = mapped_column(String(256))
    code: Mapped[str] = mapped_column(String(16), unique=True)  # public QR code path: /q/{code}
    address: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(String(64))  # picks regional reference recipes, e.g. 'hyderabad'
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    hours: Mapped[dict | None] = mapped_column(JSONB)
    fssai_number: Mapped[str | None] = mapped_column(String(32))
    cost_for_one_inr: Mapped[int | None]
    photo_path: Mapped[str | None] = mapped_column(String(512))
    deleted_at: Mapped[datetime | None] = mapped_column(TS)  # soft delete keeps diary history resolvable


class Membership(TableBase):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner','manager','chef','editor')", name="role"),
        UniqueConstraint("user_id", "business_id"),
    )
    user_id = fk("users.id", ondelete="CASCADE")
    business_id = business_fk()
    role: Mapped[str] = mapped_column(String(16))
