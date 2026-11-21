from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.feedback import service
from app.services.feedback.schemas import CheckinIn, PendingCheckin, ReportIn, ReportOut

router = APIRouter(tags=["feedback"])


@router.get("/checkins/pending", response_model=PendingCheckin | None)
async def pending(p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    return await service.pending(session, p.user_id)


@router.post("/checkins", status_code=204)
async def checkin(body: CheckinIn, p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    await service.submit(session, p.user_id, body)
    return Response(status_code=204)


@router.post("/reports", response_model=ReportOut, status_code=201)
async def report(body: ReportIn, p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    return await service.report(session, p.user_id, body)
