from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import Principal
from app.core.database import get_session
from app.services.entitlement import service
from app.services.entitlement.schemas import EntitlementOut

router = APIRouter(tags=["me"])


@router.get("/me/entitlement", response_model=EntitlementOut)
async def my_entitlement(p: Principal = access.signed_in(), session: AsyncSession = Depends(get_session)):
    return await service.get_entitlement(session, p.user_id)
