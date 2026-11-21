"""Daily: compare subscriptions with Razorpay and correct mismatches. Run from backend/: ../.venv/bin/python -m jobs.reconcile"""
import asyncio

from app.core import database
from app.services.billing import service as billing
from app.services.events import service as events


async def main() -> dict:
    async with database.sessionmaker()() as s:
        async with events.job_run(s, "subscription_reconcile") as run:
            result = await billing.reconcile(s)
            run.detail = result
        await s.commit()
    return result


if __name__ == "__main__":
    print(asyncio.run(main()))
