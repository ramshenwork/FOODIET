import uuid

from pydantic import BaseModel


class NutrientValue(BaseModel):
    low: float
    mid: float
    high: float
    unit: str
    display: str
    display_mode: str


class EstimatedNutrition(BaseModel):
    reference_recipe_id: uuid.UUID
    reference_name: str
    serving_weight_g: float | None
    share_fraction: float
    trust: dict
    display_mode: str
    excluded_from_ranking: bool
    nutrients: dict[str, NutrientValue | None]   # None = unknown, shown as "Not available"
    allergens: dict


from pydantic import Field, model_validator  # noqa: E402


class RefLineIn(BaseModel):
    ingredient_id: uuid.UUID | None = None
    sub_reference_id: uuid.UUID | None = None
    quantity_g: float = Field(gt=0, le=100000)
    oil_retained_g: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _one(self):
        if (self.ingredient_id is None) == (self.sub_reference_id is None):
            raise ValueError("Each line needs an ingredient or a reference sub-recipe.")
        return self


class ReferenceIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    canonical_dish_id: uuid.UUID | None = None
    region: str | None = Field(default=None, max_length=64)
    cooking_method: str | None = Field(default=None, max_length=32)
    cooked_yield_g: float = Field(gt=0, le=1000000)
    serving_weight_g: float | None = Field(default=None, gt=0)
    spread: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[RefLineIn] = Field(min_length=1, max_length=80)


class ReferenceAdmin(BaseModel):
    id: uuid.UUID
    name: str
    canonical_dish_id: uuid.UUID | None
    region: str | None
    cooking_method: str | None
    cooked_yield_g: float
    serving_weight_g: float | None
    spread: float | None
    notes: str | None
    lines: list[dict]
    energy_100g: str | None          # calculated by the engine, for the editor
    checks: list[dict]
    licence_cleared: bool
