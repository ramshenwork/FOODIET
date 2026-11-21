from pydantic import BaseModel


class PublicConfig(BaseModel):
    app_name: str
    environment: str
    payments_mode: str
    trial_days: int
    price_monthly_inr: int | None = None
    price_yearly_inr: int | None = None


class Health(BaseModel):
    status: str
    database: bool
