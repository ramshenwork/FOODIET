from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import JSONB, TS, business_fk, fk


class Menu(TableBase):
    __tablename__ = "menus"
    business_id = business_fk()
    branch_id = fk("branches.id")
    name: Mapped[str] = mapped_column(String(128))


class MenuCategory(TableBase):
    __tablename__ = "menu_categories"
    business_id = business_fk()
    menu_id = fk("menus.id", ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(128))
    position: Mapped[int] = mapped_column(Integer, default=0)


class MenuItem(TableBase):
    __tablename__ = "menu_items"
    __table_args__ = (CheckConstraint("status IN ('draft','published','hidden')", name="status"),
                      Index("ix_menu_items_branch_status", "branch_id", "status", postgresql_where="deleted_at IS NULL"),
                      Index("ix_menu_items_display_name_trgm", "display_name", postgresql_using="gin", postgresql_ops={"display_name": "gin_trgm_ops"}))
    business_id = business_fk()
    branch_id = fk("branches.id")
    category_id = fk("menu_categories.id", nullable=True)
    # Classification link only: no query may read nutrition through it.
    canonical_dish_id = fk("canonical_dishes.id", nullable=True)
    recipe_id = fk("recipes.id", nullable=True)  # the recipe this item follows (brand or branch override)
    display_name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(1024))
    price_inr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    diet_class: Mapped[str | None] = mapped_column(String(16))
    # Declared by the restaurant: 'jain', 'no_onion_garlic', 'vrat', 'halal'. A dish passes a restriction filter only if tagged.
    diet_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    current_recipe_version_id = fk("recipe_versions.id", nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(512))
    deleted_at: Mapped[datetime | None] = mapped_column(TS)


class MenuImport(TableBase):
    __tablename__ = "menu_imports"
    __table_args__ = (CheckConstraint("review_status IN ('pending','reviewed','discarded')", name="review_status"),)
    business_id = business_fk()
    branch_id = fk("branches.id")
    file_path: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(16))
    extraction_result: Mapped[dict | None] = mapped_column(JSONB)
    review_status: Mapped[str] = mapped_column(String(16), default="pending")
