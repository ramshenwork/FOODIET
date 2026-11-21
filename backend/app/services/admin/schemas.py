import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FlagOut(BaseModel):
    id: uuid.UUID
    rule: str
    message: str | None
    resolution: str
    resolution_note: str | None


class ValuesOut(BaseModel):
    version_id: uuid.UUID | None
    version_number: int | None
    energy_100g: str | None
    protein_100g: str | None
    fat_100g: str | None
    cooked_yield_g: float | None
    raw_total_g: float | None


class DisputeOut(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    business_name: str | None
    flag_id: uuid.UUID | None
    report_id: uuid.UUID | None
    detail: str
    status: str
    resolution_note: str | None
    created_at: datetime


class QueueItem(BaseModel):
    version_id: uuid.UUID
    recipe_id: uuid.UUID
    recipe_name: str
    business_id: uuid.UUID
    business_name: str
    version_number: int
    declared_at: datetime
    flags: list[FlagOut]
    new: ValuesOut
    previous: ValuesOut | None
    lines: list[str]
    disputes: list[DisputeOut]


class ResolveIn(BaseModel):
    decision: str = Field(pattern="^(approve|return)$")
    note: str | None = Field(default=None, max_length=2000)


class ResolveOut(BaseModel):
    version_id: uuid.UUID
    status: str


class VerifyIn(BaseModel):
    kind: str = Field(pattern="^(audit|lab_test)$")
    reference: str = Field(min_length=1, max_length=256)   # audit or lab report number
    notes: str | None = Field(default=None, max_length=2000)


class TrustOut(BaseModel):
    version_id: uuid.UUID
    label: str
    expires_at: datetime | None
    evidence: dict | None


class ReportOut(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    detail: str | None
    menu_item_id: uuid.UUID
    menu_item_name: str | None
    business_name: str | None
    branch_name: str | None
    created_at: datetime
    resolution_note: str | None


class ReportUpdate(BaseModel):
    status: str = Field(pattern="^(open|reviewing|resolved|dismissed)$")
    note: str | None = Field(default=None, max_length=2000)


class DisputeResolve(BaseModel):
    status: str = Field(pattern="^(upheld|rejected)$")
    note: str = Field(min_length=1, max_length=2000)


class DisputeIn(BaseModel):
    flag_id: uuid.UUID
    detail: str = Field(min_length=5, max_length=2000)


class VerifiedRow(BaseModel):
    version_id: uuid.UUID
    recipe_name: str
    business_name: str
    version_number: int
    label: str
    expires_at: datetime | None
    evidence: dict | None


class VersionHit(BaseModel):
    version_id: uuid.UUID
    recipe_name: str
    business_name: str
    version_number: int
    label: str
    note: str | None
