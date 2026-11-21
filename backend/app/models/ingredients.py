from sqlalchemy import CheckConstraint, Float, Index, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import fk


class Ingredient(TableBase):
    __tablename__ = "ingredients"
    __table_args__ = (CheckConstraint("state IN ('raw','cooked')", name="state"), Index("ix_ingredients_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}))
    name: Mapped[str] = mapped_column(String(256), index=True)
    category: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(8))
    allergen_flags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)


class NutrientProfile(TableBase):
    """Per-100 g values. NULL means unknown, never zero (fixed rule 6)."""
    __tablename__ = "nutrient_profiles"
    __table_args__ = (
        CheckConstraint("licence_status IN ('pending','cleared','reference_only')", name="licence_status"),
    )
    ingredient_id = fk("ingredients.id", ondelete="CASCADE")
    energy_kcal: Mapped[float | None] = mapped_column(Float)
    protein_g: Mapped[float | None] = mapped_column(Float)
    carbs_g: Mapped[float | None] = mapped_column(Float)
    fat_g: Mapped[float | None] = mapped_column(Float)
    fibre_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(String(32))
    licence_status: Mapped[str] = mapped_column(String(16), default="pending")
