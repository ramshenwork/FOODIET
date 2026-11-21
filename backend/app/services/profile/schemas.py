import uuid
from datetime import datetime

from pydantic import BaseModel, Field

GOALS = "^(lose|maintain|gain)$"
ACTIVITY = "^(sedentary|light|moderate|active|very_active)$"
DIETS = "^(veg|egg|non_veg)$"
RESTRICTIONS = {"jain", "no_onion_garlic", "vrat", "halal"}
ALLERGIES = {"milk", "egg", "fish", "crustacean", "tree_nut", "peanut", "gluten", "soy", "sesame", "mustard",
             "celery", "sulphite", "lupin", "mollusc"}


class ProfileIn(BaseModel):
    birth_year: int = Field(ge=1900, le=2100)
    sex_for_energy_estimate: str = Field(pattern="^(male|female)$")
    height_cm: float = Field(ge=100, le=250)
    weight_kg: float = Field(ge=30, le=300)
    activity_level: str = Field(pattern=ACTIVITY)
    goal: str = Field(pattern=GOALS)
    diet_type: str = Field(pattern=DIETS)
    restrictions: list[str] = Field(default=[], max_length=4)
    allergies: list[str] = Field(default=[], max_length=14)
    cuisines: list[str] = Field(default=[], max_length=12)
    spice_level: str | None = Field(default=None, pattern="^(mild|medium|hot)$")
    budget_per_meal_inr: int | None = Field(default=None, ge=0, le=100000)
    # User-edited targets (optional). Never accepted below the configured floor.
    calorie_target: int | None = Field(default=None, ge=0, le=10000)
    protein_target_g: int | None = Field(default=None, ge=0, le=500)
    health_data_consent: bool


class Targets(BaseModel):
    energy_kcal: int
    protein_g: int
    carbs_g: int
    fat_g: int
    is_estimate: bool = True
    floor_applied: bool
    note: str


class ProfileOut(BaseModel):
    complete: bool
    birth_year: int | None
    sex_for_energy_estimate: str | None
    height_cm: float | None
    weight_kg: float | None
    activity_level: str | None
    goal: str | None
    diet_type: str | None
    restrictions: list[str]
    allergies: list[str]
    cuisines: list[str]
    spice_level: str | None
    budget_per_meal_inr: int | None
    suggested: Targets | None       # from the engine (Mifflin-St Jeor)
    targets: Targets | None         # in effect (suggested, or the user's edit)
    calorie_floor_kcal: int | None
    consents: dict[str, bool]


class ConsentIn(BaseModel):
    purpose: str = Field(pattern="^(health_data|learned_preferences)$")
    granted: bool


class ConsentOut(BaseModel):
    purpose: str
    granted_at: datetime | None
    withdrawn_at: datetime | None


class DeleteIn(BaseModel):
    confirm: str = Field(pattern="^DELETE$")


class StatedFilters(BaseModel):
    """What other services read: stated by the user only, never inferred (fixed rules 10 and 11)."""
    user_id: uuid.UUID
    diet_type: str | None
    restrictions: set[str]
    allergies: set[str]
    targets: Targets | None
    budget_per_meal_inr: int | None


class LearnedOut(BaseModel):
    id: uuid.UUID
    kind: str
    value: str
    display: str


class FingerprintOut(BaseModel):
    consented: bool
    learned: list[LearnedOut]
    top_cuisines: list[str]
    avg_protein_eating_out: str | None
    most_repeated: list[str]
    note: str
