import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import OtpCode, Session


async def add_otp(session: AsyncSession, email_hash: str, code_hash: str, expires_at: datetime) -> None:
    # A new code replaces any outstanding one.
    await session.execute(update(OtpCode).where(OtpCode.email_hash == email_hash, OtpCode.consumed_at.is_(None))
                          .values(consumed_at=func.now()))
    session.add(OtpCode(email_hash=email_hash, code_hash=code_hash, expires_at=expires_at))


async def latest_open_otp(session: AsyncSession, email_hash: str, now: datetime) -> OtpCode | None:
    return await session.scalar(
        select(OtpCode).where(OtpCode.email_hash == email_hash, OtpCode.consumed_at.is_(None),
                              OtpCode.expires_at > now).order_by(OtpCode.created_at.desc()).limit(1))


async def add_session(session: AsyncSession, **fields) -> Session:
    s = Session(**fields)
    session.add(s)
    await session.flush()
    return s


async def session_by_token(session: AsyncSession, token_hash: str) -> Session | None:
    return await session.scalar(select(Session).where(Session.refresh_token_hash == token_hash))


async def session_by_previous_token(session: AsyncSession, token_hash: str) -> Session | None:
    return await session.scalar(select(Session).where(Session.previous_token_hash == token_hash))


async def get_session_row(session: AsyncSession, session_id: uuid.UUID) -> Session | None:
    return await session.get(Session, session_id)


async def active_sessions(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> list[Session]:
    rows = await session.scalars(select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None),
                                                       Session.expires_at > now).order_by(Session.created_at))
    return list(rows)


async def revoke_all(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> None:
    await session.execute(update(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
                          .values(revoked_at=now))
