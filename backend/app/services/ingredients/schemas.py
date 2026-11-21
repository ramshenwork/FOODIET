import uuid

from pydantic import BaseModel, Field, field_validator


class IngredientHit(BaseModel):
    id: uuid.UUID
    name: str
    state: str
    category: str | None
    allergens: list[str]
    data_complete: bool          # every nutrient known
    licence_cleared: bool        # usable in a published calculation


class ProfileIn(BaseModel):
    energy_kcal: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fibre_g: float | None = None
    sodium_mg: float | None = None
    source: str = Field(min_length=1, max_length=64)
    source_version: str | None = Field(default=None, max_length=32)
    licence_status: str = Field(default="pending", pattern="^(pending|cleared|reference_only)$")

    @field_validator("energy_kcal", "protein_g", "carbs_g", "fat_g", "fibre_g", "sodium_mg")
    @classmethod
    def _non_negative(cls, v):
        if v is not None and (v < 0 or v > 100000):
            raise ValueError("Values must be between 0 and 100000. Leave blank when unknown.")
        return v


class IngredientIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    category: str | None = Field(default=None, max_length=64)
    state: str = Field(pattern="^(raw|cooked)$")
    allergens: list[str] = Field(default=[], max_length=14)
    profile: ProfileIn


class IngredientAdmin(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None
    state: str
    allergens: list[str]
    profile: ProfileIn | None


class LicenceIn(BaseModel):
    ingredient_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    licence_status: str = Field(pattern="^(pending|cleared|reference_only)$")
