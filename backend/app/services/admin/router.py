"""Admin endpoints. Every request requires the admin role and is written to the audit log."""
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.core.settings import get_settings
from app.services.admin import service
from app.services.ai import service as ai
from app.services.admin.schemas import (DisputeOut, DisputeResolve, QueueItem, ReportOut, ReportUpdate, ResolveIn,
                                        ResolveOut, TrustOut, VerifiedRow, VerifyIn)
from app.services.businesses import service as businesses
from app.services.businesses.schemas import BusinessAdmin
from app.services.entitlement import service as entitlement
from app.services.events import service as events
from app.services.ingredients import service as ingredients
from app.services.ingredients.schemas import IngredientAdmin, IngredientIn, LicenceIn
from app.services.nutrition import service as nutrition
from app.services.nutrition.schemas import ReferenceAdmin, ReferenceIn
from app.services.ontology import service as ontology
from app.services.ontology.schemas import DishAdmin, DishIn
from app.services.system import service as system
from app.services.users import service as users
from app.services.users.schemas import StatusIn, UserAdmin

router = APIRouter(prefix="/admin", tags=["admin"])
Admin = access.admin


class RevokeIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


# ------------------------------------------------------------------ review queue

@router.get("/review-queue", response_model=list[QueueItem])
async def review_queue(p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await service.review_queue(session)


@router.post("/flags/{flag_id}/resolve", response_model=ResolveOut)
async def resolve_flag(flag_id: uuid.UUID, body: ResolveIn, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await service.resolve_flag(session, p.user_id, flag_id, body)


@router.post("/versions/{version_id}/resolve", response_model=ResolveOut)
async def resolve_version(version_id: uuid.UUID, body: ResolveIn, p: Principal = Admin(),
                          session: AsyncSession = Depends(get_session)):
    return await service.resolve_version(session, p.user_id, version_id, body)


# ------------------------------------------------------------------ reports and disputes

@router.get("/reports", response_model=list[ReportOut])
async def reports(status: str | None = Query(None, pattern="^(open|reviewing|resolved|dismissed)$"), p: Principal = Admin(),
                  session: AsyncSession = Depends(get_session)):
    return await service.reports(session, status)


@router.post("/reports/{report_id}", response_model=ReportOut)
async def update_report(report_id: uuid.UUID, body: ReportUpdate, p: Principal = Admin(),
                        session: AsyncSession = Depends(get_session)):
    return await service.update_report(session, p.user_id, report_id, body)


@router.get("/disputes", response_model=list[DisputeOut])
async def disputes(status: str | None = Query(None, pattern="^(open|upheld|rejected)$"), p: Principal = Admin(),
                   session: AsyncSession = Depends(get_session)):
    return await service.disputes(session, status)


@router.post("/disputes/{dispute_id}", response_model=DisputeOut)
async def resolve_dispute(dispute_id: uuid.UUID, body: DisputeResolve, p: Principal = Admin(),
                          session: AsyncSession = Depends(get_session)):
    return await service.resolve_dispute(session, p.user_id, dispute_id, body)


# ------------------------------------------------------------------ trust

@router.get("/trust", response_model=list[VerifiedRow])
async def verified(p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await service.verified_list(session)


@router.get("/versions", response_model=list[dict])
async def find_versions(q: str | None = Query(None, max_length=64), p: Principal = Admin(),
                        session: AsyncSession = Depends(get_session)):
    """Published recipe versions, to pick one for the Verified label."""
    return [h.model_dump() for h in await service.find_versions(session, q)]


@router.post("/trust/{recipe_version_id}/verify", response_model=TrustOut)
async def verify(recipe_version_id: uuid.UUID, body: VerifyIn, p: Principal = Admin(),
                 session: AsyncSession = Depends(get_session)):
    return await service.verify(session, p.user_id, recipe_version_id, body)


@router.post("/trust/{recipe_version_id}/revoke", response_model=TrustOut)
async def revoke(recipe_version_id: uuid.UUID, body: RevokeIn, p: Principal = Admin(),
                 session: AsyncSession = Depends(get_session)):
    return await service.revoke(session, p.user_id, recipe_version_id, body.reason)


# ------------------------------------------------------------------ reference data

@router.get("/ingredients", response_model=list[IngredientAdmin])
async def list_ingredients(q: str | None = None, licence: str | None = Query(None, pattern="^(pending|cleared|reference_only)$"),
                           p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await ingredients.admin_list(session, q, licence)


@router.post("/ingredients", response_model=IngredientAdmin, status_code=201)
async def create_ingredient(body: IngredientIn, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    out = await ingredients.admin_save(session, body)
    await events.audit(session, p.user_id, "ingredient_created", "ingredient", str(out.id))
    return out


@router.put("/ingredients/{ingredient_id}", response_model=IngredientAdmin)
async def update_ingredient(ingredient_id: uuid.UUID, body: IngredientIn, p: Principal = Admin(),
                            session: AsyncSession = Depends(get_session)):
    out = await ingredients.admin_save(session, body, ingredient_id)
    await events.audit(session, p.user_id, "ingredient_updated", "ingredient", str(out.id),
                       licence_status=body.profile.licence_status, source=body.profile.source)
    return out


@router.post("/ingredients/licence", response_model=dict)
async def set_licence(body: LicenceIn, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    n = await ingredients.set_licence(session, body.ingredient_ids, body.licence_status)
    await events.audit(session, p.user_id, "licence_status_changed", "ingredient", None, count=n, status=body.licence_status)
    return {"updated": n}


@router.get("/ontology", response_model=list[DishAdmin])
async def list_dishes(q: str | None = None, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await ontology.admin_list(session, q)


@router.post("/ontology", response_model=DishAdmin, status_code=201)
async def create_dish(body: DishIn, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    out = await ontology.admin_save(session, body)
    await events.audit(session, p.user_id, "dish_created", "canonical_dish", str(out.id))
    return out


@router.put("/ontology/{dish_id}", response_model=DishAdmin)
async def update_dish(dish_id: uuid.UUID, body: DishIn, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    out = await ontology.admin_save(session, body, dish_id)
    await events.audit(session, p.user_id, "dish_updated", "canonical_dish", str(out.id))
    return out


@router.get("/reference-recipes", response_model=list[ReferenceAdmin])
async def list_references(p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await nutrition.admin_references(session)


@router.get("/reference-recipes/{ref_id}", response_model=ReferenceAdmin)
async def get_reference(ref_id: uuid.UUID, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await nutrition.admin_reference(session, ref_id)


@router.post("/reference-recipes", response_model=ReferenceAdmin, status_code=201)
async def create_reference(body: ReferenceIn, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    out = await nutrition.admin_save_reference(session, body)
    await events.audit(session, p.user_id, "reference_created", "reference_recipe", str(out.id))
    return out


@router.put("/reference-recipes/{ref_id}", response_model=ReferenceAdmin)
async def update_reference(ref_id: uuid.UUID, body: ReferenceIn, p: Principal = Admin(),
                           session: AsyncSession = Depends(get_session)):
    out = await nutrition.admin_save_reference(session, body, ref_id)
    await events.audit(session, p.user_id, "reference_updated", "reference_recipe", str(out.id))
    return out


# ------------------------------------------------------------------ accounts

@router.get("/accounts/users", response_model=list[UserAdmin])
async def list_users(q: str | None = None, role: str | None = Query(None, pattern="^(consumer|business|admin)$"),
                     p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await users.admin_list(session, q, role)


@router.post("/accounts/users/{user_id}/status", response_model=UserAdmin)
async def set_user_status(user_id: uuid.UUID, body: StatusIn, p: Principal = Admin(),
                          session: AsyncSession = Depends(get_session)):
    return await users.set_status(session, p.user_id, user_id, body)


@router.get("/accounts/businesses", response_model=list[BusinessAdmin])
async def list_businesses(q: str | None = None, p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await businesses.admin_list(session, q)


@router.get("/accounts/billing", response_model=dict)
async def billing_overview(p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await entitlement.admin_overview(session)


# ------------------------------------------------------------------ audit log and health

@router.get("/audit", response_model=dict)
async def audit(limit: int = Query(50, ge=1, le=200), cursor: str | None = None, action: str | None = None,
                p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    return await events.audit_page(session, limit, cursor, action)


@router.get("/health", response_model=dict)
async def health(p: Principal = Admin(), session: AsyncSession = Depends(get_session)):
    s = get_settings()
    return {
        "database": (await system.health(session)).database,
        "environment": s.APP_ENV,
        "payments_mode": s.PAYMENTS_MODE,
        "email_configured": bool(s.EMAIL_PROVIDER),
        "storage": "supabase" if s.SUPABASE_URL and s.STORAGE_BUCKET_PRIVATE else "local (development)",
        # AI spend tracking starts with the AI module (phase 7); until then there is no spend to report.
        "ai": {"configured": bool(s.AI_PROVIDER), "monthly_budget_inr": s.AI_MONTHLY_BUDGET_INR,
               "spent_this_month_inr": round(await ai.spent_this_month(session), 2),
               "prices_set": s.AI_PRICE_INPUT_INR_PER_MTOK is not None and s.AI_PRICE_OUTPUT_INR_PER_MTOK is not None},
        "job_runs": await events.job_runs(session),
    }
