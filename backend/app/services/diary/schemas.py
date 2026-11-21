import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class EntryItemIn(BaseModel):
    menu_item_id: uuid.UUID
    serving_option_id: uuid.UUID | None = None
    share_fraction: float = Field(default=1.0, gt=0, le=1)
    modifier_ids: list[uuid.UUID] = Field(default=[], max_length=10)
    component_label: str | None = Field(default=None, max_length=128)   # thali / buffet component


class EntryIn(BaseModel):
    meal_type: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    eaten_at: datetime | None = None
    items: list[EntryItemIn] = Field(min_length=1, max_length=20)


class EntryUpdate(BaseModel):
    meal_type: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    shares: dict[uuid.UUID, float] = {}     # entry item id -> new share
    remove_item_ids: list[uuid.UUID] = []


class EntryItemOut(BaseModel):
    id: uuid.UUID
    name: str
    restaurant: str | None
    component_label: str | None
    serving_label: str | None
    share_fraction: float
    share_display: str
    trust: dict
    energy: dict | None
    protein: dict | None
    allergens: dict


class EntryOut(BaseModel):
    id: uuid.UUID
    meal_type: str
    eaten_at: datetime
    restaurant: str | None
    items: list[EntryItemOut]
    energy_display: str | None


class Ring(BaseModel):
    label: str
    display: str
    fraction: float | None


class DayOut(BaseModel):
    date: date
    entries: list[EntryOut]
    totals: dict                 # nutrient -> nutrient object or None
    rings: dict | None           # {"energy": Ring, "protein": Ring, "carbs": Ring, "fat": Ring}
    energy_value: int | None     # for the counting animation
    energy_caption: str | None
    remaining_display: str | None
    read_only: bool              # lapsed users can read but not add


class WeekPoint(BaseModel):
    week_start: date
    label: str                     # "11 Nov"
    days_logged: int
    avg_energy_kcal: int | None    # per logged day
    avg_protein_g: int | None
    energy_target: int | None
    protein_target: int | None


class TrendsOut(BaseModel):
    weeks: list[WeekPoint]
    recap: dict | None             # {"title", "lines": [...]}
