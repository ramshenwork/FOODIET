import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core import abuse, database, rate_limit
from app.core.settings import get_settings

settings = get_settings()
assert settings.TEST_DATABASE_URL, "TEST_DATABASE_URL must be set in .env"
database.configure(settings.TEST_DATABASE_URL)

from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
async def clean_db():
    settings.PAYMENTS_ENABLED = True  # the suite covers the paid path; test_free_mode switches it off
    rate_limit.reset()
    abuse.reset()
    from app.services.search.service import clear_cache
    clear_cache()
    async with database.sessionmaker()() as s:
        tables = (await s.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename NOT IN ('alembic_version','spatial_ref_sys')"))).scalars().all()
        await s.execute(text("SET session_replication_role = replica"))  # bypass immutability triggers for cleanup
        await s.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
        await s.execute(text("SET session_replication_role = DEFAULT"))
        await s.commit()
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def sign_in(client: AsyncClient, email: str = "diner@example.com", role: str = "consumer",
                  device_id: str | None = None) -> dict:
    r = await client.post("/api/v1/auth/otp/request", json={"email": email, "role": role})
    assert r.status_code == 202, r.text
    r = await client.post("/api/v1/auth/otp/verify",
                          json={"email": email, "code": settings.TEST_FIXED_OTP, "role": role, "device_id": device_id})
    assert r.status_code == 200, r.text
    return r.json()
