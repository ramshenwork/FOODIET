"""Businesses, brands, branches, team roles. Also the membership check every business endpoint uses."""
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Forbidden, NotFound
from app.models.business import Branch, Brand, Business, Membership
from app.services.businesses import repository
from app.services.businesses.schemas import BranchIn, BranchOut, BusinessIn, BusinessOut, MemberIn, MemberOut
from app.services.events import service as events

# What each role may do (spec: owner, manager, chef, editor; free plan is owner only).
PERMISSIONS = {
    "owner": {"view", "edit_menu", "edit_recipes", "manage_business", "manage_team"},
    "manager": {"view", "edit_menu", "edit_recipes", "manage_business"},
    "chef": {"view", "edit_recipes"},
    "editor": {"view", "edit_menu"},
}
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def paid_features(biz) -> bool:
    """Paid-plan features. While payments are off (testing) every restaurant has them."""
    from app.core.settings import get_settings
    return biz.plan == "paid" or not get_settings().PAYMENTS_ENABLED


def plan_label(biz) -> str:
    from app.core.settings import get_settings
    if not get_settings().PAYMENTS_ENABLED:
        return "Free while we test: everything unlocked"
    return "Paid plan" if biz.plan == "paid" else "Free plan"


class PlanRequired(AppError):
    def __init__(self, message: str):
        super().__init__(402, "plan_required", message, {"plan": "paid"})


async def require(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, permission: str = "view") -> Membership:
    """Non-members get 404 (they can't learn the business exists); members without the permission get 403."""
    m = await repository.membership(session, user_id, business_id)
    if m is None:
        raise NotFound("Business not found")
    if permission not in PERMISSIONS.get(m.role, set()):
        raise Forbidden("Your role can't do this.")
    return m


async def _new_code(session: AsyncSession) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        if not await repository.code_taken(session, code):
            return code
    raise AppError(500, "code_exhausted", "Could not allocate a branch code.")


def _point(lat: float | None, lng: float | None):
    if lat is None or lng is None:
        return None
    return f"SRID=4326;POINT({lng} {lat})"


def _branch_out(b: Branch, lat: float | None = None, lng: float | None = None) -> BranchOut:
    return BranchOut(id=b.id, name=b.name, code=b.code, address=b.address, region=b.region, latitude=lat,
                     longitude=lng, fssai_number=b.fssai_number, cost_for_one_inr=b.cost_for_one_inr)


async def _out(session: AsyncSession, biz: Business, role: str) -> BusinessOut:
    branches = [_branch_out(b, lat, lng) for b, lat, lng in await repository.branches(session, biz.id)]
    from app.core.settings import get_settings
    return BusinessOut(id=biz.id, name=biz.name, plan=biz.plan, plan_label=plan_label(biz),
                       billing=get_settings().PAYMENTS_ENABLED, my_role=role, branches=branches)


async def create(session: AsyncSession, user_id: uuid.UUID, body: BusinessIn) -> BusinessOut:
    biz = await repository.add(session, Business(name=body.name, plan="free", owner_user_id=user_id))
    await repository.add(session, Membership(user_id=user_id, business_id=biz.id, role="owner"))
    brand = await repository.add(session, Brand(business_id=biz.id, name=body.name))
    await _add_branch(session, biz, brand, body.first_branch)
    await events.audit(session, user_id, "business_created", "business", str(biz.id))
    return await _out(session, biz, "owner")


async def _add_branch(session: AsyncSession, biz: Business, brand: Brand, b: BranchIn) -> Branch:
    return await repository.add(session, Branch(
        business_id=biz.id, brand_id=brand.id, name=b.name, code=await _new_code(session), address=b.address,
        region=(b.region or "").strip().lower() or None, location=_point(b.latitude, b.longitude),
        fssai_number=b.fssai_number, cost_for_one_inr=b.cost_for_one_inr))


