from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import TS, fk


class User(TableBase):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('consumer','business','admin')", name="role"),
        CheckConstraint("status IN ('active','suspended','deleted')", name="status"),
    )
    email: Mapped[str | None] = mapped_column(String(320), unique=True)  # NULL after deletion
    role: Mapped[str] = mapped_column(String(16), default="consumer")
    date_of_birth_confirmed_18: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(TS)


class OtpCode(TableBase):
    __tablename__ = "otp_codes"
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(TS)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(TS)


class Session(TableBase):
    __tablename__ = "sessions"
    user_id = fk("users.id", ondelete="CASCADE")
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # Hash of the token this one replaced: presenting it again means reuse -> end all sessions.
    previous_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    device_id: Mapped[str | None] = mapped_column(String(128))
    user_agent: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(TS)
    revoked_at: Mapped[datetime | None] = mapped_column(TS)
