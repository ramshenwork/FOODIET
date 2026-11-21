"""Shared column helpers for the models package."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import mapped_column

UUIDType = UUID(as_uuid=True)
TS = DateTime(timezone=True)


def fk(target: str, nullable: bool = False, ondelete: str | None = None, index: bool = True):
    return mapped_column(UUIDType, ForeignKey(target, ondelete=ondelete), nullable=nullable, index=index)


def business_fk():
    """Every business-owned row carries business_id; repositories filter on it."""
    return fk("businesses.id", ondelete="CASCADE")


__all__ = ["JSONB", "TS", "UUIDType", "business_fk", "datetime", "fk", "uuid"]
