import uuid

from pydantic import BaseModel


class DishHit(BaseModel):
    id: uuid.UUID
    name: str
    cuisine: str | None
    region: str | None
    diet_class: str | None
    matched_alias: str | None     # the alias that matched, if it wasn't the name


from pydantic import Field  # noqa: E402


class AliasIn(BaseModel):
    alias: str = Field(min_length=1, max_length=256)
    language: str | None = Field(default=None, max_length=16)
    transliteration: str | None = Field(default=None, max_length=256)


class VariantIn(BaseModel):
    region: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=256)


class DishIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    cuisine: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=64)
    diet_class: str | None = Field(default=None, pattern="^(veg|egg|non_veg)$")
    expected_kcal_100g_low: float | None = Field(default=None, ge=0, le=1000)
    expected_kcal_100g_high: float | None = Field(default=None, ge=0, le=1000)
    aliases: list[AliasIn] = []
    variants: list[VariantIn] = []


class DishAdmin(DishIn):
    id: uuid.UUID
    reference_recipes: int
