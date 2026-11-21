"""Daily: email restaurant owners 14 and 3 days before a declared recipe's 90-day confirmation runs out.

Each reminder is sent once (recorded as an event). Run from backend/:  ../.venv/bin/python -m jobs.reminders
"""
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core import database
from app.core.settings import get_settings
from app.models.activity import Event
from app.models.business import Business
from app.models.identity import User
from app.models.menus import MenuItem
from app.models.nutrition import TrustRecord
from app.services.events import service as events
from app.services.notifications import service as notifications
from app.services.notifications.schemas import Email

STAGES = {"14_days": 14, "3_days": 3}


async def run(session, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    s = get_settings()
    sent = 0
    already = {(e.properties or {}).get("key") for e in await session.scalars(
        select(Event).where(Event.name == "expiry_reminder"))}
    rows = (await session.execute(
        select(TrustRecord, MenuItem, Business, User.email)
        .join(MenuItem, MenuItem.current_recipe_version_id == TrustRecord.recipe_version_id)
        .join(Business, Business.id == MenuItem.business_id).join(User, User.id == Business.owner_user_id)
        .where(TrustRecord.label == "declared", TrustRecord.revoked_at.is_(None), MenuItem.deleted_at.is_(None),
               TrustRecord.expires_at > now, TrustRecord.expires_at <= now + timedelta(days=14)))).all()
    for rec, item, biz, email in rows:
        days_left = (rec.expires_at - now).days
        stage = "3_days" if days_left < 3 else "14_days"
        key = f"{rec.id}:{rec.expires_at.date()}:{stage}"
        if key in already or not email:
            continue
        link = f"{s.APP_BASE_URL.rstrip('/')}/business/menu/{item.id}"
        await notifications.send(Email(
            to=email, subject=f"Is {item.display_name} still made the same way?",
            text=f"The recipe for {item.display_name} at {biz.name} needs reconfirming within {STAGES[stage]} days, "
                 f"or diners will see wider ranges. If nothing changed, one click confirms it: {link}"))
        await events.track(session, "expiry_reminder", None, key=key, menu_item_id=str(item.id))
        already.add(key)
        sent += 1
    return sent


async def main() -> int:
    async with database.sessionmaker()() as s:
        async with events.job_run(s, "expiry_reminders") as job:
            n = await run(s)
            job.detail = {"sent": n}
        await s.commit()
    return n


if __name__ == "__main__":
    print(asyncio.run(main()))
