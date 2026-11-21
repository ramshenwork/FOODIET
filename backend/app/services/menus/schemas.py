import uuid

from pydantic import BaseModel, Field

DIETS = "^(veg|egg|non_veg)$"


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    position: int = 0


class ItemIn(BaseModel):
    branch_id: uuid.UUID
    category_id: uuid.UUID | None = None
    display_name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    price_inr: float | None = Field(default=None, ge=0, le=1000000)
    diet_class: str | None = Field(default=None, pattern=DIETS)
    canonical_dish_id: uuid.UUID | None = None
    recipe_id: uuid.UUID | None = None
    diet_tags: list[str] = Field(default=[], max_length=4)


class ItemUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    display_name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    price_inr: float | None = Field(default=None, ge=0, le=1000000)
    diet_class: str | None = Field(default=None, pattern=DIETS)
    canonical_dish_id: uuid.UUID | None = None
    recipe_id: uuid.UUID | None = None
    diet_tags: list[str] = Field(default=[], max_length=4)
    status: str = Field(default="draft", pattern="^(draft|published|hidden)$")


class ItemNutrition(BaseModel):
    trust: dict                    # {"label", "note"}
    display_mode: str | None
    energy: dict | None            # API nutrient object or None (unknown)
    protein: dict | None
    carbs: dict | None
    fat: dict | None
    serving_label: str | None
    allergens: dict


class ItemOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    category_id: uuid.UUID | None
    display_name: str
    description: str | None
    price_inr: float | None
    diet_class: str | None
    status: str
    diet_tags: list[str] = []
    canonical_dish_id: uuid.UUID | None
    canonical_dish_name: str | None
    recipe_id: uuid.UUID | None
    recipe_name: str | None
    current_recipe_version_id: uuid.UUID | None
    nutrition: ItemNutrition


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    position: int
    items: list[ItemOut]


class MenuOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    categories: list[CategoryOut]
    uncategorised: list[ItemOut]


class ImportRow(BaseModel):
    include: bool = True
    name: str = Field(min_length=1, max_length=256)
    price_inr: float | None = Field(default=None, ge=0)
    category: str | None = Field(default=None, max_length=128)
    diet_class: str | None = Field(default=None, pattern=DIETS)
    description: str | None = Field(default=None, max_length=1024)
    canonical_dish_id: uuid.UUID | None = None
    canonical_dish_name: str | None = None


class ImportOut(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    file_type: str
    review_status: str
    status: str                     # 'ready' | 'needs_ai' | 'confirmed'
    message: str | None
    rows: list[ImportRow]


class ImportUpdate(BaseModel):
    rows: list[ImportRow] = Field(max_length=500)


class ConfirmOut(BaseModel):
    created: int


class DashboardOut(BaseModel):
    menu_items: int
    published_dishes: int
    awaiting_recipes: int
    with_declared_recipe: int
    menu_completion_pct: int        # share of items with declared or estimated nutrition
    recipes_expiring_soon: int
    open_flags: int
    held_versions: int
    most_viewed: list[dict]
