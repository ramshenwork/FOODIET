"""Protecting the paid data: detect sustained crawling of dish pages and search results.

A crawler is an account that opens far more distinct dishes (or search pages) in an hour than a person would.
When that happens the account's sessions end, the event is audited, and admins are emailed.
"""
import time
import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.settings import get_settings

_seen: dict[str, dict[str, float]] = defaultdict(dict)
WINDOW = 3600


def reset() -> None:
    _seen.clear()


def _count(key: str, item: str) -> int:
    now = time.monotonic()
    bucket = _seen[key]
    for k in [k for k, t in bucket.items() if now - t > WINDOW]:
        del bucket[k]
    bucket[item] = now
    return len(bucket)


async def note_access(session: AsyncSession, user_id: uuid.UUID, kind: str, item: str) -> None:
    limit = get_settings().CRAWL_DISTINCT_DISHES_PER_HOUR
    if _count(f"{kind}:{user_id}", item) <= limit:
        return
    from datetime import UTC, datetime
    from app.services.auth import repository as auth_repo
    from app.services.events import service as events
    from app.services.notifications import service as notifications
    from app.services.notifications.schemas import Email
    from app.services.users import repository as users_repo
    await auth_repo.revoke_all(session, user_id, datetime.now(UTC))
    await events.audit(session, user_id, "crawl_suspected", "user", str(user_id), kind=kind, distinct_per_hour=limit)
    for admin in await users_repo.admin_list(session, None, "admin", 20):
        if admin.email:
            await notifications.send(Email(to=admin.email, subject="Possible crawling paused",
                                           text=f"An account opened more than {limit} distinct {kind} items in an hour. "
                                                "Its sessions were ended. See the audit log."))
    _seen.pop(f"{kind}:{user_id}", None)
    await session.commit()   # the session revocation must stick even though this request fails
    raise AppError(429, "account_paused", "Unusual activity paused this account. Sign in again to continue.")
