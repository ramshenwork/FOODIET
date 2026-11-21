from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.database import get_session
from app.services.ontology import service
from app.services.ontology.schemas import DishHit

router = APIRouter(tags=["reference"])


@router.get("/canonical-dishes", response_model=list[DishHit], dependencies=[access.business_member()])
async def search_dishes(q: str = Query(min_length=1, max_length=64), limit: int = Query(20, ge=1, le=50),
                        session: AsyncSession = Depends(get_session)):
    return await service.search(session, q, limit)
