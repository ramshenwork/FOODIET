import uuid

from pydantic import BaseModel


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    age_confirmed: bool
    access_level: str


from datetime import datetime  # noqa: E402

from pydantic import Field  # noqa: E402


class UserAdmin(BaseModel):
    id: uuid.UUID
    email: str | None
    role: str
    status: str
    access_level: str
    created_at: datetime


class StatusIn(BaseModel):
    status: str = Field(pattern="^(active|suspended)$")
    reason: str = Field(min_length=1, max_length=500)
