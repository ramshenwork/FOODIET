import uuid

from pydantic import BaseModel


class DishInsight(BaseModel):
    menu_item_id: uuid.UUID
    name: str
    views_7d: int
    recommend: str | None           # "82% would recommend (from 17 people)" or None below the minimum
    felt: str | None                # "Most felt it was as expected" etc., or None below the minimum


class DemandInsight(BaseModel):
    display: str                    # "23 searches within 2 km for 'paneer' under 400 kcal found nothing"
    searches: int


class InsightsOut(BaseModel):
    plan: str
    detailed: bool
    total_views_7d: int
    checkins_30d: str               # aggregate text, never per person
    recommend_rate: str | None
    dishes: list[DishInsight]       # paid plan only
    unmet_demand: list[DemandInsight]
    unmet_summary: str
    minimum_note: str
