import uuid

from pydantic import BaseModel, Field


class BranchIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    address: str | None = Field(default=None, max_length=1000)
    region: str | None = Field(default=None, max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    fssai_number: str | None = Field(default=None, pattern=r"^\d{14}$")
    cost_for_one_inr: int | None = Field(default=None, ge=0, le=100000)


class BranchOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    address: str | None
    region: str | None
    latitude: float | None
    longitude: float | None
    fssai_number: str | None
    cost_for_one_inr: int | None


class BusinessIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    first_branch: BranchIn


class BusinessUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=256)


class BusinessOut(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    plan_label: str = ""
    billing: bool = True  # False while payments are off: no upgrade or cancel controls
    my_role: str
    branches: list[BranchOut]


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str | None
    role: str


class MemberIn(BaseModel):
    email: str = Field(max_length=320)
    role: str = Field(pattern="^(manager|chef|editor)$")


class BusinessAdmin(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    branches: int
    members: int
    owner_email: str | None
