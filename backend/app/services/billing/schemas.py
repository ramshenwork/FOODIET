from pydantic import BaseModel, Field


class TrialIn(BaseModel):
    device_id: str = Field(min_length=8, max_length=128)


class SubscribeIn(BaseModel):
    plan: str = Field(pattern="^(monthly|yearly)$")
    ref: str | None = Field(default=None, max_length=16)   # branch code of the QR page it started from


class SubscribeOut(BaseModel):
    mode: str                 # 'mock' | 'live'
    subscription_id: str
    checkout: dict | None     # options for Razorpay Checkout in live mode; nothing secret


class CancelOut(BaseModel):
    access_until: str | None


class PlanOut(BaseModel):
    plan: str                 # free | paid
    mode: str
    subscription_id: str | None
    checkout: dict | None
    renews_until: str | None
