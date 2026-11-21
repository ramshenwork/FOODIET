from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import JSONB, TS, business_fk, fk


class Recipe(TableBase):
    __tablename__ = "recipes"
    business_id = business_fk()
    brand_id = fk("brands.id", nullable=True)    # brand-level recipe shared by branches
    branch_id = fk("branches.id", nullable=True)  # set for a branch-owned override
    overrides_recipe_id = fk("recipes.id", nullable=True)
    name: Mapped[str] = mapped_column(String(256))
    is_sub_recipe: Mapped[bool] = mapped_column(Boolean, default=False)


class RecipeVersion(TableBase):
    """Immutable (fixed rule 4): a database trigger rejects UPDATE and DELETE."""
    __tablename__ = "recipe_versions"
    __table_args__ = (
        UniqueConstraint("recipe_id", "version_number"),
        CheckConstraint("status IN ('published','held','returned')", name="status"),
    )
    business_id = business_fk()
    recipe_id = fk("recipes.id")
    version_number: Mapped[int] = mapped_column(Integer)
    cooking_method: Mapped[str | None] = mapped_column(String(32))
    cooked_yield_g: Mapped[float] = mapped_column(Float)
    servings_per_batch: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    declared_by = fk("users.id", nullable=True)
    declared_at: Mapped[datetime] = mapped_column(TS)


class RecipeIngredient(TableBase):
    """Immutable with its version."""
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        CheckConstraint("(ingredient_id IS NULL) <> (sub_recipe_version_id IS NULL)", name="one_source"),
    )
    business_id = business_fk()
    recipe_version_id = fk("recipe_versions.id")
    ingredient_id = fk("ingredients.id", nullable=True)
    sub_recipe_version_id = fk("recipe_versions.id", nullable=True)
    quantity_g: Mapped[float] = mapped_column(Float)
    oil_retained_g: Mapped[float | None] = mapped_column(Float)  # frying oil counts retained, not added
    entered_quantity: Mapped[float | None] = mapped_column(Float)  # what the chef typed, for editing
    entered_unit: Mapped[str | None] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer, default=0)


class ServingOption(TableBase):
    __tablename__ = "serving_options"
    business_id = business_fk()
    menu_item_id = fk("menu_items.id", ondelete="CASCADE")
    label: Mapped[str] = mapped_column(String(64))
    weight_g: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))  # plate | piece | katori
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class ModifierGroup(TableBase):
    __tablename__ = "modifier_groups"
    business_id = business_fk()
    menu_item_id = fk("menu_items.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(64))
    exclusive: Mapped[bool] = mapped_column(Boolean, default=True)


class Modifier(TableBase):
    __tablename__ = "modifiers"
    __table_args__ = (CheckConstraint("kind IN ('delta','method_swap')", name="kind"),)
    business_id = business_fk()
    group_id = fk("modifier_groups.id", ondelete="CASCADE")
    label: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    # delta: [{"ingredient_id": ..., "delta_g": -10}]; method_swap: {"cooking_method": ..., "oil_retained_g": ...}
    spec: Mapped[dict] = mapped_column(JSONB)
