import uuid
from datetime import date

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.diary import service
from app.services.diary.schemas import DayOut, EntryIn, EntryOut, EntryUpdate, TrendsOut
from app.services.entitlement.service import access_level

router = APIRouter(prefix="/diary", tags=["diary"])


@router.get("", response_model=DayOut)
async def get_day(date_: date | None = Query(None, alias="date"), p: Principal = access.subscriber_or_lapsed_read(),
                  session: AsyncSession = Depends(get_session)):
    read_only = (await access_level(session, p.user_id)) == "lapsed"
    return await service.day(session, p.user_id, date_ or service.today(), read_only)


@router.post("/entries", response_model=EntryOut, status_code=201)
async def add_entry(body: EntryIn, p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session),
                    idempotency_key: str | None = Header(default=None, max_length=128)):
    return await service.add_entry(session, p.user_id, body, idempotency_key)


@router.put("/entries/{entry_id}", response_model=EntryOut)
async def update_entry(entry_id: uuid.UUID, body: EntryUpdate, p: Principal = access.subscriber(),
                       session: AsyncSession = Depends(get_session)):
    return await service.update_entry(session, p.user_id, entry_id, body)


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(entry_id: uuid.UUID, p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    await service.delete_entry(session, p.user_id, entry_id)
    return Response(status_code=204)


@router.get("/trends", response_model=TrendsOut)
async def trends(weeks: int = Query(8, ge=2, le=26), p: Principal = access.subscriber(),
                 session: AsyncSession = Depends(get_session)):
    return await service.trends(session, p.user_id, weeks)
