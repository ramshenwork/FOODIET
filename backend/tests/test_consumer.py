"""Phase 5: consumer core acceptance checks."""
import hashlib
import hmac
import json
import uuid
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core import database
from app.core.settings import get_settings
from app.main import app
from app.models.activity import OutletStats
from app.models.business import Branch
from jobs import dev_clear_placeholders, dev_seed_demo, seed_reference
from tests.conftest import sign_in

HERE = {"lat": 17.4200, "lng": 78.4600}
NUTRITION_WORDS = ("energy", "kcal", "protein", "carb", "fat", "fibre", "sodium", "nutri")


@pytest.fixture
async def demo():
    async with database.sessionmaker()() as s:
        ings = await seed_reference.seed_ingredients(s)
        dishes = await seed_reference.seed_dishes(s)
        await seed_reference.seed_references(s, ings, dishes)
        await dev_clear_placeholders.clear(s)
        await s.commit()
    await dev_seed_demo.main()


class Diner:
    def __init__(self, c, csrf):
        self.c, self.csrf = c, csrf

    async def get(self, path, **kw):
        return await self.c.get("/api/v1" + path, **kw)

    async def post(self, path, body=None, headers=None):
        return await self.c.post("/api/v1" + path, json=body, headers={"X-CSRF-Token": self.csrf, **(headers or {})})

    async def put(self, path, body):
        return await self.c.put("/api/v1" + path, json=body, headers={"X-CSRF-Token": self.csrf})

    async def delete(self, path, body=None):
        return await self.c.request("DELETE", "/api/v1" + path, json=body, headers={"X-CSRF-Token": self.csrf})


PROFILE = {"birth_year": 1990, "sex_for_energy_estimate": "female", "height_cm": 162, "weight_kg": 60,
           "activity_level": "light", "goal": "lose", "diet_type": "non_veg", "restrictions": [], "allergies": [],
           "cuisines": ["South Indian"], "spice_level": "medium", "budget_per_meal_inr": 400, "health_data_consent": True}


async def diner(email="diner@example.com", device="device-0001", subscribe=True, **profile) -> Diner:
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    s = await sign_in(c, email)
    d = Diner(c, s["csrf_token"])
    if subscribe:
        assert (await d.post("/billing/trial", {"device_id": device})).status_code == 204
    r = await d.put("/me/profile", {**PROFILE, **profile})
    assert r.status_code == 200, r.text
    return d