async def mine(session: AsyncSession, user_id: uuid.UUID) -> list[BusinessOut]:
    return [await _out(session, biz, role) for biz, role in await repository.businesses_for(session, user_id)]


async def get(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID) -> BusinessOut:
    m = await require(session, user_id, business_id)
    return await _out(session, await repository.get(session, business_id), m.role)


async def update(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, name: str) -> BusinessOut:
    m = await require(session, user_id, business_id, "manage_business")
    biz = await repository.get(session, business_id)
    biz.name = name
    return await _out(session, biz, m.role)


async def add_branch(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, body: BranchIn) -> BranchOut:
    await require(session, user_id, business_id, "manage_business")
    biz = await repository.get(session, business_id)
    if not paid_features(biz) and await repository.count_branches(session, business_id) >= 1:
        raise PlanRequired("The free plan includes one branch. More branches need the paid plan.")
    b = await _add_branch(session, biz, await repository.default_brand(session, business_id), body)
    return _branch_out(b, body.latitude, body.longitude)


async def update_branch(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, branch_id: uuid.UUID,
                        body: BranchIn) -> BranchOut:
    await require(session, user_id, business_id, "manage_business")
    b = await repository.branch(session, business_id, branch_id)
    if b is None:
        raise NotFound("Branch not found")
    b.name, b.address, b.fssai_number, b.cost_for_one_inr = body.name, body.address, body.fssai_number, body.cost_for_one_inr
    b.region = (body.region or "").strip().lower() or None
    if body.latitude is not None and body.longitude is not None:
        b.location = _point(body.latitude, body.longitude)
    return _branch_out(b, body.latitude, body.longitude)


async def branch_of_member(session: AsyncSession, user_id: uuid.UUID, branch_id: uuid.UUID) -> Branch:
    b = await repository.branch_for_member(session, branch_id, user_id)
    if b is None:
        raise NotFound("Branch not found")
    return b


async def branch_for_business(session: AsyncSession, business_id: uuid.UUID, branch_id: uuid.UUID) -> Branch:
    b = await repository.branch(session, business_id, branch_id)
    if b is None:
        raise NotFound("Branch not found")
    return b


async def branch_by_code(session: AsyncSession, code: str) -> Branch | None:
    return await repository.branch_by_code(session, code)


async def team(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID) -> list[MemberOut]:
    await require(session, user_id, business_id)
    return [MemberOut(user_id=m.user_id, email=email, role=m.role) for m, email in await repository.members(session, business_id)]


async def add_member(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, body: MemberIn) -> MemberOut:
    await require(session, user_id, business_id, "manage_team")
    biz = await repository.get(session, business_id)
    if not paid_features(biz):
        raise PlanRequired("Team roles need the paid plan. The free plan is owner only.")
    from app.services.users import service as users
    member_user = await users.get_or_create(session, body.email, "business")
    if await repository.membership(session, member_user.id, business_id):
        raise AppError(409, "already_member", "That person is already on the team.")
    await repository.add(session, Membership(user_id=member_user.id, business_id=business_id, role=body.role))
    await events.audit(session, user_id, "member_added", "business", str(business_id), role=body.role)
    return MemberOut(user_id=member_user.id, email=member_user.email, role=body.role)


async def admin_list(session: AsyncSession, q: str | None, limit: int = 200):
    from sqlalchemy import select
    from app.models.identity import User
    from app.services.businesses.schemas import BusinessAdmin
    stmt = select(Business, User.email).join(User, User.id == Business.owner_user_id)
    if q:
        stmt = stmt.where(Business.name.ilike(f"%{q}%"))
    out = []
    for biz, email in (await session.execute(stmt.order_by(Business.created_at.desc()).limit(limit))).all():
        out.append(BusinessAdmin(id=biz.id, name=biz.name, plan=biz.plan, owner_email=email,
                                 branches=await repository.count_branches(session, biz.id),
                                 members=len(await repository.members(session, biz.id))))
    return out
