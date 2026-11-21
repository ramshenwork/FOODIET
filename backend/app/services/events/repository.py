import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import AuditLog, Event


async def add_event(session: AsyncSession, name: str, user_id: uuid.UUID | None, properties: dict | None) -> None:
    session.add(Event(name=name, user_id=user_id, properties=properties))


async def add_audit(session: AsyncSession, actor: uuid.UUID | None, action: str,
                    target_type: str | None, target_id: str | None, detail: dict | None) -> None:
    session.add(AuditLog(actor_user_id=actor, action=action, target_type=target_type,
                         target_id=target_id, detail=detail))


from datetime import datetime  # noqa: E402

from sqlalchemy import and_, or_, select  # noqa: E402

from app.models.activity import JobRun  # noqa: E402
from app.models.identity import User  # noqa: E402


async def audit_page(session: AsyncSession, limit: int, before: tuple[datetime, uuid.UUID] | None, action: str | None):
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if before:
        ts, rid = before
        stmt = stmt.where(or_(AuditLog.created_at < ts, and_(AuditLog.created_at == ts, AuditLog.id < rid)))
    rows = await session.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1))
    return [tuple(r) for r in rows.all()]


async def job_runs(session: AsyncSession, limit: int) -> list[JobRun]:
    return list(await session.scalars(select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)))


async def add_job_run(session: AsyncSession, run: JobRun) -> JobRun:
    session.add(run)
    await session.flush()
    return run
