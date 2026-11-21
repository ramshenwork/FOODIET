import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter
from sqlalchemy import text

from app.core import access, database
from app.core.logging import RedactingFilter
from app.core.settings import Settings
from app.models.access import Entitlement
from app.services.entitlement.service import effective_level


async def test_public_config(client):
    r = await client.get("/api/v1/config")
    assert r.status_code == 200
    assert r.json()["app_name"]  # read from APP_NAME, never hard-coded
    assert "SECRET" not in r.text.upper()


async def test_health(client):
    assert (await client.get("/api/v1/health")).json() == {"status": "ok", "database": True}


async def test_unknown_route_uses_error_shape(client):
    r = await client.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("overrides", [
    {"PAYMENTS_ENABLED": True, "PAYMENTS_MODE": "mock"},
    {"PAYMENTS_MODE": "live", "TEST_FIXED_OTP": "123456"},
])
def test_production_refuses_unsafe_config(overrides):
    with pytest.raises(ValueError):
        Settings(APP_ENV="production", APP_BASE_URL="https://example.com", **{"TEST_FIXED_OTP": None, **overrides})


LIVE = dict(APP_ENV="production", APP_BASE_URL="https://example.com", PAYMENTS_ENABLED=True, PAYMENTS_MODE="live", TEST_FIXED_OTP=None,
            CALORIE_FLOOR_KCAL=1200, COVERAGE_MIN_RESTAURANTS=5, PRICE_CONSUMER_MONTHLY_INR=199, ASSISTANT_DAILY_QUESTIONS=20,
            RAZORPAY_KEY_ID="rzp_live_x", RAZORPAY_KEY_SECRET="s", RAZORPAY_WEBHOOK_SECRET="w")


def test_production_starts_with_safe_config():
    Settings(**LIVE)


@pytest.mark.parametrize("override,match", [
    ({"CALORIE_FLOOR_KCAL": None}, "CALORIE_FLOOR_KCAL"),
    ({"RAZORPAY_WEBHOOK_SECRET": None}, "Razorpay"),
    ({"SECRET_KEY": "short"}, "SECRET_KEY"),
    ({"FIELD_ENCRYPTION_KEY": "not-a-key"}, "FIELD_ENCRYPTION_KEY"),
])
def test_production_refuses_unsafe_or_incomplete_config(override, match):
    with pytest.raises(ValueError, match=match):
        Settings(**{**LIVE, **override})


def test_startup_check_rejects_undeclared_route():
    r = APIRouter()

    @r.get("/leaky")
    async def leaky():
        return {}

    with pytest.raises(RuntimeError, match="Missing"):
        access.assert_all_routes_declared([r])


def test_effective_level_transitions():
    now = datetime.now(UTC)
    assert effective_level(None, now) == "preview"
    trial = Entitlement(level="trial", source="trial", period_end=now + timedelta(days=1))
    assert effective_level(trial, now) == "trial"
    assert effective_level(trial, now + timedelta(days=2)) == "lapsed"
    sub = Entitlement(level="subscriber", source="razorpay", period_end=now, grace_end=now + timedelta(days=5))
    assert effective_level(sub, now + timedelta(days=1)) == "grace"
    assert effective_level(sub, now + timedelta(days=6)) == "lapsed"


def test_logs_redact_codes_tokens_and_emails():
    rec = logging.LogRecord("t", logging.INFO, "", 0, "otp=482913 token: abc.def user a.b@example.com code 123456", (), None)
    RedactingFilter().filter(rec)
    msg = rec.getMessage()
    assert "482913" not in msg and "abc.def" not in msg and "example.com" not in msg and "123456" not in msg


async def _exec(sql, **params):
    async with database.sessionmaker()() as s:
        res = await s.execute(text(sql), params)
        await s.commit()
        return res


async def test_recipe_versions_are_immutable():
    uid, bid, rid, vid = (uuid.uuid4() for _ in range(4))
    await _exec("INSERT INTO users (id, email, role, date_of_birth_confirmed_18, status) VALUES (:u, 'o@x.com', 'business', true, 'active')", u=uid)
    await _exec("INSERT INTO businesses (id, name, plan, owner_user_id) VALUES (:b, 'B', 'free', :u)", b=bid, u=uid)
    await _exec("INSERT INTO recipes (id, business_id, name, is_sub_recipe) VALUES (:r, :b, 'Dal', false)", r=rid, b=bid)
    await _exec("INSERT INTO recipe_versions (id, business_id, recipe_id, version_number, cooked_yield_g, status, declared_at) "
                "VALUES (:v, :b, :r, 1, 1000, 'published', now())", v=vid, b=bid, r=rid)
    with pytest.raises(Exception, match="immutable"):
        await _exec("UPDATE recipe_versions SET cooked_yield_g = 900 WHERE id = :v", v=vid)
    with pytest.raises(Exception, match="immutable"):
        await _exec("DELETE FROM recipe_versions WHERE id = :v", v=vid)


async def test_sensitive_profile_columns_are_encrypted_at_rest():
    from app.models.identity import User
    from app.models.profile import ConsumerProfile
    async with database.sessionmaker()() as s:
        u = User(email="enc@x.com")
        s.add(u)
        await s.flush()
        s.add(ConsumerProfile(user_id=u.id, height_cm="172", weight_kg="68.5"))
        await s.commit()
        raw = (await s.execute(text("SELECT height_cm, weight_kg FROM consumer_profiles"))).one()
        assert raw[0].startswith("gAAAA") and raw[1].startswith("gAAAA")  # encrypted tokens, not plain text
        prof = (await s.execute(text("SELECT id FROM consumer_profiles"))).scalar()
        s.expire_all()
        assert (await s.get(ConsumerProfile, prof)).weight_kg == "68.5"
