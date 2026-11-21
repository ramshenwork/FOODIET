from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.database import get_session
from app.services.system import service
from app.services.system.schemas import Health, PublicConfig

router = APIRouter(tags=["system"])


@router.get("/config", response_model=PublicConfig, dependencies=[access.public()])
async def get_config():
    return service.public_config()


@router.get("/health", response_model=Health, dependencies=[access.public()])
async def get_health(session: AsyncSession = Depends(get_session)):
    return await service.health(session)
