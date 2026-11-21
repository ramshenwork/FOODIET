import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, NotFound
from app.core.security import keyed_hash
from app.models.identity import User
from app.services.users import repository
from app.services.users.schemas import MeOut

SELF_SERVICE_ROLES = {"consumer", "business"}  # admin is never self-assigned


def normalise_email(email: str) -> str:
    return email.strip().lower()


async def get_or_create(session: AsyncSession, email: str, role: str) -> User:
    email = normalise_email(email)
    user = await repository.by_email(session, email)
    if user:
        if user.status != "active":
            raise Forbidden("This account is not active.")
        return user
    if role not in SELF_SERVICE_ROLES:
        role = "consumer"
    return await repository.create(session, email, role)


async def get(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await repository.by_id(session, user_id)
    if not user or user.status != "active":
        raise NotFound("Account not found")
    return user


async def email_hash_for(session: AsyncSession, user_id: uuid.UUID) -> str | None:
    user = await repository.by_id(session, user_id)
    return keyed_hash(user.email) if user and user.email else None


async def me(session: AsyncSession, user_id: uuid.UUID) -> MeOut:
    from app.services.entitlement.service import access_level
    user = await get(session, user_id)
    return MeOut(id=user.id, email=user.email, role=user.role,
                 age_confirmed=user.date_of_birth_confirmed_18,
                 access_level=await access_level(session, user_id))


# ------------------------------------------------------------------ admin

from app.services.users.schemas import StatusIn, UserAdmin  # noqa: E402


async def admin_list(session: AsyncSession, q: str | None, role: str | None, limit: int = 200) -> list[UserAdmin]:
    from app.services.entitlement.service import access_level
    return [UserAdmin(id=u.id, email=u.email, role=u.role, status=u.status, created_at=u.created_at,
                      access_level=await access_level(session, u.id))
            for u in await repository.admin_list(session, q, role, limit)]


async def set_status(session: AsyncSession, admin_id: uuid.UUID, user_id: uuid.UUID, body: StatusIn) -> UserAdmin:
    from datetime import UTC, datetime
    from app.services.auth import repository as auth_repo
    from app.services.events import service as events
    user = await repository.by_id(session, user_id)
    if user is None or user.status == "deleted":
        raise NotFound("Account not found")
    if user.id == admin_id:
        raise Forbidden("You can't change your own account status.")
    user.status = body.status
    if body.status == "suspended":
        await auth_repo.revoke_all(session, user.id, datetime.now(UTC))  # signed out everywhere at once
    await events.audit(session, admin_id, f"user_{body.status}", "user", str(user.id), reason=body.reason)
    return (await admin_list(session, user.email, None, 1))[0]


# ------------------------------------------------------------------ export and deletion

async def export(session: AsyncSession, user_id: uuid.UUID) -> dict:
    from app.services.assistant import service as assistant
    from app.services.diary import service as diary
    from app.services.entitlement import service as entitlement
    from app.services.profile import service as profile
    user = await get(session, user_id)
    return {"account": {"email": user.email, "role": user.role, "created_at": user.created_at.isoformat()},
            "access": (await entitlement.get_entitlement(session, user_id)).model_dump(mode="json"),
            **(await profile.export(session, user_id)), "diary": await diary.export(session, user_id),
            "assistant": await assistant.export(session, user_id)}


async def delete_account(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Removes personal data; diary rows that feed aggregates are kept anonymised. The trial-claim hash is kept
    so the one-trial rule still holds."""
    from datetime import UTC, datetime
    from sqlalchemy import select
    from app.models.business import Business
    from app.services.auth import repository as auth_repo
    from app.services.diary import service as diary
    from app.services.events import service as events
    from app.services.profile import service as profile
    if await session.scalar(select(Business.id).where(Business.owner_user_id == user_id).limit(1)):
        raise Forbidden("You own a restaurant account. Transfer or close it before deleting your account.")
    user = await get(session, user_id)
    await profile.delete_all(session, user_id)
    from app.services.assistant import service as assistant
    await assistant.delete_all(session, user_id)
    await diary.anonymise(session, user_id)
    now = datetime.now(UTC)
    await auth_repo.revoke_all(session, user_id, now)
    user.email, user.status, user.deleted_at = None, "deleted", now
    await events.audit(session, None, "account_deleted", "user", str(user_id))
