"""Nightly: per-dish and per-outlet statistics, learned preferences. Run by a Render cron job.

Run from backend/:  ../.venv/bin/python -m jobs.nightly
"""
import asyncio

from app.core import database
from app.services.aggregates import service as aggregates
from app.services.events import service as events


async def main() -> dict:
    async with database.sessionmaker()() as s:
        async with events.job_run(s, "nightly_aggregates") as run:
            result = await aggregates.recompute(s)
            run.detail = result
        await s.commit()
    return result


if __name__ == "__main__":
    print(asyncio.run(main()))
