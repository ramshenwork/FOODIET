"""Phase 8: abuse limits, request limits, headers, crawl protection, live payments, reconciliation, restaurant plan."""
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core import database, storage
from app.core.settings import get_settings
from app.main import app
from app.models.activity import AuditLog
from app.services.billing import razorpay
from app.services.billing import service as billing
from tests.conftest import sign_in
from tests.test_business import make_owner
from tests.test_consumer import HERE, _item_id, demo, diner  # noqa: F401


# ------------------------------------------------------------------ client IP, request ceilings, sizes, headers

async def test_spoofed_forwarded_for_does_not_bypass_ip_limits(client):
    for i in range(20):
        r = await client.post("/api/v1/auth/otp/request", json={"email": f"x{i}@example.com"},
                              headers={"X-Forwarded-For": f"10.0.0.{i}"})
        assert r.status_code == 202
    r = await client.post("/api/v1/auth/otp/request", json={"email": "x99@example.com"}, headers={"X-Forwarded-For": "10.9.9.9"})
    assert r.status_code == 429


async def test_per_ip_ceiling_spares_webhooks(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "API_RATE_PER_MINUTE_PER_IP", 5)
    codes = [(await client.get("/api/v1/config")).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429
    hook = await client.post("/api/v1/billing/webhooks/razorpay", content=b"{}")
    assert hook.status_code == 400   # reached the handler (bad signature), not rate limited


async def test_request_size_limits(client):
    big = b'{"email":"' + b"a" * 1_100_000 + b'@example.com"}'
    r = await client.post("/api/v1/auth/otp/request", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "request_too_large"


async def test_security_headers(client, demo):
    api = await client.get("/api/v1/config")
    for h in ("X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options", "Content-Security-Policy", "Permissions-Policy"):
        assert h in api.headers
    assert api.headers["Cache-Control"] == "no-store" and "frame-ancestors 'none'" in api.headers["Content-Security-Policy"]
    async with database.sessionmaker()() as s:
        code = await s.scalar(text("SELECT code FROM branches LIMIT 1"))
    qr = await client.get(f"/q/{code}")
    assert qr.headers["Content-Security-Policy"].startswith("default-src 'none'")   # no scripts at all on the QR page
    assert qr.headers["Cache-Control"].startswith("public")


async def test_search_input_is_data_not_sql(demo):
    d = await diner()
    r = await d.get("/search", params={**HERE, "q": "'; DROP TABLE users; --"})
    assert r.status_code == 200
    async with database.sessionmaker()() as s:
        assert await s.scalar(text("SELECT count(*) FROM users")) >= 1


def test_storage_refuses_path_traversal():
    for bad in ("local:../../.env", "local:a/b", "supabase:x"):
        with pytest.raises(storage.StorageError):
            storage.read_local(bad)


# ------------------------------------------------------------------ crawl protection

async def test_sustained_crawling_pauses_the_account(demo, monkeypatch):
    monkeypatch.setattr(get_settings(), "CRAWL_DISTINCT_DISHES_PER_HOUR", 3)
    d = await diner()
    names = ["Masala Dosa", "Idli (4)", "Plain Dosa", "Dal Tadka"]
    codes = [(await d.get(f"/dishes/{await _item_id(n)}")).status_code for n in names]
    assert codes[:3] == [200] * 3 and codes[3] == 429
    assert (await d.get("/me")).status_code == 401   # sessions ended
    async with database.sessionmaker()() as s:
        assert (await s.scalars(select(AuditLog).where(AuditLog.action == "crawl_suspected"))).first() is not None


# ------------------------------------------------------------------ server-decided capabilities

async def test_capabilities_come_from_the_server(demo):
    d = await diner()
    e = (await d.get("/me/entitlement")).json()
    assert e["can"]["nutrition"] and not e["can"]["start_trial"] and e["display"]["title"] == "Free trial"
    assert e["display"]["period"].startswith("Ends ")
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE entitlements SET period_end = now() - interval '1 day'"))
        await s.commit()
    e = (await d.get("/me/entitlement")).json()
    assert e["can"] == {"nutrition": False, "diary_write": False, "diary_read": True, "start_trial": False,
                        "subscribe": True, "cancel": False, "billing": True}


# ------------------------------------------------------------------ live payments (Razorpay stand-in)

class FakeRazorpay:
    def __init__(self):
        self.calls, self.status = [], "created"

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.calls.append((request.method, request.url.path, body))
        assert request.headers["authorization"].startswith("Basic ")
        if request.url.path == "/v1/subscriptions" and request.method == "POST":
            if body["plan_id"] == "plan_broken":
                return httpx.Response(500, json={"error": {}})
            return httpx.Response(200, json={"id": "sub_live123", "status": "created"})
        if request.url.path.endswith("/cancel"):
            return httpx.Response(200, json={"id": "sub_live123", "status": "cancelled"})
        return httpx.Response(200, json={"id": "sub_live123", "status": self.status, "current_end": self.current_end})


@pytest.fixture
def live(monkeypatch):
    s = get_settings()
    for k, v in {"PAYMENTS_MODE": "live", "RAZORPAY_KEY_ID": "rzp_test_k", "RAZORPAY_KEY_SECRET": "secret",
                 "RAZORPAY_WEBHOOK_SECRET": "whsec", "RAZORPAY_PLAN_CONSUMER_MONTHLY": "plan_month",
                 "RAZORPAY_PLAN_BUSINESS_MONTHLY": "plan_biz"}.items():
        monkeypatch.setattr(s, k, v)
    fake = FakeRazorpay()
    razorpay.set_transport(httpx.MockTransport(fake.handler))
    yield fake
    razorpay.set_transport(None)


def _signed(event: str, entity: dict) -> tuple[bytes, dict]:
    raw = json.dumps({"event": event, "payload": {"subscription": {"entity": entity}}}).encode()
    return raw, {"X-Razorpay-Signature": hmac.new(b"whsec", raw, hashlib.sha256).hexdigest(),
                 "X-Razorpay-Event-Id": f"evt_{event}", "Content-Type": "application/json"}


async def test_live_subscription_waits_for_the_webhook(demo, live):
    d = await diner(subscribe=False)
    r = (await d.post("/billing/subscribe", {"plan": "monthly"})).json()
    assert r["mode"] == "live" and r["checkout"]["subscription_id"] == "sub_live123" and r["checkout"]["key"] == "rzp_test_k"
    assert "secret" not in json.dumps(r)
    method, path, body = live.calls[0]
    assert body["plan_id"] == "plan_month" and body["notes"]["user_id"] and body["total_count"] == 120
    assert (await d.get("/me/entitlement")).json()["level"] == "preview"   # nothing granted by the client
    end = int((datetime.now(UTC) + timedelta(days=30)).timestamp())
    raw, h = _signed("subscription.activated", {"id": "sub_live123", "status": "active", "current_end": end})
    assert (await d.c.post("/api/v1/billing/webhooks/razorpay", content=raw, headers=h)).json() == {"status": "processed"}
    assert (await d.get("/me/entitlement")).json()["level"] == "subscriber"
    assert (await d.post("/billing/cancel")).status_code == 200
    assert live.calls[-1][1] == "/v1/subscriptions/sub_live123/cancel" and live.calls[-1][2] == {"cancel_at_cycle_end": 1}


async def test_live_payment_failures_are_clear(demo, live, monkeypatch):
    d = await diner(subscribe=False)
    monkeypatch.setattr(get_settings(), "RAZORPAY_PLAN_CONSUMER_YEARLY", None)
    assert (await d.post("/billing/subscribe", {"plan": "yearly"})).json()["error"]["code"] == "plan_not_configured"
    monkeypatch.setattr(get_settings(), "RAZORPAY_PLAN_CONSUMER_MONTHLY", "plan_broken")
    r = await d.post("/billing/subscribe", {"plan": "monthly"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "payment_provider_error"


async def test_reconciliation_corrects_a_missed_webhook(demo, live):
    d = await diner(subscribe=False)
    await d.post("/billing/subscribe", {"plan": "monthly"})
    live.status, live.current_end = "active", int((datetime.now(UTC) + timedelta(days=30)).timestamp())
    async with database.sessionmaker()() as s:
        assert (await billing.reconcile(s))["fixed"] == 1
        await s.commit()
    assert (await d.get("/me/entitlement")).json()["level"] == "subscriber"
    live.status = "halted"
    async with database.sessionmaker()() as s:
        await billing.reconcile(s)
        await s.commit()
        assert (await billing.reconcile(s))["fixed"] == 0   # nothing left to correct
    assert (await d.get("/me/entitlement")).json()["level"] == "lapsed"


# ------------------------------------------------------------------ restaurant paid plan (mock mode)

async def test_restaurant_plan_upgrade_and_period_end(demo):
    o = await make_owner("plan.owner@example.com", "Plan Cafe")
    r = (await o.post(f"/api/v1/business/{o.bid}/plan/subscribe")).json()
    assert r["plan"] == "paid" and r["mode"] == "mock"
    assert (await o.post(f"/api/v1/business/{o.bid}/branches", {"name": "Second"})).status_code == 201
    assert (await o.post(f"/api/v1/business/{o.bid}/team", {"email": "ed@example.com", "role": "editor"})).status_code == 201
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ec:
        s = await sign_in(ec, "ed@example.com", role="business")
        r = await ec.post(f"/api/v1/business/{o.bid}/plan/cancel", headers={"X-CSRF-Token": s["csrf_token"]})
        assert r.status_code == 403   # owner only
    after = (await o.post(f"/api/v1/business/{o.bid}/plan/cancel")).json()
    assert after["plan"] == "paid"   # paid until the period ends
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE subscriptions SET current_period_end = now() - interval '1 day' WHERE business_id = :b"), {"b": o.bid})
        await billing.reconcile(s)
        await s.commit()
    assert (await o.get(f"/api/v1/business/{o.bid}/plan")).json()["plan"] == "free"
