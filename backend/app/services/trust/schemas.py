from pydantic import BaseModel


class NutrientValue(BaseModel):
    low: float
    mid: float
    high: float
    unit: str
    display: str
    display_mode: str


class TrustOut(BaseModel):
    label: str
    note: str | None = None
