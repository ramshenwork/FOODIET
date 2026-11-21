"""First-party product analytics and the audit trail."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.events import repository


async def track(session: AsyncSession, name: str, user_id: uuid.UUID | None = None, **properties) -> None:
    await repository.add_event(session, name, user_id, properties or None)


async def audit(session: AsyncSession, actor: uuid.UUID | None, action: str,
                target_type: str | None = None, target_id: str | None = None, **detail) -> None:
    await repository.add_audit(session, actor, action, target_type, target_id, detail or None)


# ------------------------------------------------------------------ admin: audit log and job runs

import base64  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from datetime import UTC, datetime  # noqa: E402

from app.models.activity import JobRun  # noqa: E402


def _cursor(ts: datetime, rid: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{ts.isoformat()}|{rid}".encode()).decode()


def _parse_cursor(c: str | None):
    if not c:
        return None
    try:
        ts, rid = base64.urlsafe_b64decode(c.encode()).decode().split("|")
        return datetime.fromisoformat(ts), uuid.UUID(rid)
    except Exception:
        return None


async def audit_page(session: AsyncSession, limit: int = 50, cursor: str | None = None, action: str | None = None) -> dict:
    rows = await repository.audit_page(session, limit, _parse_cursor(cursor), action)
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [{"id": a.id, "at": a.created_at, "actor": email or ("system" if a.actor_user_id is None else "deleted user"),
                   "action": a.action, "target_type": a.target_type, "target_id": a.target_id, "detail": a.detail}
                  for a, email in rows],
        "next_cursor": _cursor(rows[-1][0].created_at, rows[-1][0].id) if more and rows else None,
    }


async def job_runs(session: AsyncSession, limit: int = 50) -> list[dict]:
    return [{"name": j.name, "started_at": j.started_at, "finished_at": j.finished_at, "status": j.status,
             "detail": j.detail} for j in await repository.job_runs(session, limit)]


@asynccontextmanager
async def job_run(session: AsyncSession, name: str):
    """Record a scheduled job run for the health screen."""
    run = await repository.add_job_run(session, JobRun(name=name, started_at=datetime.now(UTC), status="running"))
    try:
        yield run
        run.status = "ok"
    except Exception as e:
        run.status, run.detail = "failed", {"error": type(e).__name__}
        raise
    finally:
        run.finished_at = datetime.now(UTC)
