from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.services.system import repository
from app.services.system.schemas import Health, PublicConfig


def public_config() -> PublicConfig:
    return PublicConfig(**get_settings().public_config())


async def health(session: AsyncSession) -> Health:
    ok = await repository.ping(session)
    return Health(status="ok" if ok else "degraded", database=ok)
