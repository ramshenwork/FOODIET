"""Post-visit check-ins and diner reports. Restaurants only ever see these in aggregate (fixed rule 15)."""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.errors import AppError, NotFound
from app.core.settings import get_settings
from app.models.activity import Checkin, Report
from app.services.events import service as events
from app.services.feedback import repository
from app.services.feedback.schemas import CheckinIn, MenuChoice, PendingCheckin, ReportIn, ReportOut


async def pending(session: AsyncSession, user_id: uuid.UUID) -> PendingCheckin | None:
    """One card at a time: the latest restaurant meal that ended a little while ago and has no check-in."""
    s = get_settings()
    now = datetime.now(UTC)
    entries = await repository.pending_entries(session, user_id, now - timedelta(days=s.CHECKIN_WINDOW_DAYS),
                                               now - timedelta(minutes=s.CHECKIN_DELAY_MINUTES))
    if not entries:
        return None
    e = entries[0]
    from app.services.diary import repository as diary_repo
    from app.services.search import repository as search_repo
    branch = await search_repo.branch(session, e.branch_id)
    if branch is None:
        return None
    items = await diary_repo.items(session, [e.id])
    # Only offer dishes this diner could eat: their stated diet and restrictions apply here too.
    from app.services.profile import service as profile
    from app.services.search.ranking import DIET_ALLOWS
    stated = await profile.stated(session, user_id)
    allowed = DIET_ALLOWS.get(stated.diet_type) if stated.diet_type else None
    menu = [m for m in await search_repo.published_items(session, [branch.id])
            if (allowed is None or m.diet_class in allowed) and stated.restrictions <= set(m.diet_tags or ())]
    return PendingCheckin(meal_entry_id=e.id, restaurant=branch.name, eaten_at=e.eaten_at,
                          dishes=[(i.nutrition_snapshot or {}).get("name", "Dish") for i in items],
                          menu=[MenuChoice(id=m.id, name=m.display_name) for m in menu])


async def submit(session: AsyncSession, user_id: uuid.UUID, body: CheckinIn) -> None:
    e = await repository.entry(session, user_id, body.meal_entry_id)
    if e is None or e.branch_id is None:
        raise NotFound("Meal not found")
    if await repository.checkin_for(session, e.id):
        raise AppError(409, "already_checked_in", "You've already told us about this meal.")
    if body.recommended_item_id:
        from app.services.search import repository as search_repo
        item = await search_repo.published_item(session, body.recommended_item_id)
        if item is None or item.branch_id != e.branch_id:
            raise AppError(422, "item_not_here", "Pick a dish from this restaurant's menu.")
    await repository.add(session, Checkin(meal_entry_id=e.id, felt=body.felt, recommend=body.recommend,
                                          recommended_item_id=body.recommended_item_id))
    dismissed = body.felt is None and body.recommend is None and body.recommended_item_id is None
    await events.track(session, "checkin_dismissed" if dismissed else "checkin_done", user_id)


async def report(session: AsyncSession, user_id: uuid.UUID, body: ReportIn) -> ReportOut:
    rate_limit.check(f"report:{user_id}", limit=10, window_seconds=3600)
    from app.services.search import repository as search_repo
    if await search_repo.published_item(session, body.menu_item_id) is None:
        raise NotFound("Dish not found")
    if await repository.open_report(session, user_id, body.menu_item_id, body.type):
        raise AppError(409, "already_reported", "You've already reported this; we're looking into it.")
    r = await repository.add(session, Report(user_id=user_id, menu_item_id=body.menu_item_id, type=body.type,
                                             detail=(body.detail or "").strip() or None, status="open"))
    await events.track(session, "report_filed", user_id, type=body.type)
    msg = ("Thanks. Allergen concerns are reviewed first." if body.type == "allergen_concern"
           else "Thanks. We'll check this with the restaurant.")
    return ReportOut(id=r.id, type=r.type, status=r.status, message=msg)
