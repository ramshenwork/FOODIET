"""Phase 4: admin area."""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core import database
from app.main import app
from app.models.activity import AuditLog, Report
from jobs import make_admin
from tests.conftest import sign_in
from tests.test_business import dal_lines, dish_with_recipe, make_owner, ref_data  # noqa: F401


class Admin:
    def __init__(self, c, csrf):
        self.c, self.csrf = c, csrf

    async def get(self, path, **kw):
        return await self.c.get("/api/v1/admin" + path, **kw)

    async def post(self, path, body=None):
        return await self.c.post("/api/v1/admin" + path, json=body, headers={"X-CSRF-Token": self.csrf})

    async def put(self, path, body):
        return await self.c.put("/api/v1/admin" + path, json=body, headers={"X-CSRF-Token": self.csrf})


@pytest.fixture
async def admin():
    await make_admin.main("root@example.com")
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    s = await sign_in(c, "root@example.com")
    assert s["user"]["role"] == "admin"
    yield Admin(c, s["csrf_token"])
    await c.aclose()


async def held_version(ing, dish):
    o = await make_owner("owner@a.com")
    B = f"/api/v1/business/{o.bid}"
    recipe, item, v1 = await dish_with_recipe(o, ing, dish)
    v2 = (await o.post(B + f"/recipes/{recipe['id']}/versions",
                       {"cooking_method": "simmer", "cooked_yield_g": 1300, "lines": dal_lines(ing, ghee=300)})).json()
    assert v2["status"] == "held"
    return o, recipe, item, v1, v2


async def test_admin_routes_need_admin_and_are_audited(admin, client):
    await sign_in(client, "diner@example.com")
    assert (await client.get("/api/v1/admin/review-queue")).status_code == 403
    biz = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    await sign_in(biz, "owner@x.com", role="business")
    assert (await biz.get("/api/v1/admin/reports")).status_code == 403
    await biz.aclose()
    assert (await admin.get("/review-queue")).status_code == 200
    async with database.sessionmaker()() as s:
        rows = (await s.scalars(select(AuditLog).where(AuditLog.action == "admin_request"))).all()
    assert any(r.target_id == "GET /api/v1/admin/review-queue" for r in rows)


async def test_queue_shows_rule_old_and_new_values(admin, ref_data):
    ing, dish = ref_data
    o, recipe, item, v1, v2 = await held_version(ing, dish)
    q = (await admin.get("/review-queue")).json()
    assert len(q) == 1
    entry = q[0]
    assert entry["version_id"] == v2["id"] and entry["business_name"] == "Spice Route"
    assert {"energy_out_of_range", "energy_changed"} & {f["rule"] for f in entry["flags"]}
    assert entry["previous"]["version_number"] == 1 and entry["new"]["version_number"] == 2
    assert entry["previous"]["energy_100g"] != entry["new"]["energy_100g"]
    assert any(l.startswith("Ghee: 300 g") for l in entry["lines"])


async def test_return_sends_note_to_restaurant(admin, ref_data):
    ing, dish = ref_data
    o, recipe, item, v1, v2 = await held_version(ing, dish)
    assert (await admin.post(f"/versions/{v2['id']}/resolve", {"decision": "return"})).status_code == 422  # note required
    r = await admin.post(f"/versions/{v2['id']}/resolve", {"decision": "return", "note": "300 g ghee looks like a typo."})
    assert r.json()["status"] == "returned"
    versions = (await o.get(f"/api/v1/business/{o.bid}/recipes/{recipe['id']}/versions")).json()
    assert versions[1]["status"] == "returned"
    assert versions[1]["checks"][0]["resolution_note"] == "300 g ghee looks like a typo."
    menu = (await o.get(f"/api/v1/business/{o.bid}/menus", params={"branch_id": o.branch})).json()
    assert menu["uncategorised"][0]["current_recipe_version_id"] == v1["id"]   # still on v1
    assert (await admin.get("/review-queue")).json() == []


async def test_approve_publishes_and_moves_items(admin, ref_data):
    ing, dish = ref_data
    o, recipe, item, v1, v2 = await held_version(ing, dish)
    flag_id = (await admin.get("/review-queue")).json()[0]["flags"][0]["id"]
    r = await admin.post(f"/flags/{flag_id}/resolve", {"decision": "approve", "note": "Confirmed with the chef."})
    assert r.status_code == 200 and r.json()["status"] == "published"
    menu = (await o.get(f"/api/v1/business/{o.bid}/menus", params={"branch_id": o.branch})).json()
    assert menu["uncategorised"][0]["current_recipe_version_id"] == v2["id"]
    assert (await admin.post(f"/versions/{v2['id']}/resolve", {"decision": "approve"})).status_code == 409


