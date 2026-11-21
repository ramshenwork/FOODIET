"""Admin: review queue, Verified label, reports, disputes. Reference data and accounts are handled by the
services that own those tables; the admin router calls them."""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.models.activity import Dispute
from app.models.nutrition import TrustRecord
from app.services.admin import repository
from app.services.admin.schemas import (DisputeIn, DisputeOut, DisputeResolve, FlagOut, QueueItem, ReportOut,
                                        ReportUpdate, ResolveIn, ResolveOut, TrustOut, ValuesOut, VerifiedRow, VerifyIn)
from app.services.events import service as events
from app.services.notifications import service as notifications
from app.services.notifications.schemas import Email
from app.services.nutrition import engine
from app.services.nutrition import service as nutrition
from app.services.trust import rules
from app.services.trust import service as trust


def _shown(values: dict, n: str) -> str | None:
    v = values.get(n)
    return None if v is None else rules.display_value(n, v, v, v, "single")["display"]


async def _values(session: AsyncSession, v) -> ValuesOut | None:
    if v is None:
        return None
    res = engine.calculate(await nutrition.version_recipe_data(session, v.id))
    return ValuesOut(version_id=v.id, version_number=v.version_number, energy_100g=_shown(res.per_100g, "energy_kcal"),
                     protein_100g=_shown(res.per_100g, "protein_g"), fat_100g=_shown(res.per_100g, "fat_g"),
                     cooked_yield_g=round(res.cooked_yield_g), raw_total_g=round(res.raw_total_g))


def _dispute_out(d: Dispute, business_name: str | None) -> DisputeOut:
    return DisputeOut(id=d.id, business_id=d.business_id, business_name=business_name, flag_id=d.flag_id,
                      report_id=d.report_id, detail=d.detail, status=d.status, resolution_note=d.resolution_note,
                      created_at=d.created_at)


# ------------------------------------------------------------------ review queue

async def review_queue(session: AsyncSession, limit: int = 50) -> list[QueueItem]:
    out = []
    for v, r, biz in await repository.held_versions(session, limit):
        flags = await repository.flags(session, v.id)
        data = await nutrition.version_recipe_data(session, v.id)
        lines = [f"{l.ingredient.name if l.ingredient else l.sub_recipe.name}: {l.quantity_g:.0f} g"
                 + (f" (oil kept {l.oil_retained_g:.0f} g)" if l.oil_retained_g is not None else "") for l in data.lines]
        out.append(QueueItem(
            version_id=v.id, recipe_id=r.id, recipe_name=r.name, business_id=biz.id, business_name=biz.name,
            version_number=v.version_number, declared_at=v.declared_at,
            flags=[FlagOut(id=f.id, rule=f.rule, message=(f.detail or {}).get("message"), resolution=f.resolution,
                           resolution_note=f.resolution_note) for f in flags],
            new=await _values(session, v), previous=await _values(session, await repository.previous_published(session, v)),
            lines=lines, disputes=[_dispute_out(d, n) for d, n in
                                   await repository.disputes_for_flags(session, [f.id for f in flags])]))
    return out


async def resolve_version(session: AsyncSession, admin_id: uuid.UUID, version_id: uuid.UUID, body: ResolveIn) -> ResolveOut:
    v = await repository.version(session, version_id)
    if v is None:
        raise NotFound("Recipe version not found")
    if v.status != "held":
        raise AppError(409, "not_held", "This version isn't waiting for review.")
    now = datetime.now(UTC)
    flags = [f for f in await repository.flags(session, v.id) if f.resolution == "open"]
    recipe = await repository.recipe(session, v.recipe_id)
    if body.decision == "approve":
        if await repository.newer_published(session, v):
            raise AppError(409, "newer_published", "A newer version is already published. Return this one instead.")
        try:  # never publish values built on uncleared data, even with approval
            engine.calculate(await nutrition.version_recipe_data(session, v.id), require_cleared=True)
        except engine.EngineError as e:
            raise AppError(409, "licence_not_cleared", f"{e}. Clear the data source in Reference data first.") from e
        v.status = "published"
        from app.services.recipes import service as recipes
        await recipes.publish_version(session, v.business_id, recipe, v)
    else:
        if not body.note:
            raise AppError(422, "note_required", "Tell the restaurant what to fix when returning a version.")
        v.status = "returned"
        await _tell_owner(session, v.business_id, f"Recipe {recipe.name!r} version {v.version_number} needs changes",
                          body.note)
    for f in flags:
        f.resolution = "approved" if body.decision == "approve" else "returned"
        f.resolved_by, f.resolved_at, f.resolution_note = admin_id, now, body.note
    action = "version_approved" if body.decision == "approve" else "version_returned"
    await events.audit(session, admin_id, action, "recipe_version", str(v.id), note=body.note)
    return ResolveOut(version_id=v.id, status=v.status)


async def resolve_flag(session: AsyncSession, admin_id: uuid.UUID, flag_id: uuid.UUID, body: ResolveIn) -> ResolveOut:
    """POST /admin/flags/{id}/resolve: decides the whole held version the flag belongs to."""
    f = await repository.flag(session, flag_id)
    if f is None:
        raise NotFound("Flag not found")
    return await resolve_version(session, admin_id, f.recipe_version_id, body)


async def _tell_owner(session: AsyncSession, business_id: uuid.UUID, subject: str, text: str) -> None:
    from app.services.businesses import repository as biz_repo
    from app.services.users import repository as users_repo
    biz = await biz_repo.get(session, business_id)
    owner = await users_repo.by_id(session, biz.owner_user_id) if biz else None
    if owner and owner.email:
        await notifications.send(Email(to=owner.email, subject=subject, text=text))


