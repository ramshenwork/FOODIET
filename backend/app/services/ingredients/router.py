from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.database import get_session
from app.services.ingredients import service
from app.services.ingredients.schemas import IngredientHit

router = APIRouter(tags=["reference"])


@router.get("/ingredients", response_model=list[IngredientHit], dependencies=[access.business_member()])
async def search_ingredients(q: str = Query(min_length=1, max_length=64), limit: int = Query(20, ge=1, le=50),
                             session: AsyncSession = Depends(get_session)):
    return await service.search(session, q, limit)
