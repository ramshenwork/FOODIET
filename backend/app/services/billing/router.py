import uuid

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.billing import service
from app.services.billing.schemas import CancelOut, PlanOut, SubscribeIn, SubscribeOut, TrialIn

router = APIRouter(tags=["billing"])


@router.post("/billing/trial", status_code=204)
async def start_trial(body: TrialIn, p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    await service.start_trial(session, p.user_id, body.device_id)


@router.post("/billing/subscribe", response_model=SubscribeOut)
async def subscribe(body: SubscribeIn, p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session),
                    idempotency_key: str | None = Header(default=None, max_length=128)):
    return await service.subscribe(session, p.user_id, body, idempotency_key)


@router.post("/billing/cancel", response_model=CancelOut)
async def cancel(p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    return await service.cancel(session, p.user_id)


@router.post("/billing/webhooks/razorpay", dependencies=[access.webhook()])
async def razorpay_webhook(request: Request, session: AsyncSession = Depends(get_session),
                           x_razorpay_signature: str | None = Header(default=None),
                           x_razorpay_event_id: str | None = Header(default=None)):
    return await service.webhook(session, await request.body(), x_razorpay_signature, x_razorpay_event_id)


@router.get("/business/{business_id}/plan", response_model=PlanOut)
async def business_plan(business_id: uuid.UUID, p: Principal = access.business_member(),
                        session: AsyncSession = Depends(get_session)):
    return await service.business_plan(session, p.user_id, business_id)


@router.post("/business/{business_id}/plan/subscribe", response_model=PlanOut)
async def business_subscribe(business_id: uuid.UUID, p: Principal = access.business_member(),
                             session: AsyncSession = Depends(get_session)):
    return await service.business_subscribe(session, p.user_id, business_id)


@router.post("/business/{business_id}/plan/cancel", response_model=PlanOut)
async def business_cancel(business_id: uuid.UUID, p: Principal = access.business_member(),
                          session: AsyncSession = Depends(get_session)):
    return await service.business_cancel(session, p.user_id, business_id)
