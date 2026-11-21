from datetime import datetime

from pydantic import BaseModel


class EntitlementOut(BaseModel):
    level: str  # preview | trial | subscriber | grace | lapsed
    source: str
    period_end: datetime | None
    grace_end: datetime | None
    trial_available: bool
    cancelled: bool = False
    can: dict = {}            # server-decided capabilities: nutrition, diary_write, diary_read, start_trial, subscribe
    display: dict = {}        # {"title", "detail"}: wording for this state, so clients never interpret levels


class Paywall(BaseModel):
    level: str
    trial_available: bool
    trial_days: int
    message: str
    price_monthly_inr: int | None = None
    price_yearly_inr: int | None = None
