from httpx import ASGITransport, AsyncClient

from app.core.settings import get_settings
from app.main import app
from tests.conftest import sign_in

S = get_settings()
WRONG = "000000" if S.TEST_FIXED_OTP != "000000" else "111111"


async def test_sign_in_sets_session_and_me_works(client):
    body = await sign_in(client)
    assert body["user"]["email"] == "diner@example.com"
    assert body["user"]["access_level"] == "preview"
    assert {"access_token", "csrf_token"} <= set(client.cookies.keys())
    me = await client.get("/api/v1/me")
    assert me.status_code == 200 and me.json()["role"] == "consumer"
    ent = await client.get("/api/v1/me/entitlement")
    assert ent.json()["level"] == "preview" and ent.json()["trial_available"] is True


async def test_email_is_normalised(client):
    await sign_in(client, "Diner@Example.COM ".strip())
    assert (await client.get("/api/v1/me")).json()["email"] == "diner@example.com"


async def test_wrong_code_counts_attempts_then_locks(client):
    await client.post("/api/v1/auth/otp/request", json={"email": "a@example.com"})
    for i in range(S.OTP_MAX_ATTEMPTS - 1):
        r = await client.post("/api/v1/auth/otp/verify", json={"email": "a@example.com", "code": WRONG})
        assert r.status_code == 400 and r.json()["error"]["code"] == "code_invalid"
    r = await client.post("/api/v1/auth/otp/verify", json={"email": "a@example.com", "code": WRONG})
    assert r.status_code == 429 and r.json()["error"]["code"] == "code_locked"
    # Even the right code is refused once locked.
    r = await client.post("/api/v1/auth/otp/verify", json={"email": "a@example.com", "code": S.TEST_FIXED_OTP})
    assert r.status_code == 429


async def test_otp_request_rate_limited_per_email(client):
    for _ in range(5):
        assert (await client.post("/api/v1/auth/otp/request", json={"email": "b@example.com"})).status_code == 202
    r = await client.post("/api/v1/auth/otp/request", json={"email": "b@example.com"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"


async def test_unauthenticated_gets_error_shape(client):
    r = await client.get("/api/v1/me")
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "unauthorized" and err["request_id"] == r.headers["X-Request-ID"]


async def test_state_change_requires_csrf(client):
    body = await sign_in(client)
    assert (await client.post("/api/v1/auth/logout")).status_code == 403
    r = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": body["csrf_token"]})
    assert r.status_code == 200
    # Cookies cleared and the session is revoked server-side.
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_revoked_session_rejected_even_with_valid_access_token(client):
    body = await sign_in(client)
    token = client.cookies["access_token"]
    await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": body["csrf_token"]})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        r = await other.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


async def test_refresh_rotates_and_reuse_ends_all_sessions(client):
    body = await sign_in(client)
    old_refresh = client.cookies.get("refresh_token", path="/api/v1/auth")
    r = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": body["csrf_token"]})
    assert r.status_code == 200
    new_refresh = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert new_refresh and new_refresh != old_refresh
    assert (await client.get("/api/v1/me")).status_code == 200

    # Replaying the old token (as a thief would) ends every session.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as thief:
        thief.cookies.set("refresh_token", old_refresh, path="/api/v1/auth")
        thief.cookies.set("csrf_token", "x")
        r = await thief.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "x"})
        assert r.status_code == 401
    assert (await client.get("/api/v1/me")).status_code == 401


async def test_refresh_requires_csrf(client):
    await sign_in(client)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 403


async def test_device_limit_signs_out_oldest(client):
    first = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    await sign_in(first, device_id="d0")
    for i in range(1, S.MAX_DEVICES_PER_ACCOUNT + 1):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await sign_in(c, device_id=f"d{i}")
    assert (await first.get("/api/v1/me")).status_code == 401
    await first.aclose()


async def test_admin_role_cannot_be_self_assigned(client):
    r = await client.post("/api/v1/auth/otp/verify", json={"email": "x@example.com", "code": "123456", "role": "admin"})
    assert r.status_code == 422
