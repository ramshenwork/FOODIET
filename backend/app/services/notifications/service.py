"""Transactional email. The provider is an open owner decision; until it is set, nothing is sent."""
import logging

from app.core.settings import get_settings
from app.services.notifications.schemas import Email

log = logging.getLogger("app.notifications")


async def send(email: Email) -> bool:
    s = get_settings()
    if not s.EMAIL_PROVIDER:
        # Never log the body: it may hold an OTP code.
        log.info("email not sent: no EMAIL_PROVIDER configured (subject=%r)", email.subject)
        return False
    raise NotImplementedError(f"Email provider {s.EMAIL_PROVIDER!r} is not wired yet")
