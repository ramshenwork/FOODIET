import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MenuChoice(BaseModel):
    id: uuid.UUID
    name: str


class PendingCheckin(BaseModel):
    meal_entry_id: uuid.UUID
    restaurant: str
    eaten_at: datetime
    dishes: list[str]
    menu: list[MenuChoice]        # for "what would you recommend here?"


class CheckinIn(BaseModel):
    meal_entry_id: uuid.UUID
    felt: str | None = Field(default=None, pattern="^(lighter|as_expected|heavier)$")
    recommend: bool | None = None
    recommended_item_id: uuid.UUID | None = None   # all empty = dismissed


class ReportIn(BaseModel):
    menu_item_id: uuid.UUID
    type: str = Field(pattern="^(menu_changed|portion_wrong|allergen_concern)$")
    detail: str | None = Field(default=None, max_length=1000)


class ReportOut(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    message: str
