import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.aggregates import service
from app.services.aggregates.schemas import InsightsOut

router = APIRouter(tags=["insights"])


@router.get("/business/{business_id}/insights/feedback", response_model=InsightsOut)
async def feedback_insights(business_id: uuid.UUID, p: Principal = access.business_member(),
                            session: AsyncSession = Depends(get_session)):
    """Summary on the free plan, detailed on the paid plan. Aggregates only."""
    return await service.insights(session, p.user_id, business_id)