async def test_version_content_still_immutable_after_status_change(admin, ref_data):
    ing, dish = ref_data
    _, _, _, _, v2 = await held_version(ing, dish)
    async with database.sessionmaker()() as s:
        with pytest.raises(Exception, match="immutable"):
            await s.execute(text("UPDATE recipe_versions SET cooked_yield_g = 1 WHERE id = :v"), {"v": v2["id"]})
    async with database.sessionmaker()() as s:
        with pytest.raises(Exception, match="immutable"):
            await s.execute(text("DELETE FROM recipe_versions WHERE id = :v"), {"v": v2["id"]})


async def test_cannot_approve_uncleared_data(admin, ref_data):
    ing, dish = ref_data
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE nutrient_profiles SET licence_status = 'pending'"))
        await s.commit()
    o = await make_owner("owner@a.com")
    _, _, v = await dish_with_recipe(o, ing, dish)
    assert v["status"] == "held"
    r = await admin.post(f"/versions/{v['id']}/resolve", {"decision": "approve"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "licence_not_cleared"
    # Clearing the sources in reference data makes approval possible.
    r = await admin.post("/ingredients/licence", {"ingredient_ids": list(ing.values()), "licence_status": "cleared"})
    assert r.json()["updated"] == len(ing)
    assert (await admin.post(f"/versions/{v['id']}/resolve", {"decision": "approve"})).json()["status"] == "published"


async def test_verified_label_single_mode_expiry_and_revoke(admin, ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    _, item, v = await dish_with_recipe(o, ing, dish)
    r = await admin.post(f"/trust/{v['id']}/verify", {"kind": "lab_test", "reference": "LAB-2026-0042"})
    assert r.status_code == 200 and r.json()["label"] == "verified"
    n = (await o.get(f"/api/v1/business/{o.bid}/menus", params={"branch_id": o.branch})).json()["uncategorised"][0]["nutrition"]
    assert n["trust"]["label"] == "verified" and n["display_mode"] == "single"
    assert (await admin.get("/trust")).json()[0]["evidence"]["reference"] == "LAB-2026-0042"

    async with database.sessionmaker()() as s:  # time-shift: the lab test is now 91 days old
        await s.execute(text("UPDATE trust_records SET expires_at = now() - interval '1 day' WHERE label = 'verified'"))
        await s.commit()
    n = (await o.get(f"/api/v1/business/{o.bid}/menus", params={"branch_id": o.branch})).json()["uncategorised"][0]["nutrition"]
    assert n["trust"]["label"] == "declared"

    await admin.post(f"/trust/{v['id']}/verify", {"kind": "audit", "reference": "AUD-7"})
    r = await admin.post(f"/trust/{v['id']}/revoke", {"reason": "Kitchen changed supplier"})
    assert r.json()["label"] == "declared"
    assert (await admin.post(f"/trust/{v['id']}/revoke", {"reason": "again"})).status_code == 409


async def test_reports_allergen_first_and_restaurant_cannot_hide(admin, ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    _, item, _ = await dish_with_recipe(o, ing, dish)
    async with database.sessionmaker()() as s:
        for t in ("menu_changed", "portion_wrong", "allergen_concern"):
            s.add(Report(menu_item_id=uuid.UUID(item["id"]), type=t, detail=f"{t} detail", status="open"))
        await s.commit()
    rep = (await admin.get("/reports")).json()
    assert rep[0]["type"] == "allergen_concern" and rep[0]["menu_item_name"] == "Dal Tadka"
    r = await admin.post(f"/reports/{rep[0]['id']}", {"status": "resolved", "note": "Cashew garnish added to recipe."})
    assert r.json()["status"] == "resolved"
    assert [x["type"] for x in (await admin.get("/reports")).json()][-1] == "allergen_concern"  # closed ones go last
    # No business endpoint can remove a report.
    assert (await o.c.delete(f"/api/v1/reports/{rep[1]['id']}", headers={"X-CSRF-Token": o.csrf})).status_code in (404, 405)


async def test_dispute_flow(admin, ref_data):
    ing, dish = ref_data
    o, recipe, item, v1, v2 = await held_version(ing, dish)
    flag = v2["checks"][0]
    r = await o.post(f"/api/v1/business/{o.bid}/disputes", {"flag_id": flag["id"], "detail": "We really use 300 g ghee in this batch."})
    assert r.status_code == 201
    other = await make_owner("other@b.com", "Other")
    r2 = await other.post(f"/api/v1/business/{other.bid}/disputes", {"flag_id": flag["id"], "detail": "Not ours at all"})
    assert r2.status_code == 404
    queue = (await admin.get("/review-queue")).json()
    assert queue[0]["disputes"][0]["detail"].startswith("We really use")
    d = (await admin.get("/disputes", params={"status": "open"})).json()[0]
    r = await admin.post(f"/disputes/{d['id']}", {"status": "upheld", "note": "Accepted; approving."})
    assert r.json()["status"] == "upheld"
    assert (await admin.post(f"/disputes/{d['id']}", {"status": "rejected", "note": "x"})).status_code == 409


async def test_reference_data_editing(admin, ref_data):
    ing, dish = ref_data
    r = await admin.post("/ingredients", {"name": "Moong dal, raw", "category": "pulse", "state": "raw", "allergens": [],
                                          "profile": {"energy_kcal": 347, "protein_g": 24, "carbs_g": 63, "fat_g": 1.2,
                                                      "fibre_g": None, "sodium_mg": 15, "source": "lab", "licence_status": "cleared"}})
    assert r.status_code == 201 and r.json()["profile"]["fibre_g"] is None
    assert (await admin.post("/ingredients", {"name": "Moong dal, raw", "state": "raw", "profile": {"source": "x"}})).status_code == 409
    bad = await admin.post("/ingredients", {"name": "X", "state": "raw", "allergens": ["glitter"], "profile": {"source": "x"}})
    assert bad.status_code == 422
    neg = await admin.post("/ingredients", {"name": "Y", "state": "raw", "profile": {"source": "x", "energy_kcal": -5}})
    assert neg.status_code == 422
    assert len((await admin.get("/ingredients", params={"licence": "cleared"})).json()) == len(ing) + 1

    d = await admin.post("/ontology", {"name": "Moong Dal", "cuisine": "North Indian", "diet_class": "veg",
                                       "expected_kcal_100g_low": 70, "expected_kcal_100g_high": 140,
                                       "aliases": [{"alias": "Yellow dal", "language": "en"}], "variants": []})
    assert d.status_code == 201
    inverted = await admin.put(f"/ontology/{d.json()['id']}", {**d.json(), "expected_kcal_100g_low": 200})
    assert inverted.status_code == 422

    ref = await admin.post("/reference-recipes", {
        "name": "Moong Dal", "canonical_dish_id": d.json()["id"], "cooked_yield_g": 1200, "serving_weight_g": 180,
        "lines": [{"ingredient_id": r.json()["id"], "quantity_g": 250}, {"ingredient_id": ing["Water"], "quantity_g": 1000},
                  {"ingredient_id": ing["Ghee"], "quantity_g": 25}]})
    assert ref.status_code == 201 and ref.json()["checks"] == [] and ref.json()["energy_100g"].endswith("per 100 g")
    loop = await admin.put(f"/reference-recipes/{ref.json()['id']}", {**ref.json(), "lines": [
        {"sub_reference_id": ref.json()["id"], "quantity_g": 10}]})
    assert loop.status_code == 422
    biz_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    await sign_in(biz_client, "chef@x.com", role="business")
    assert any(h["name"] == "Moong Dal" for h in (await biz_client.get("/api/v1/canonical-dishes", params={"q": "yellow dal"})).json())
    await biz_client.aclose()


async def test_accounts_suspend_signs_user_out(admin, client):
    await sign_in(client, "diner@example.com")
    users = (await admin.get("/accounts/users", params={"q": "diner"})).json()
    assert users[0]["access_level"] == "preview"
    r = await admin.post(f"/accounts/users/{users[0]['id']}/status", {"status": "suspended", "reason": "Account sharing"})
    assert r.json()["status"] == "suspended"
    assert (await client.get("/api/v1/me")).status_code == 401
    await client.post("/api/v1/auth/otp/request", json={"email": "diner@example.com"})
    from app.core.settings import get_settings
    r = await client.post("/api/v1/auth/otp/verify", json={"email": "diner@example.com", "code": get_settings().TEST_FIXED_OTP})
    assert r.status_code == 403
    me = (await admin.get("/accounts/users", params={"role": "admin"})).json()[0]
    assert (await admin.post(f"/accounts/users/{me['id']}/status", {"status": "suspended", "reason": "x"})).status_code == 403


async def test_audit_log_paginates_and_health(admin, ref_data):
    for _ in range(4):
        await admin.get("/review-queue")
    page1 = (await admin.get("/audit", params={"limit": 3})).json()
    assert len(page1["items"]) == 3 and page1["next_cursor"]
    page2 = (await admin.get("/audit", params={"limit": 3, "cursor": page1["next_cursor"]})).json()
    assert not {i["id"] for i in page1["items"]} & {i["id"] for i in page2["items"]}
    assert page1["items"][0]["actor"] == "root@example.com"
    h = (await admin.get("/health")).json()
    assert h["database"] is True and h["ai"]["configured"] is False and h["payments_mode"] == "mock"
    biz = (await admin.get("/accounts/businesses")).json()
    assert isinstance(biz, list)
    assert "trial_claims" in (await admin.get("/accounts/billing")).json()