def keys(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys(v)


async def _item_id(name):
    async with database.sessionmaker()() as s:
        return str(await s.scalar(text("SELECT id FROM menu_items WHERE display_name = :n AND status='published'"), {"n": name}))


# ------------------------------------------------------------------ access levels and preview

async def test_preview_responses_contain_no_nutrition(demo):
    d = await diner(subscribe=False)
    r = await d.get("/preview/nearby", params=HERE)
    body = r.json()
    assert r.status_code == 200 and body["coverage"]["declared_restaurants"] == 3 and not body["coverage"]["waitlist"]
    assert {x["name"] for x in body["restaurants"]} == {"Paradise Corner", "Udupi Tiffins", "Tandoor House"}
    leaked = [k for k in keys(body) if any(w in k.lower() for w in NUTRITION_WORDS)]
    assert leaked == [] and "kcal" not in r.text.split('"display"')[0]
    for path in ("/restaurants/nearby", "/search"):
        r = await d.get(path, params=HERE)
        assert r.status_code == 402 and r.json()["error"]["code"] == "subscription_required"
        assert r.json()["paywall"]["trial_available"] is True
    r = await d.get(f"/dishes/{await _item_id('Masala Dosa')}")
    assert r.status_code == 402
    assert not [k for k in keys(r.json()) if any(w in k.lower() for w in NUTRITION_WORDS)]


async def test_trial_once_per_email_and_device(demo):
    d = await diner(device="device-AAAA1111")
    assert (await d.get("/me/entitlement")).json()["level"] == "trial"
    assert (await d.post("/billing/trial", {"device_id": "device-AAAA1111"})).status_code == 409
    other = await diner("other@example.com", subscribe=False)
    r = await other.post("/billing/trial", {"device_id": "device-AAAA1111"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "trial_used"


async def test_mock_subscription_and_webhook_replay(demo, monkeypatch):
    d = await diner(subscribe=False)
    r = await d.post("/billing/subscribe", {"plan": "monthly", "ref": None}, headers={"Idempotency-Key": "k1"})
    assert r.json()["mode"] == "mock"
    again = await d.post("/billing/subscribe", {"plan": "monthly"}, headers={"Idempotency-Key": "k1"})
    assert again.json()["subscription_id"] == r.json()["subscription_id"]
    assert (await d.get("/me/entitlement")).json()["level"] == "subscriber"

    monkeypatch.setattr(get_settings(), "RAZORPAY_WEBHOOK_SECRET", "whsec_test")
    raw = json.dumps({"event": "subscription.pending", "payload": {"subscription": {"entity": {"id": r.json()["subscription_id"]}}}}).encode()
    sig = hmac.new(b"whsec_test", raw, hashlib.sha256).hexdigest()
    h = {"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt_1", "Content-Type": "application/json"}
    first = await d.c.post("/api/v1/billing/webhooks/razorpay", content=raw, headers=h)
    assert first.json() == {"status": "processed"}
    ent1 = (await d.get("/me/entitlement")).json()
    assert ent1["level"] == "grace"
    second = await d.c.post("/api/v1/billing/webhooks/razorpay", content=raw, headers=h)
    assert second.json() == {"status": "duplicate"}
    assert (await d.get("/me/entitlement")).json() == ent1
    bad = await d.c.post("/api/v1/billing/webhooks/razorpay", content=raw, headers={**h, "X-Razorpay-Signature": "nope"})
    assert bad.status_code == 400


async def test_qr_ref_credits_outlet(demo):
    async with database.sessionmaker()() as s:
        b = await s.scalar(select(Branch).where(Branch.name == "Udupi Tiffins"))
    d = await diner(subscribe=False)
    await d.post("/billing/subscribe", {"plan": "yearly", "ref": b.code})
    async with database.sessionmaker()() as s:
        credited = await s.scalar(text("SELECT credited_branch_id FROM entitlements"))
    assert credited == b.id


async def test_lapsed_reads_diary_but_gets_402_on_dish(demo):
    d = await diner()
    await d.post("/diary/entries", {"meal_type": "lunch", "items": [{"menu_item_id": await _item_id("Masala Dosa")}]})
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE entitlements SET period_end = now() - interval '1 day'"))
        await s.commit()
    assert (await d.get("/me/entitlement")).json()["level"] == "lapsed"
    day = await d.get("/diary")
    assert day.status_code == 200 and day.json()["read_only"] and len(day.json()["entries"]) == 1
    assert (await d.get(f"/dishes/{await _item_id('Masala Dosa')}")).status_code == 402
    r = await d.post("/diary/entries", {"meal_type": "dinner", "items": [{"menu_item_id": await _item_id("Idli (4)")}]})
    assert r.status_code == 402
    assert (await d.get("/me/export")).status_code == 200


async def test_cancel_keeps_access_to_period_end(demo):
    d = await diner(subscribe=False)
    await d.post("/billing/subscribe", {"plan": "monthly"})
    r = await d.post("/billing/cancel")
    assert r.status_code == 200 and r.json()["access_until"]
    ent = (await d.get("/me/entitlement")).json()
    assert ent["level"] == "subscriber" and ent["cancelled"] is True


# ------------------------------------------------------------------ profile and targets

async def test_profile_rules(demo):
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    s = await sign_in(c, "kid@example.com")
    d = Diner(c, s["csrf_token"])
    young = await d.put("/me/profile", {**PROFILE, "birth_year": date.today().year - 16})
    assert young.status_code == 403 and young.json()["error"]["code"] == "under_18"
    assert (await d.put("/me/profile", {**PROFILE, "health_data_consent": False})).status_code == 422
    assert (await d.put("/me/profile", {**PROFILE, "calorie_target": 800})).json()["error"]["code"] == "below_floor"
    tiny = await d.put("/me/profile", {**PROFILE, "height_cm": 145, "weight_kg": 40, "activity_level": "sedentary"})
    t = tiny.json()["targets"]
    assert t["energy_kcal"] == get_settings().CALORIE_FLOOR_KCAL and t["floor_applied"] and "not medical advice" in t["note"]
    assert (await d.get("/me/profile")).json()["complete"] is True
    async with database.sessionmaker()() as s:
        raw = await s.scalar(text("SELECT weight_kg FROM consumer_profiles"))
    assert raw.startswith("gAAAA") and raw != "40"  # stored as an encrypted (Fernet) token, not plain text
    withdrawn = await d.post("/me/consents", {"purpose": "health_data", "granted": False})
    assert withdrawn.json()["weight_kg"] is None and withdrawn.json()["targets"] is None


# ------------------------------------------------------------------ hard filters and ranking

async def test_veg_user_never_sees_non_veg(demo):
    d = await diner(diet_type="veg")
    near = (await d.get("/restaurants/nearby", params=HERE)).json()
    for card in near["restaurants"]:
        page = (await d.get(f"/restaurants/{card['id']}", params=HERE)).json()
        assert all(x["diet_class"] == "veg" for x in page["dishes"] + page["other_dishes"])
    found = (await d.get("/search", params={**HERE, "q": "chicken"})).json()
    assert found["dishes"] == []


async def test_allergy_hides_declaring_dishes_everywhere(demo):
    d = await diner(allergies=["milk"])
    found = (await d.get("/search", params=HERE)).json()
    names = {x["name"] for x in found["dishes"]}
    assert "Paneer Butter Masala" not in names and "Butter Chicken" not in names and "Palak Paneer" not in names
    for x in found["dishes"]:
        if x["trust"]["label"] == "estimated":
            assert x["allergen_warning"] == "Allergen status unknown" and not x["ranked"]
    for card in (await d.get("/restaurants/nearby", params=HERE)).json()["restaurants"]:
        page = (await d.get(f"/restaurants/{card['id']}", params=HERE)).json()
        assert "Paneer Butter Masala" not in {x["name"] for x in page["dishes"] + page["other_dishes"]}
    # Opening it directly still works, with a clear warning.
    page = (await d.get(f"/dishes/{await _item_id('Paneer Butter Masala')}")).json()
    assert page["allergy_conflict"] == ["milk"]


async def test_restriction_needs_restaurant_tag(demo):
    d = await diner(diet_type="veg", restrictions=["jain"])
    names = {x["name"] for x in (await d.get("/search", params=HERE)).json()["dishes"]}
    assert names == {"Jeera Rice", "Plain Dosa", "Idli (4)", "Roti"}


async def test_ranking_uses_worst_case_and_counts_fits(demo):
    d = await diner()
    near = (await d.get("/restaurants/nearby", params=HERE)).json()
    assert near["meal_budget_display"].endswith("kcal per meal")
    assert near["restaurants"] == sorted(near["restaurants"], key=lambda c: -c["fit_count"])
    found = (await d.get("/search", params={**HERE, "max_kcal": 300})).json()
    assert found["dishes"] and all(x["energy"]["high"] <= 300 for x in found["dishes"])
    page1 = (await d.get("/search", params={**HERE, "limit": 3})).json()
    page2 = (await d.get("/search", params={**HERE, "limit": 3, "cursor": page1["next_cursor"]})).json()
    assert len(page1["dishes"]) == 3 and not {x["id"] for x in page1["dishes"]} & {x["id"] for x in page2["dishes"]}
    alias = (await d.get("/search", params={**HERE, "q": "chole"})).json()
    assert alias["dishes"][0]["name"] == "Chana Masala"


async def test_typical_meal_band_hidden_until_enough_data(demo):
    d = await diner()
    async with database.sessionmaker()() as s:
        b = await s.scalar(select(Branch).where(Branch.name == "Tandoor House"))
        s.add(OutletStats(branch_id=b.id, sample_meals=29, sample_users=20, kcal_p25=500, kcal_p75=800, band_source="logged"))
        await s.commit()
    page = (await d.get(f"/restaurants/{b.id}", params=HERE)).json()
    assert page["typical_meal"]["source"] == "modelled" and page["typical_meal"]["label"] == "estimated from menu"
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE outlet_stats SET sample_meals = 30, sample_users = 15"))
        await s.commit()
    page = (await d.get(f"/restaurants/{b.id}", params=HERE)).json()
    assert page["typical_meal"] == {"display": "500 to 800 kcal", "label": "what our users eat here, from 30 meals", "source": "logged"}


# ------------------------------------------------------------------ dish page

async def test_dish_page_and_calculation(demo):
    d = await diner()
    item = await _item_id("Masala Dosa")
    page = (await d.get(f"/dishes/{item}")).json()
    n = page["nutrition"]
    assert n["trust"]["label"] == "declared" and n["display_mode"] == "band"
    assert page["ingredients_label"] == "Restaurant's recipe" and "Potato" in page["ingredients"]
    assert n["protein_per_100_inr"].endswith("g protein per ₹100") and n["fit"]["display"].startswith("Fits your remaining")
    assert page["last_updated"] is not None
    half = (await d.post(f"/dishes/{item}/calculate", {"share_fraction": 0.5})).json()
    assert half["nutrients"]["energy_kcal"]["mid"] == pytest.approx(n["nutrients"]["energy_kcal"]["mid"] / 2)
    assert (await d.post(f"/dishes/{item}/calculate", {"serving_option_id": str(uuid.uuid4())})).status_code == 422
    est = (await d.get(f"/dishes/{await _item_id('Sambar')}")).json()
    assert est["nutrition"]["trust"]["label"] == "estimated" and est["allergens"]["display"] == "Allergen status unknown"
    assert est["ingredients_label"] == "Typical recipe for this dish"
    nodata = (await d.get(f"/dishes/{await _item_id('Veg Biryani')}")).json()
    assert nodata["nutrition"]["trust"]["label"] == "no_data" and nodata["nutrition"]["nutrients"]["energy_kcal"] is None


async def test_missing_sodium_is_null_not_zero(demo):
    d = await diner()
    page = (await d.get(f"/dishes/{await _item_id('Paneer Butter Masala')}")).json()
    assert page["nutrition"]["nutrients"]["sodium_mg"] is None


# ------------------------------------------------------------------ diary

async def test_diary_snapshot_survives_recipe_change(demo):
    d = await diner()
    dosa = await _item_id("Masala Dosa")
    body = {"meal_type": "lunch", "items": [{"menu_item_id": dosa, "component_label": "Main"},
                                            {"menu_item_id": await _item_id("Sambar"), "share_fraction": 0.5, "component_label": "Side"}]}
    e1 = await d.post("/diary/entries", body, headers={"Idempotency-Key": "meal-1"})
    e2 = await d.post("/diary/entries", body, headers={"Idempotency-Key": "meal-1"})
    assert e1.status_code == 201 and e1.json()["id"] == e2.json()["id"]
    before = (await d.get("/diary")).json()
    assert len(before["entries"]) == 1 and before["rings"]["energy"]["fraction"] > 0
    assert before["entries"][0]["items"][1]["share_display"] == "Half"
    assert before["remaining_display"].endswith("kcal left today")

    # The restaurant publishes a much richer recipe; the logged meal must not change.
    async with database.sessionmaker()() as s:
        owner = await s.scalar(text("SELECT id FROM users WHERE email = 'demo.udupi@example.com'"))
        biz = await s.scalar(text("SELECT id FROM businesses WHERE name = 'Udupi Tiffins (demo)'"))
        rid = await s.scalar(text("SELECT recipe_id FROM menu_items WHERE id = :i"), {"i": dosa})
        ghee = await s.scalar(text("SELECT id FROM ingredients WHERE name = 'Ghee'"))
        from app.services.recipes import repository as rrepo, service as recipes
        from app.services.recipes.schemas import LineIn, VersionIn
        await recipes.create_version(s, owner, biz, await rrepo.recipe(s, biz, rid), VersionIn(
            cooked_yield_g=1250, lines=[LineIn(ingredient_id=ghee, quantity=60), *[
                LineIn(ingredient_id=r[0], quantity=r[1]) for r in (await s.execute(text(
                    "SELECT ri.ingredient_id, ri.quantity_g FROM recipe_ingredients ri JOIN menu_items m "
                    "ON m.current_recipe_version_id = ri.recipe_version_id WHERE m.id = :i"), {"i": dosa})).all()]]))
        await s.commit()
    assert (await d.get(f"/dishes/{dosa}")).json()["nutrition"]["nutrients"]["energy_kcal"]["mid"] > \
        before["entries"][0]["items"][0]["energy"]["mid"]
    after = (await d.get("/diary")).json()
    assert after["entries"][0]["items"][0]["energy"] == before["entries"][0]["items"][0]["energy"]
    assert after["totals"] == before["totals"]

    entry = after["entries"][0]
    upd = await d.put(f"/diary/entries/{entry['id']}", {"meal_type": "dinner", "shares": {entry["items"][0]["id"]: 0.5}})
    assert upd.json()["items"][0]["energy"]["mid"] == pytest.approx(entry["items"][0]["energy"]["mid"] / 2)
    assert (await d.delete(f"/diary/entries/{entry['id']}")).status_code == 204
    assert (await d.get("/diary")).json()["entries"] == []


async def test_export_and_delete_account(demo):
    d = await diner()
    await d.post("/diary/entries", {"meal_type": "lunch", "items": [{"menu_item_id": await _item_id("Idli (4)")}]})
    exported = json.loads((await d.get("/me/export")).text)
    assert exported["account"]["email"] == "diner@example.com" and len(exported["diary"]) == 1
    assert exported["profile"]["weight_kg"] == 60
    assert (await d.delete("/me", {"confirm": "nope"})).status_code == 422
    assert (await d.delete("/me", {"confirm": "DELETE"})).status_code == 204
    assert (await d.get("/me")).status_code == 401
    async with database.sessionmaker()() as s:
        assert await s.scalar(text("SELECT count(*) FROM users WHERE email = 'diner@example.com'")) == 0
        assert await s.scalar(text("SELECT count(*) FROM consumer_profiles")) == 0
        assert await s.scalar(text("SELECT count(*) FROM meal_entries WHERE user_id IS NULL")) == 1
