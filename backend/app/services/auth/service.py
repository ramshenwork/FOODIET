"""Email OTP sign-in, rotating refresh tokens, lockout, device limit."""
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.errors import AppError, Unauthorized
from app.core.security import (constant_time_equal, create_access_token, csrf_token_for, keyed_hash,
                               new_opaque_token, new_otp)
from app.core.settings import get_settings
from app.services.auth import repository
from app.services.events import service as events
from app.services.notifications.schemas import Email
from app.services.notifications import service as notifications
from app.services.users import service as users

log = logging.getLogger("app.auth")


class Issued:
    """Tokens the router turns into cookies. Never logged."""
    def __init__(self, access_token: str, refresh_token: str, csrf_token: str, user_id: uuid.UUID):
        self.access_token, self.refresh_token, self.csrf_token, self.user_id = (
            access_token, refresh_token, csrf_token, user_id)


async def request_otp(session: AsyncSession, email: str, ip: str) -> None:
    s = get_settings()
    email = users.normalise_email(email)
    rate_limit.check(f"otp-email:{keyed_hash(email)}", limit=5, window_seconds=900)
    rate_limit.check(f"otp-ip:{ip}", limit=20, window_seconds=900)
    code = new_otp(email)
    await repository.add_otp(session, keyed_hash(email), keyed_hash(f"otp:{code}"),
                             datetime.now(UTC) + timedelta(minutes=s.OTP_TTL_MINUTES))
    await notifications.send(Email(
        to=email, subject=f"Your {s.APP_NAME} sign-in code",
        text=f"Your code is {code}. It expires in {s.OTP_TTL_MINUTES} minutes."))


async def verify_otp(session: AsyncSession, email: str, code: str, role: str,
                     device_id: str | None, user_agent: str | None, ip: str) -> Issued:
    s = get_settings()
    rate_limit.check(f"otp-verify-ip:{ip}", limit=30, window_seconds=900)
    email = users.normalise_email(email)
    now = datetime.now(UTC)
    otp = await repository.latest_open_otp(session, keyed_hash(email), now)
    if otp is None:
        raise AppError(400, "code_invalid", "That code has expired. Request a new one.")
    if otp.attempts >= s.OTP_MAX_ATTEMPTS:
        raise AppError(429, "code_locked", "Too many wrong attempts. Request a new code.")
    if not constant_time_equal(otp.code_hash, keyed_hash(f"otp:{code}")):
        otp.attempts += 1
        await session.commit()  # the attempt must count even though the request fails
        left = s.OTP_MAX_ATTEMPTS - otp.attempts
        if left <= 0:
            raise AppError(429, "code_locked", "Too many wrong attempts. Request a new code.")
        raise AppError(400, "code_invalid", f"That code is not right. {left} attempts left.")
    otp.consumed_at = now

    user = await users.get_or_create(session, email, role)
    issued = await _start_session(session, user.id, user.role, device_id, user_agent, now)
    await events.track(session, "signed_in", user.id)
    return issued


async def _start_session(session: AsyncSession, user_id: uuid.UUID, role: str, device_id: str | None,
                         user_agent: str | None, now: datetime) -> Issued:
    s = get_settings()
    refresh = new_opaque_token()
    row = await repository.add_session(
        session, user_id=user_id, refresh_token_hash=keyed_hash(refresh), device_id=device_id,
        user_agent=(user_agent or "")[:512], expires_at=now + timedelta(days=s.REFRESH_TOKEN_TTL_DAYS))
    # Device limit: the oldest sessions beyond the limit are signed out.
    active = await repository.active_sessions(session, user_id, now)
    for old in active[: max(0, len(active) - s.MAX_DEVICES_PER_ACCOUNT)]:
        old.revoked_at = now
    return Issued(create_access_token(user_id, row.id, role), refresh, csrf_token_for(row.id), user_id)


async def refresh(session: AsyncSession, refresh_token: str | None) -> Issued:
    s = get_settings()
    if not refresh_token:
        raise Unauthorized()
    now = datetime.now(UTC)
    token_hash = keyed_hash(refresh_token)
    row = await repository.session_by_token(session, token_hash)
    if row is None:
        reused = await repository.session_by_previous_token(session, token_hash)
        if reused is not None:
            # An old refresh token came back: assume theft and end every session for this user.
            await repository.revoke_all(session, reused.user_id, now)
            await events.audit(session, reused.user_id, "refresh_token_reuse", "session", str(reused.id))
            await session.commit()
            log.warning("refresh token reuse detected; all sessions ended")
        raise Unauthorized("Session ended. Sign in again.")
    if row.revoked_at is not None or row.expires_at <= now:
        raise Unauthorized("Session ended. Sign in again.")
    user = await users.get(session, row.user_id)
    new_token = new_opaque_token()
    row.previous_token_hash, row.refresh_token_hash = token_hash, keyed_hash(new_token)
    row.expires_at = now + timedelta(days=s.REFRESH_TOKEN_TTL_DAYS)
    return Issued(create_access_token(user.id, row.id, user.role), new_token, csrf_token_for(row.id), user.id)


async def logout(session: AsyncSession, session_id: uuid.UUID) -> None:
    row = await repository.get_session_row(session, session_id)
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)


async def session_is_active(session: AsyncSession, session_id: uuid.UUID) -> bool:
    row = await repository.get_session_row(session, session_id)
    return bool(row and row.revoked_at is None and row.expires_at > datetime.now(UTC))
