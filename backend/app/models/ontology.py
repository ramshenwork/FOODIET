from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import fk


class CanonicalDish(TableBase):
    """For search, matching and comparison only. Holds no nutrition (fixed rule 1)."""
    __tablename__ = "canonical_dishes"
    __table_args__ = (Index("ix_canonical_dishes_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),)
    name: Mapped[str] = mapped_column(String(256), index=True)
    cuisine: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(64))
    diet_class: Mapped[str | None] = mapped_column(String(16))  # veg | egg | non_veg
    # Plausibility reference band (not served nutrition).
    expected_kcal_100g_low: Mapped[float | None] = mapped_column(Float)
    expected_kcal_100g_high: Mapped[float | None] = mapped_column(Float)
    # Dimension is fixed once the embedding model is chosen (open item); the HNSW index is added then.
    embedding = mapped_column(Vector(), nullable=True)


class DishAlias(TableBase):
    __tablename__ = "dish_aliases"
    canonical_dish_id = fk("canonical_dishes.id", ondelete="CASCADE")
    alias: Mapped[str] = mapped_column(String(256))
    language: Mapped[str | None] = mapped_column(String(16))
    transliteration: Mapped[str | None] = mapped_column(String(256))


class RegionalVariant(TableBase):
    __tablename__ = "regional_variants"
    canonical_dish_id = fk("canonical_dishes.id", ondelete="CASCADE")
    region: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(256))
