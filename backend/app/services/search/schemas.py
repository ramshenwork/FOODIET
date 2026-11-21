import uuid
from datetime import datetime

from pydantic import BaseModel


class Band(BaseModel):
    display: str
    label: str            # 'what our users eat here, from N meals' | 'estimated from menu'
    source: str           # logged | modelled


class PersonalLine(BaseModel):
    display: str          # e.g. "12 dishes fit your 650 kcal meal budget: 380 to 610 kcal"
    fit_count: int


class RestaurantCard(BaseModel):
    id: uuid.UUID
    name: str
    distance_km: float
    distance_display: str
    cost_for_one_inr: int | None
    typical_meal: Band | None
    fit_count: int
    fit_display: str


class DishCard(BaseModel):
    id: uuid.UUID
    name: str
    restaurant_id: uuid.UUID
    restaurant_name: str
    distance_display: str | None
    price_inr: float | None
    diet_class: str | None
    trust: dict
    energy: dict | None
    protein: dict | None
    fits: bool
    allergen_warning: str | None
    ranked: bool


class RestaurantPage(BaseModel):
    id: uuid.UUID
    name: str
    address: str | None
    distance_display: str | None
    cost_for_one_inr: int | None
    typical_meal: Band | None
    personal: PersonalLine | None
    recommend_rate: str | None
    declared_share: str
    dishes: list[DishCard]
    other_dishes: list[DishCard]     # outside your filters or allergen status unknown


class PreviewRestaurant(BaseModel):
    id: uuid.UUID
    name: str
    distance_display: str
    dish_names: list[str]
    declared_dishes: int
    total_dishes: int


class Coverage(BaseModel):
    declared_restaurants: int
    radius_km: float
    display: str
    waitlist: bool


class PreviewOut(BaseModel):
    coverage: Coverage
    restaurants: list[PreviewRestaurant]


class NearbyOut(BaseModel):
    restaurants: list[RestaurantCard]
    meal_budget_display: str | None


class SearchOut(BaseModel):
    dishes: list[DishCard]
    restaurants: list[RestaurantCard]
    next_cursor: str | None


class Serving(BaseModel):
    id: uuid.UUID | None
    label: str
    weight_g: float | None
    selected: bool


class ModifierOpt(BaseModel):
    id: uuid.UUID
    label: str


class ModifierGroupOpt(BaseModel):
    id: uuid.UUID
    name: str
    exclusive: bool
    modifiers: list[ModifierOpt]


class DishNutritionOut(BaseModel):
    trust: dict                      # label, note, meaning
    display_mode: str | None
    nutrients: dict                  # energy_kcal..sodium_mg -> nutrient object or None (unknown)
    serving_label: str | None
    share_fraction: float
    modifier_ids: list[uuid.UUID]
    fit: dict | None                 # {"fits": bool, "display": "..."}
    protein_per_100_inr: str | None
    excluded_from_ranking: bool


class DishPage(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price_inr: float | None
    diet_class: str | None
    diet_tags: list[str]
    restaurant_id: uuid.UUID
    restaurant_name: str
    nutrition: DishNutritionOut
    servings: list[Serving]
    modifier_groups: list[ModifierGroupOpt]
    ingredients: list[str]
    ingredients_label: str           # "Restaurant's recipe" | "Typical recipe for this dish"
    allergens: dict
    allergy_conflict: list[str]      # the user's stated allergies this dish declares
    last_updated: datetime | None


class CalculateIn(BaseModel):
    serving_option_id: uuid.UUID | None = None
    share_fraction: float = 1.0
    modifier_ids: list[uuid.UUID] = []


class Swap(BaseModel):
    kind: str                       # 'option' (a modifier on this dish) | 'dish' (another dish here)
    title: str
    display: str                    # e.g. "About 70 kcal less" or "170 kcal, give or take 30, instead of 430"
    modifier_id: uuid.UUID | None = None
    dish_id: uuid.UUID | None = None


class SwapsOut(BaseModel):
    swaps: list[Swap]
    note: str
