"""Token hashing, access tokens, CSRF tokens, and column encryption."""
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.fernet import Fernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.settings import get_settings

ALGORITHM = "HS256"


def keyed_hash(value: str) -> str:
    """HMAC-SHA256 with the app secret: used for OTP codes, refresh tokens, email hashes."""
    return hmac.new(get_settings().SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def new_otp(email: str | None = None) -> str:
    """A random 6-digit code. The fixed test code applies in development, and on staging only for listed test emails."""
    s = get_settings()
    fixed = s.TEST_FIXED_OTP
    if fixed and (not s.is_staging or (email or "").lower() in s.test_signin_emails):
        return fixed
    return f"{secrets.randbelow(1_000_000):06d}"


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=s.ACCESS_TOKEN_TTL_MINUTES),
        "typ": "access",
    }
    return jwt.encode(payload, s.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == "access" else None


def csrf_token_for(session_id: uuid.UUID | str) -> str:
    """Stateless CSRF token bound to the session (double-submit, verified server-side)."""
    return keyed_hash(f"csrf:{session_id}")


def _fernet() -> Fernet:
    return Fernet(get_settings().FIELD_ENCRYPTION_KEY.encode())


class EncryptedString(TypeDecorator):
    """Column-level encryption for sensitive profile values. Stored as Fernet ciphertext."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet().encrypt(str(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _fernet().decrypt(value.encode()).decode()
