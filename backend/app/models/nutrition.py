from datetime import datetime

from sqlalchemy import CheckConstraint, Float, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import JSONB, TS, fk

NUTRIENTS = ("energy_kcal", "protein_g", "carbs_g", "fat_g", "fibre_g", "sodium_mg")


class NutritionResult(TableBase):
    """Engine output, stored unrounded. Each nutrient has low/mid/high; NULL = unknown."""
    __tablename__ = "nutrition_results"
    __table_args__ = (
        UniqueConstraint("recipe_version_id", "reference_recipe_id", "serving_option_id", "modifier_key",
                         postgresql_nulls_not_distinct=True),
        CheckConstraint("(recipe_version_id IS NULL) <> (reference_recipe_id IS NULL)", name="one_source"),
    )
    recipe_version_id = fk("recipe_versions.id", nullable=True)
    reference_recipe_id = fk("reference_recipes.id", nullable=True)  # Estimated values
    serving_option_id = fk("serving_options.id", nullable=True)  # NULL = per 100 g
    modifier_key: Mapped[str] = mapped_column(String(256), default="")  # sorted modifier ids
    engine_version: Mapped[str] = mapped_column(String(16))
    serving_weight_g: Mapped[float | None] = mapped_column(Float)
    display_mode: Mapped[str | None] = mapped_column(String(8))  # remembered for hysteresis
    for _n in NUTRIENTS:
        locals()[f"{_n}_low"] = mapped_column(Float, nullable=True)
        locals()[f"{_n}_mid"] = mapped_column(Float, nullable=True)
        locals()[f"{_n}_high"] = mapped_column(Float, nullable=True)
    del _n


class TrustRecord(TableBase):
    __tablename__ = "trust_records"
    __table_args__ = (
        CheckConstraint("label IN ('verified','declared','estimated','no_data')", name="label"),
    )
    recipe_version_id = fk("recipe_versions.id")
    label: Mapped[str] = mapped_column(String(16))
    verified_by = fk("users.id", nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(TS)
    expires_at: Mapped[datetime | None] = mapped_column(TS)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    revoked_at: Mapped[datetime | None] = mapped_column(TS)


class PlausibilityFlag(TableBase):
    __tablename__ = "plausibility_flags"
    __table_args__ = (
        CheckConstraint("resolution IN ('open','approved','returned')", name="resolution"),
    )
    recipe_version_id = fk("recipe_versions.id")
    rule: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSONB)
    resolution: Mapped[str] = mapped_column(String(16), default="open")
    resolved_by = fk("users.id", nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TS)
    resolution_note: Mapped[str | None] = mapped_column(Text)  # shown to the restaurant


class ReferenceRecipe(TableBase):
    """Platform recipes behind the Estimated label."""
    __tablename__ = "reference_recipes"
    name: Mapped[str] = mapped_column(String(256), unique=True)
    canonical_dish_id = fk("canonical_dishes.id", nullable=True)  # NULL for reference sub-recipes (bases)
    region: Mapped[str | None] = mapped_column(String(64))
    # [{"ingredient_id" | "sub_reference_id", "quantity_g", "oil_retained_g"}]
    ingredients: Mapped[list] = mapped_column(JSONB)
    cooked_yield_g: Mapped[float] = mapped_column(Float)
    cooking_method: Mapped[str | None] = mapped_column(String(32))
    serving_weight_g: Mapped[float | None] = mapped_column(Float)  # typical serving for this dish and region
    spread: Mapped[float | None] = mapped_column(Float)  # the reference set's own spread, if wider than the default
    allergens: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    notes: Mapped[str | None] = mapped_column(Text)
