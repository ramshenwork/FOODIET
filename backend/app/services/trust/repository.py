"""Trust records and plausibility flags are written in phase 3 (publishing) and phase 4 (admin)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nutrition import PlausibilityFlag, TrustRecord


async def add(session: AsyncSession, obj) -> None:
    session.add(obj)
    await session.flush()


async def records(session: AsyncSession, version_id: uuid.UUID) -> list[TrustRecord]:
    return list(await session.scalars(select(TrustRecord).where(TrustRecord.recipe_version_id == version_id,
                                                                TrustRecord.revoked_at.is_(None))
                                      .order_by(TrustRecord.created_at)))


async def open_flags(session: AsyncSession, version_ids: list[uuid.UUID]) -> list[PlausibilityFlag]:
    if not version_ids:
        return []
    return list(await session.scalars(select(PlausibilityFlag).where(PlausibilityFlag.recipe_version_id.in_(version_ids),
                                                                     PlausibilityFlag.resolution == "open")))


async def flags_for(session: AsyncSession, version_id: uuid.UUID) -> list[PlausibilityFlag]:
    return list(await session.scalars(select(PlausibilityFlag).where(PlausibilityFlag.recipe_version_id == version_id)))


async def expiring(session: AsyncSession, version_ids: list[uuid.UUID], before: datetime) -> list[TrustRecord]:
    if not version_ids:
        return []
    return list(await session.scalars(select(TrustRecord).where(
        TrustRecord.recipe_version_id.in_(version_ids), TrustRecord.label == "declared",
        TrustRecord.revoked_at.is_(None), TrustRecord.expires_at < before)))