# ------------------------------------------------------------------ Verified label

async def verify(session: AsyncSession, admin_id: uuid.UUID, version_id: uuid.UUID, body: VerifyIn) -> TrustOut:
    from app.services.search.service import clear_cache
    clear_cache()
    v = await repository.version(session, version_id)
    if v is None:
        raise NotFound("Recipe version not found")
    if v.status != "published":
        raise AppError(409, "not_published", "Only a published version can be verified.")
    now = datetime.now(UTC)
    for rec in await trust.repository.records(session, v.id):
        if rec.label == "verified":
            rec.revoked_at = now  # a new verification replaces the old one
    expires = now + timedelta(days=trust.thresholds().expiry_days)
    evidence = body.model_dump()
    await repository.add(session, TrustRecord(recipe_version_id=v.id, label="verified", verified_by=admin_id,
                                              verified_at=now, expires_at=expires, evidence=evidence))
    await events.audit(session, admin_id, "verified_granted", "recipe_version", str(v.id), **evidence)
    return TrustOut(version_id=v.id, label="verified", expires_at=expires, evidence=evidence)


async def revoke(session: AsyncSession, admin_id: uuid.UUID, version_id: uuid.UUID, reason: str) -> TrustOut:
    from app.services.search.service import clear_cache
    clear_cache()
    recs = [r for r in await trust.repository.records(session, version_id) if r.label == "verified"]
    if not recs:
        raise AppError(409, "not_verified", "This version has no active Verified label.")
    for r in recs:
        r.revoked_at = datetime.now(UTC)
    await events.audit(session, admin_id, "verified_revoked", "recipe_version", str(version_id), reason=reason)
    effective = await trust.effective_for_version(session, version_id)
    return TrustOut(version_id=version_id, label=effective.label, expires_at=None, evidence=None)


async def verified_list(session: AsyncSession, limit: int = 100) -> list[VerifiedRow]:
    return [VerifiedRow(version_id=v.id, recipe_name=r.name, business_name=b.name, version_number=v.version_number,
                        label="verified", expires_at=t.expires_at, evidence=t.evidence)
            for t, v, r, b in await repository.verified_records(session, limit)]


# ------------------------------------------------------------------ reports and disputes

async def reports(session: AsyncSession, status: str | None, limit: int = 100) -> list[ReportOut]:
    return [ReportOut(id=r.id, type=r.type, status=r.status, detail=r.detail, menu_item_id=r.menu_item_id,
                      menu_item_name=item, business_name=biz, branch_name=branch, created_at=r.created_at,
                      resolution_note=r.resolution_note)
            for r, item, biz, branch in await repository.reports(session, status, limit)]


async def update_report(session: AsyncSession, admin_id: uuid.UUID, report_id: uuid.UUID, body: ReportUpdate) -> ReportOut:
    r = await repository.report(session, report_id)
    if r is None:
        raise NotFound("Report not found")
    r.status, r.resolution_note = body.status, body.note
    if body.status in ("resolved", "dismissed"):
        r.resolved_by, r.resolved_at = admin_id, datetime.now(UTC)
    await events.audit(session, admin_id, "report_updated", "report", str(r.id), status=body.status)
    return next(x for x in await reports(session, None, 1000) if x.id == r.id)


async def disputes(session: AsyncSession, status: str | None, limit: int = 100) -> list[DisputeOut]:
    return [_dispute_out(d, n) for d, n in await repository.disputes(session, status, limit)]


async def resolve_dispute(session: AsyncSession, admin_id: uuid.UUID, dispute_id: uuid.UUID, body: DisputeResolve) -> DisputeOut:
    d = await repository.dispute(session, dispute_id)
    if d is None:
        raise NotFound("Dispute not found")
    if d.status != "open":
        raise AppError(409, "dispute_closed", "This dispute is already decided.")
    d.status, d.resolution_note, d.resolved_by, d.resolved_at = body.status, body.note, admin_id, datetime.now(UTC)
    await events.audit(session, admin_id, "dispute_resolved", "dispute", str(d.id), status=body.status)
    await _tell_owner(session, d.business_id, "Your dispute has been reviewed", body.note)
    return _dispute_out(d, None)


async def raise_dispute(session: AsyncSession, user_id: uuid.UUID, business_id: uuid.UUID, body: DisputeIn) -> DisputeOut:
    """A restaurant explains a held recipe. It can explain, never hide or remove anything (fixed rule 14)."""
    from app.services.businesses import service as businesses
    await businesses.require(session, user_id, business_id, "edit_recipes")
    f = await repository.flag(session, body.flag_id)
    v = await repository.version(session, f.recipe_version_id) if f else None
    if f is None or v is None or v.business_id != business_id:
        raise NotFound("Check not found")
    d = await repository.add(session, Dispute(business_id=business_id, flag_id=f.id, detail=body.detail,
                                              raised_by=user_id, status="open"))
    await events.audit(session, user_id, "dispute_raised", "dispute", str(d.id))
    return _dispute_out(d, None)


async def find_versions(session: AsyncSession, q: str | None, limit: int = 50):
    from app.services.admin.schemas import VersionHit
    out = []
    for v, r, b in await repository.published_versions(session, q, limit):
        t = await trust.effective_for_version(session, v.id)
        out.append(VersionHit(version_id=v.id, recipe_name=r.name, business_name=b.name, version_number=v.version_number,
                              label=t.label, note=t.note))
    return out
