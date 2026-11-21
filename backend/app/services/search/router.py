import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.search import service
from app.services.search.schemas import (CalculateIn, DishNutritionOut, DishPage, NearbyOut, PreviewOut, RestaurantPage,
                                         SearchOut, SwapsOut)

router = APIRouter(tags=["discover"])
Lat = Query(ge=-90, le=90)
Lng = Query(ge=-180, le=180)


@router.get("/preview/nearby", response_model=PreviewOut)
async def preview_nearby(lat: float = Lat, lng: float = Lng, p: Principal = access.signed_in(),
                         session: AsyncSession = Depends(get_session)):
    return await service.preview_nearby(session, lat, lng)


@router.get("/restaurants/nearby", response_model=NearbyOut)
async def nearby(lat: float = Lat, lng: float = Lng, p: Principal = access.subscriber(),
                 session: AsyncSession = Depends(get_session)):
    return await service.nearby(session, p.user_id, lat, lng)


@router.get("/restaurants/{branch_id}", response_model=RestaurantPage)
async def restaurant(branch_id: uuid.UUID, lat: float | None = Query(None, ge=-90, le=90),
                     lng: float | None = Query(None, ge=-180, le=180), p: Principal = access.subscriber(),
                     session: AsyncSession = Depends(get_session)):
    return await service.restaurant(session, p.user_id, branch_id, lat, lng)


@router.get("/search", response_model=SearchOut)
async def search(lat: float = Lat, lng: float = Lng, q: str | None = Query(None, max_length=64),
                 max_kcal: float | None = Query(None, gt=0), min_protein: float | None = Query(None, ge=0),
                 max_price: float | None = Query(None, gt=0), max_km: float | None = Query(None, gt=0, le=15),
                 trust: list[str] = Query([], max_length=3), limit: int = Query(20, ge=1, le=20), cursor: str | None = None,
                 p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    labels = {t for t in trust if t in ("verified", "declared", "estimated")}
    return await service.search(session, p.user_id, lat, lng, q, max_kcal, min_protein, max_price, max_km, labels, limit, cursor)


@router.get("/dishes/{item_id}", response_model=DishPage)
async def dish(item_id: uuid.UUID, p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    return await service.dish_page(session, p.user_id, item_id)


@router.get("/dishes/{item_id}/swaps", response_model=SwapsOut)
async def swaps(item_id: uuid.UUID, p: Principal = access.subscriber(), session: AsyncSession = Depends(get_session)):
    return await service.swaps(session, p.user_id, item_id)


@router.post("/dishes/{item_id}/calculate", response_model=DishNutritionOut)
async def calculate(item_id: uuid.UUID, body: CalculateIn, p: Principal = access.subscriber(),
                    session: AsyncSession = Depends(get_session)):
    return await service.calculate(session, p.user_id, item_id, body)


class WaitlistIn(BaseModel):
    area: str = Field(min_length=2, max_length=256)


@router.post("/preview/waitlist", status_code=204)
async def join_waitlist(body: WaitlistIn, p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    """Shown instead of a purchase button where coverage is thin."""
    await service.join_waitlist(session, p.user_id, body.area)
