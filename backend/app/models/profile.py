from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.core.security import EncryptedString
from app.models._types import TS, fk


class ConsumerProfile(TableBase):
    __tablename__ = "consumer_profiles"
    user_id = fk("users.id", ondelete="CASCADE")
    birth_year: Mapped[int | None]
    sex_for_energy_estimate: Mapped[str | None] = mapped_column(String(8))  # 'male' | 'female' (equation input only)
    height_cm: Mapped[str | None] = mapped_column(EncryptedString)
    weight_kg: Mapped[str | None] = mapped_column(EncryptedString)
    activity_level: Mapped[str | None] = mapped_column(String(16))
    goal: Mapped[str | None] = mapped_column(String(24))
    diet_type: Mapped[str | None] = mapped_column(String(24))
    calorie_target: Mapped[str | None] = mapped_column(EncryptedString)
    protein_target_g: Mapped[str | None] = mapped_column(EncryptedString)
    carb_target_g: Mapped[str | None] = mapped_column(EncryptedString)
    fat_target_g: Mapped[str | None] = mapped_column(EncryptedString)
    cuisines: Mapped[str | None] = mapped_column(String(512))
    spice_level: Mapped[str | None] = mapped_column(String(16))
    budget_per_meal_inr: Mapped[int | None]


class Restriction(TableBase):
    """Stated by the user only (Jain, no onion/garlic, vrat, halal...). Never inferred."""
    __tablename__ = "restrictions"
    user_id = fk("users.id", ondelete="CASCADE")
    type: Mapped[str] = mapped_column(EncryptedString)


class Allergy(TableBase):
    """Stated by the user only. Never inferred."""
    __tablename__ = "allergies"
    user_id = fk("users.id", ondelete="CASCADE")
    type: Mapped[str] = mapped_column(EncryptedString)


class LearnedPreference(TableBase):
    __tablename__ = "learned_preferences"
    __table_args__ = (CheckConstraint("kind IN ('cuisine','dish','modifier')", name="kind"),)
    user_id = fk("users.id", ondelete="CASCADE")
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(256))
    weight: Mapped[float] = mapped_column(Float, default=0)


class WeightLog(TableBase):
    __tablename__ = "weight_log"
    user_id = fk("users.id", ondelete="CASCADE")
    logged_on: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[str] = mapped_column(EncryptedString)


class ConsentRecord(TableBase):
    __tablename__ = "consent_records"
    user_id = fk("users.id", ondelete="CASCADE")
    purpose: Mapped[str] = mapped_column(String(64))  # 'health_data', 'learned_preferences'
    granted_at: Mapped[datetime] = mapped_column(TS)
    withdrawn_at: Mapped[datetime | None] = mapped_column(TS)
