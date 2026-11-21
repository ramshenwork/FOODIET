"""Testing build: with PAYMENTS_ENABLED off everyone has full access and no billing route runs."""
import pytest

from app.core import security
from app.core.settings import Settings, get_settings
from tests.test_business import make_owner, ref_data  # noqa: F401
from tests.test_consumer import _item_id, demo, diner  # noqa: F401

settings = get_settings()


@pytest.fixture(autouse=True)
def payments_off():
    settings.PAYMENTS_ENABLED = False
    yield
    settings.PAYMENTS_ENABLED = True


async def test_diner_gets_everything_without_a_trial(demo):
    d = await diner(subscribe=False)
    e = (await d.get("/me/entitlement")).json()
    assert e["level"] == "free" and e["can"]["nutrition"] and e["can"]["diary_write"]
    assert not e["can"]["start_trial"] and not e["can"]["subscribe"] and not e["can"]["cancel"]
    assert e["can"]["billing"] is False
    item = await _item_id("Masala Dosa")
    r = await d.get(f"/dishes/{item}")
    assert r.status_code == 200 and r.json()["nutrition"]["nutrients"]["energy_kcal"]


async def test_billing_routes_are_closed(demo):
    d = await diner(subscribe=False)
    for path, body in [("/billing/trial", {"device_id": "device-0001"}), ("/billing/subscribe", {"plan": "monthly"}),
                       ("/billing/cancel", None)]:
        r = await d.post(path, body)
        assert r.status_code == 409 and r.json()["error"]["code"] == "payments_off", path


async def test_restaurants_get_paid_features(ref_data):
    o = await make_owner("owner@free.com")
    assert o.biz["billing"] is False and "test" in o.biz["plan_label"]
    assert (await o.post(f"/api/v1/business/{o.bid}/branches", {"name": "Second"})).status_code == 201
    assert (await o.post(f"/api/v1/business/{o.bid}/team", {"email": "chef@free.com", "role": "chef"})).status_code == 201
    r = await o.post(f"/api/v1/business/{o.bid}/plan/subscribe")
    assert r.status_code == 409 and r.json()["error"]["code"] == "payments_off"


BASE = dict(FIELD_ENCRYPTION_KEY=settings.FIELD_ENCRYPTION_KEY, SECRET_KEY="s" * 40,
            APP_BASE_URL="https://test.example.com", APP_NAME="Foodiet",
            DATABASE_URL="postgresql+asyncpg://x@localhost/x", _env_file=None)


def test_production_without_payments_needs_no_prices_or_razorpay():
    Settings(APP_ENV="production", PAYMENTS_ENABLED=False, PAYMENTS_MODE="mock", CALORIE_FLOOR_KCAL=1200,
             COVERAGE_MIN_RESTAURANTS=1, ASSISTANT_DAILY_QUESTIONS=20, **BASE)


def test_staging_fixed_code_rules():
    with pytest.raises(ValueError):  # guessable code
        Settings(APP_ENV="staging", TEST_FIXED_OTP="123456", TEST_SIGNIN_EMAILS="a@b.com", **BASE)
    with pytest.raises(ValueError):  # no allowlist
        Settings(APP_ENV="staging", TEST_FIXED_OTP="583921", **BASE)
    with pytest.raises(ValueError):  # http
        Settings(APP_ENV="staging", **{**BASE, "APP_BASE_URL": "http://x.example.com"})
    Settings(APP_ENV="staging", TEST_FIXED_OTP="583921", TEST_SIGNIN_EMAILS="a@b.com", **BASE)


def test_staging_fixed_code_only_for_listed_emails(monkeypatch):
    s = Settings(APP_ENV="staging", TEST_FIXED_OTP="583921", TEST_SIGNIN_EMAILS="Tester@B.com", **BASE)
    monkeypatch.setattr(security, "get_settings", lambda: s)
    assert security.new_otp("tester@b.com") == "583921"
    assert security.new_otp("someone@else.com") != "583921"
