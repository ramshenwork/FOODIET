from pydantic import BaseModel, EmailStr, Field

from app.services.users.schemas import MeOut


class OtpRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="consumer", pattern="^(consumer|business)$")


class OtpRequested(BaseModel):
    message: str
    ttl_minutes: int


class OtpVerify(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    role: str = Field(default="consumer", pattern="^(consumer|business)$")
    device_id: str | None = Field(default=None, max_length=128)


class SessionOut(BaseModel):
    user: MeOut
    csrf_token: str


class Ok(BaseModel):
    ok: bool = True
