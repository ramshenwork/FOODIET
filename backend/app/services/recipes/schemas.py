import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

UNITS = ("g", "kg", "ml", "l", "tsp", "tbsp", "cup", "katori")
METHODS = ("simmer", "boil", "steam", "tawa", "saute", "deep_fry", "shallow_fry", "tandoor", "grill", "bake", "dum", "raw")


class LineIn(BaseModel):
    ingredient_id: uuid.UUID | None = None
    sub_recipe_id: uuid.UUID | None = None
    quantity: float = Field(gt=0, le=100000)
    unit: str = Field(default="g", pattern="^(" + "|".join(UNITS) + ")$")
    oil_retained_g: float | None = Field(default=None, ge=0, le=100000)  # frying oil only

    @model_validator(mode="after")
    def _one(self):
        if (self.ingredient_id is None) == (self.sub_recipe_id is None):
            raise ValueError("Pick an ingredient or a sub-recipe for each line.")
        return self


class VersionIn(BaseModel):
    cooking_method: str | None = Field(default=None, pattern="^(" + "|".join(METHODS) + ")$")
    cooked_yield_g: float = Field(gt=0, le=1000000)
    servings_per_batch: float | None = Field(default=None, gt=0, le=10000)
    lines: list[LineIn] = Field(min_length=1, max_length=80)


class PreviewIn(VersionIn):
    canonical_dish_id: uuid.UUID | None = None
    serving_weight_g: float | None = Field(default=None, gt=0, le=100000)


class RecipeIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    is_sub_recipe: bool = False


class OverrideIn(BaseModel):
    branch_id: uuid.UUID


class LineOut(BaseModel):
    ingredient_id: uuid.UUID | None
    sub_recipe_version_id: uuid.UUID | None
    sub_recipe_id: uuid.UUID | None = None
    name: str
    quantity_g: float
    entered_quantity: float | None
    entered_unit: str | None
    oil_retained_g: float | None


class NutritionBlock(BaseModel):
    per_batch: dict
    per_100g: dict
    per_serving: dict | None
    serving_weight_g: float | None
    trust: dict
    display_mode: str
    allergens: list[str]


class Check(BaseModel):
    rule: str
    message: str
    id: uuid.UUID | None = None            # stored flags only
    resolution: str | None = None          # open | approved | returned
    resolution_note: str | None = None     # the reviewer's note


class PreviewOut(BaseModel):
    nutrition: NutritionBlock
    checks: list[Check]
    licence_cleared: bool
    can_publish: bool


class VersionOut(BaseModel):
    id: uuid.UUID
    recipe_id: uuid.UUID
    version_number: int
    status: str                    # published | held | returned
    cooking_method: str | None
    cooked_yield_g: float
    servings_per_batch: float | None
    declared_at: datetime
    lines: list[LineOut]
    checks: list[Check]
    nutrition: NutritionBlock | None


class RecipeOut(BaseModel):
    id: uuid.UUID
    name: str
    is_sub_recipe: bool
    scope: str                     # 'brand' | 'branch'
    branch_id: uuid.UUID | None
    overrides_recipe_id: uuid.UUID | None
    latest_version: int | None
    latest_status: str | None
    published_version_id: uuid.UUID | None
    used_by_items: int


class ServingIn(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    weight_g: float = Field(gt=0, le=100000)
    unit: str = Field(pattern="^(plate|piece|katori|bowl|glass|portion)$")
    is_default: bool = False


class ServingOut(ServingIn):
    id: uuid.UUID


class DeltaIn(BaseModel):
    ingredient_id: uuid.UUID
    delta_g: float = Field(ge=-10000, le=10000)


class ModifierIn(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    kind: str = Field(pattern="^(delta|method_swap)$")
    deltas: list[DeltaIn] = []
    cooking_method: str | None = Field(default=None, pattern="^(" + "|".join(METHODS) + ")$")
    oil_retained_g: float | None = Field(default=None, ge=0)
    cooked_yield_g: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _shape(self):
        if self.kind == "delta" and not self.deltas:
            raise ValueError("A change to ingredients needs at least one ingredient and amount.")
        if self.kind == "method_swap" and not self.cooking_method:
            raise ValueError("A cooking-method change needs the new method.")
        return self


class ModifierOut(ModifierIn):
    id: uuid.UUID
    energy_change_display: str | None = None


class ModifierGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    exclusive: bool = True


class ModifierGroupOut(ModifierGroupIn):
    id: uuid.UUID
    modifiers: list[ModifierOut]


class ReconfirmOut(BaseModel):
    expires_at: datetime
