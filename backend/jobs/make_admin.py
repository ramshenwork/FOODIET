"""Grant the admin role to an account. Admin is never self-assigned through the app.

Run on the server, from backend/:  ../.venv/bin/python -m jobs.make_admin someone@example.com
"""
import asyncio
import sys

from sqlalchemy import select

from app.core import database
from app.models.identity import User
from app.services.events import service as events


async def main(email: str) -> None:
    email = email.strip().lower()
    async with database.sessionmaker()() as s:
        user = await s.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, role="admin")
            s.add(user)
        else:
            user.role = "admin"
        await s.flush()
        await events.audit(s, None, "admin_granted", "user", str(user.id), via="make_admin command")
        await s.commit()
    print("Admin role granted. The person signs in with their email code as usual.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m jobs.make_admin <email>")
    asyncio.run(main(sys.argv[1]))
