"""Phase 3: business area acceptance checks."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core import database
from app.main import app
from app.models.ingredients import Ingredient
from app.models.ontology import CanonicalDish
from jobs import dev_clear_placeholders, seed_reference
from tests.conftest import sign_in


@pytest.fixture
async def ref_data():
    async with database.sessionmaker()() as s:
        ings = await seed_reference.seed_ingredients(s)
        dishes = await seed_reference.seed_dishes(s)
        await seed_reference.seed_references(s, ings, dishes)
        await dev_clear_placeholders.clear(s)
        await s.commit()
        ing = {i.name: str(i.id) for i in (await s.scalars(select(Ingredient))).all()}
        dish = {d.name: str(d.id) for d in (await s.scalars(select(CanonicalDish))).all()}
    return ing, dish


class Owner:
    """A signed-in business owner with one business and one branch."""

    def __init__(self, client, csrf, business):
        self.c, self.csrf, self.biz = client, csrf, business
        self.bid, self.branch = business["id"], business["branches"][0]["id"]

    async def post(self, path, body=None, **kw):
        return await self.c.post(path, json=body, headers={"X-CSRF-Token": self.csrf}, **kw)

    async def put(self, path, body):
        return await self.c.put(path, json=body, headers={"X-CSRF-Token": self.csrf})

    async def get(self, path, **kw):
        return await self.c.get(path, **kw)


async def make_owner(email, name="Spice Route", region=None) -> Owner:
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    s = await sign_in(c, email, role="business")
    r = await c.post("/api/v1/business", headers={"X-CSRF-Token": s["csrf_token"]},
                     json={"name": name, "first_branch": {"name": f"{name} Main", "region": region,
                                                          "latitude": 17.385, "longitude": 78.4867}})
    assert r.status_code == 201, r.text
    return Owner(c, s["csrf_token"], r.json())


def dal_lines(ing, ghee=30):
    return [{"ingredient_id": ing["Toor dal, raw"], "quantity": 250, "unit": "g"},
            {"ingredient_id": ing["Water"], "quantity": 1, "unit": "l"},
            {"ingredient_id": ing["Onion"], "quantity": 80},
            {"ingredient_id": ing["Tomato"], "quantity": 100},
            {"ingredient_id": ing["Ghee"], "quantity": ghee},
            {"ingredient_id": ing["Salt"], "quantity": 12}]


async def dish_with_recipe(o: Owner, ing, dish, lines=None, serving=180, name="Dal Tadka"):
    B = f"/api/v1/business/{o.bid}"
    recipe = (await o.post(B + "/recipes", {"name": name})).json()
    item = (await o.post(B + "/menu-items", {"branch_id": o.branch, "display_name": name, "price_inr": 180,
                                             "diet_class": "veg", "canonical_dish_id": dish["Dal Tadka"],
                                             "recipe_id": recipe["id"]})).json()
    assert (await o.post(B + f"/menu-items/{item['id']}/servings",
                         {"label": "Katori", "weight_g": serving, "unit": "katori"})).status_code == 201
    v = await o.post(B + f"/recipes/{recipe['id']}/versions",
                     {"cooking_method": "simmer", "cooked_yield_g": 1300, "lines": lines or dal_lines(ing)})
    assert v.status_code == 201, v.text
    return recipe, item, v.json()


async def test_publish_flow_and_item_shows_declared(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    recipe, item, v = await dish_with_recipe(o, ing, dish)
    assert v["status"] == "published" and v["version_number"] == 1 and v["checks"] == []
    assert v["lines"][1]["quantity_g"] == 1000 and v["lines"][1]["entered_unit"] == "l"
    menu = (await o.get(f"/api/v1/business/{o.bid}/menus", params={"branch_id": o.branch})).json()
    n = menu["uncategorised"][0]["nutrition"]
    assert n["trust"]["label"] == "declared" and n["display_mode"] == "band"
    assert n["energy"]["display"].endswith("kcal, give or take 30") or "give or take" in n["energy"]["display"]


async def test_editing_creates_new_version_and_keeps_old(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    recipe, item, v1 = await dish_with_recipe(o, ing, dish)
    v2 = await o.post(f"/api/v1/recipes/{recipe['id']}/versions",
                      {"cooking_method": "simmer", "cooked_yield_g": 1300, "lines": dal_lines(ing, ghee=40)})
    assert v2.status_code == 201 and v2.json()["version_number"] == 2 and v2.json()["status"] == "published"
    versions = (await o.get(f"/api/v1/business/{o.bid}/recipes/{recipe['id']}/versions")).json()
    assert [v["version_number"] for v in versions] == [1, 2]
    assert versions[0]["nutrition"]["per_100g"]["energy_kcal"]["mid"] < versions[1]["nutrition"]["per_100g"]["energy_kcal"]["mid"]
    async with database.sessionmaker()() as s:
        cur = await s.scalar(text("SELECT current_recipe_version_id FROM menu_items WHERE id = :i"), {"i": item["id"]})
    assert str(cur) == v2.json()["id"]


async def test_two_outlets_same_dish_different_recipes_differ(ref_data):
    ing, dish = ref_data
    a, b = await make_owner("a@x.com", "Outlet A"), await make_owner("b@x.com", "Outlet B")
    await dish_with_recipe(a, ing, dish)
    await dish_with_recipe(b, ing, dish, lines=dal_lines(ing, ghee=60))
    ea = (await a.get(f"/api/v1/business/{a.bid}/menus", params={"branch_id": a.branch})).json()["uncategorised"][0]
    eb = (await b.get(f"/api/v1/business/{b.bid}/menus", params={"branch_id": b.branch})).json()["uncategorised"][0]
    assert ea["canonical_dish_id"] == eb["canonical_dish_id"]
    assert ea["nutrition"]["energy"]["mid"] != eb["nutrition"]["energy"]["mid"]


async def test_other_business_gets_404(ref_data):
    ing, dish = ref_data
    a, b = await make_owner("a@x.com", "A"), await make_owner("b@x.com", "B")
    recipe, item, _ = await dish_with_recipe(a, ing, dish)
    assert (await b.get(f"/api/v1/business/{a.bid}/recipes/{recipe['id']}")).status_code == 404
    assert (await b.get(f"/api/v1/business/{b.bid}/recipes/{recipe['id']}")).status_code == 404
    r = await b.post(f"/api/v1/recipes/{recipe['id']}/versions",
                     {"cooked_yield_g": 1000, "lines": [{"ingredient_id": ing["Salt"], "quantity": 1}]})
    assert r.status_code == 404
    assert (await b.post(f"/api/v1/menu-items/{item['id']}/reconfirm")).status_code == 404
    assert (await b.get(f"/api/v1/branches/{a.branch}/qr")).status_code == 404
    assert (await b.get(f"/api/v1/business/{a.bid}/menus", params={"branch_id": a.branch})).status_code == 404


async def test_500g_oil_in_250g_serving_is_held_not_published(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    lines = [{"ingredient_id": ing["Vegetable oil (refined)"], "quantity": 500},
             {"ingredient_id": ing["Potato"], "quantity": 100}]
    B = f"/api/v1/business/{o.bid}"
    recipe = (await o.post(B + "/recipes", {"name": "Oil bomb"})).json()
    item = (await o.post(B + "/menu-items", {"branch_id": o.branch, "display_name": "Oil bomb", "recipe_id": recipe["id"]})).json()
    await o.post(B + f"/menu-items/{item['id']}/servings", {"label": "Plate", "weight_g": 250, "unit": "plate"})
    v = (await o.post(B + f"/recipes/{recipe['id']}/versions", {"cooked_yield_g": 250, "lines": lines})).json()
    assert v["status"] == "held"
    assert "fat_share_high" in {c["rule"] for c in v["checks"]}
    menu = (await o.get(B + "/menus", params={"branch_id": o.branch})).json()
    assert menu["uncategorised"][0]["current_recipe_version_id"] is None
    assert (await o.get(B + "/insights")).json()["held_versions"] == 1


async def test_uncleared_data_is_held(ref_data):
    ing, dish = ref_data
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE nutrient_profiles SET licence_status = 'pending'"))
        await s.commit()
    o = await make_owner("owner@a.com")
    _, _, v = await dish_with_recipe(o, ing, dish)
    assert v["status"] == "held" and "licence_not_cleared" in {c["rule"] for c in v["checks"]}


async def test_preview_is_live_and_stores_nothing(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    B = f"/api/v1/business/{o.bid}"
    r = await o.post(B + "/recipes/preview", {"cooked_yield_g": 1300, "lines": dal_lines(ing), "serving_weight_g": 180,
                                              "canonical_dish_id": dish["Dal Tadka"]})
    body = r.json()
    assert r.status_code == 200 and body["can_publish"] and body["nutrition"]["per_serving"]["energy_kcal"]["mid"] > 0
    async with database.sessionmaker()() as s:
        assert await s.scalar(text("SELECT count(*) FROM recipe_versions")) == 0
    bad = await o.post(B + "/recipes/preview", {"cooked_yield_g": 100, "lines": dal_lines(ing)})
    assert "yield_implausible" in {c["rule"] for c in bad.json()["checks"]} and not bad.json()["can_publish"]


async def test_sub_recipe_must_be_published_and_is_used(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    B = f"/api/v1/business/{o.bid}"
    gravy = (await o.post(B + "/recipes", {"name": "Makhani base", "is_sub_recipe": True})).json()
    main = (await o.post(B + "/recipes", {"name": "Paneer makhani"})).json()
    lines = [{"sub_recipe_id": gravy["id"], "quantity": 500}, {"ingredient_id": ing["Paneer"], "quantity": 400}]
    early = await o.post(B + f"/recipes/{main['id']}/versions", {"cooked_yield_g": 900, "lines": lines})
    assert early.status_code == 422 and early.json()["error"]["code"] == "sub_recipe_unpublished"
    await o.post(B + f"/recipes/{gravy['id']}/versions", {"cooked_yield_g": 800, "lines": [
        {"ingredient_id": ing["Tomato"], "quantity": 900}, {"ingredient_id": ing["Butter, salted"], "quantity": 40},
        {"ingredient_id": ing["Cashew nuts"], "quantity": 30}]})
    v = (await o.post(B + f"/recipes/{main['id']}/versions", {"cooked_yield_g": 900, "lines": lines})).json()
    assert v["status"] == "published" and v["lines"][0]["sub_recipe_version_id"]
    assert set(v["nutrition"]["allergens"]) == {"milk", "tree_nut"}


async def test_free_plan_limits_branches_and_team(ref_data):
    o = await make_owner("owner@a.com")
    r = await o.post(f"/api/v1/business/{o.bid}/branches", {"name": "Second"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "plan_required"
    r = await o.post(f"/api/v1/business/{o.bid}/team", {"email": "chef@a.com", "role": "chef"})
    assert r.status_code == 402


async def _upgrade(o):
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE businesses SET plan='paid' WHERE id = :b"), {"b": o.bid})
        await s.commit()


async def test_branch_override_leaves_brand_and_other_branches_unchanged(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    await _upgrade(o)
    B = f"/api/v1/business/{o.bid}"
    second = (await o.post(B + "/branches", {"name": "Branch Two"})).json()
    recipe, item1, v1 = await dish_with_recipe(o, ing, dish)
    item2 = (await o.post(B + "/menu-items", {"branch_id": second["id"], "display_name": "Dal Tadka",
                                              "recipe_id": recipe["id"]})).json()
    assert item2["current_recipe_version_id"] == v1["id"]
    override = (await o.post(B + f"/recipes/{recipe['id']}/override", {"branch_id": second["id"]})).json()
    assert override["scope"] == "branch" and override["overrides_recipe_id"] == recipe["id"]
    ov2 = await o.post(B + f"/recipes/{override['id']}/versions",
                       {"cooking_method": "simmer", "cooked_yield_g": 1300, "lines": dal_lines(ing, ghee=45)})
    assert ov2.json()["status"] == "published"
    brand_versions = (await o.get(B + f"/recipes/{recipe['id']}/versions")).json()
    assert [v["id"] for v in brand_versions] == [v1["id"]]
    m1 = (await o.get(B + "/menus", params={"branch_id": o.branch})).json()["uncategorised"][0]
    m2 = (await o.get(B + "/menus", params={"branch_id": second["id"]})).json()["uncategorised"][0]
    assert m1["current_recipe_version_id"] == v1["id"] and m1["recipe_id"] == recipe["id"]
    assert m2["recipe_id"] == override["id"] and m2["current_recipe_version_id"] == ov2.json()["id"]


async def test_roles_limit_what_members_can_do(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    await _upgrade(o)
    assert (await o.post(f"/api/v1/business/{o.bid}/team", {"email": "ed@a.com", "role": "editor"})).status_code == 201
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ec:
        s = await sign_in(ec, "ed@a.com", role="business")
        h = {"X-CSRF-Token": s["csrf_token"]}
        assert (await ec.post(f"/api/v1/business/{o.bid}/recipes", json={"name": "x"}, headers=h)).status_code == 403
        r = await ec.post(f"/api/v1/business/{o.bid}/menu-items", headers=h,
                          json={"branch_id": o.branch, "display_name": "Lassi"})
        assert r.status_code == 201


async def test_modifiers_exclusive_and_show_energy_change(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    _, item, _ = await dish_with_recipe(o, ing, dish)
    B = f"/api/v1/business/{o.bid}"
    g = (await o.post(B + f"/menu-items/{item['id']}/modifier-groups", {"name": "Ghee", "exclusive": True})).json()
    m = await o.post(B + f"/modifier-groups/{g['id']}/modifiers",
                     {"label": "No ghee tadka", "kind": "delta", "deltas": [{"ingredient_id": ing["Ghee"], "delta_g": -4}]})
    assert m.status_code == 201
    bad = await o.post(B + f"/modifier-groups/{g['id']}/modifiers", {"label": "x", "kind": "delta", "deltas": []})
    assert bad.status_code == 422
    groups = (await o.get(B + f"/menu-items/{item['id']}/modifier-groups")).json()
    assert groups[0]["modifiers"][0]["energy_change_display"] == "-40 kcal"


async def test_reconfirm_resets_expiry(ref_data):
    ing, dish = ref_data
    o = await make_owner("owner@a.com")
    _, item, _ = await dish_with_recipe(o, ing, dish)
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE trust_records SET verified_at = now() - interval '100 days', "
                             "expires_at = now() - interval '10 days'"))
        await s.commit()
    menu = (await o.get(f"/api/v1/business/{o.bid}/menus", params={"branch_id": o.branch})).json()
    stale = menu["uncategorised"][0]["nutrition"]
    assert stale["trust"]["note"].startswith("Not reconfirmed since") and stale["display_mode"] == "range"
    r = await o.post(f"/api/v1/menu-items/{item['id']}/reconfirm")
    assert r.status_code == 200
    fresh = (await o.get(f"/api/v1/business/{o.bid}/menus", params={"branch_id": o.branch})).json()["uncategorised"][0]
    assert fresh["nutrition"]["trust"]["note"] is None and fresh["nutrition"]["display_mode"] == "band"


async def test_csv_import_creates_drafts_only(ref_data):
    o = await make_owner("owner@a.com")
    B = f"/api/v1/business/{o.bid}"
    csv = "Name,Price,Category,Diet\nChole,160,Mains,veg\nButter Chicken,320,Mains,non-veg\nMasala Dosa,120,South,veg\n"
    r = await o.c.post(B + "/menu-imports", headers={"X-CSRF-Token": o.csrf}, data={"branch_id": o.branch},
                       files={"file": ("menu.csv", csv.encode(), "text/csv")})
    assert r.status_code == 201, r.text
    imp = r.json()
    assert imp["status"] == "ready" and len(imp["rows"]) == 3
    assert imp["rows"][0]["canonical_dish_name"] == "Chana Masala" and imp["rows"][1]["diet_class"] == "non_veg"
    rows = imp["rows"]
    rows[2]["include"] = False
    assert (await o.put(B + f"/menu-imports/{imp['id']}", {"rows": rows})).status_code == 200
    assert (await o.post(B + f"/menu-imports/{imp['id']}/confirm")).json() == {"created": 2}
    menu = (await o.get(B + "/menus", params={"branch_id": o.branch})).json()
    items = [i for c in menu["categories"] for i in c["items"]]
    assert {i["display_name"] for i in items} == {"Chole", "Butter Chicken"}
    assert all(i["status"] == "draft" for i in items)
    assert (await o.post(B + f"/menu-imports/{imp['id']}/confirm")).status_code == 409


async def test_photo_import_waits_for_ai_and_bad_files_rejected(ref_data):
    o = await make_owner("owner@a.com")
    B = f"/api/v1/business/{o.bid}"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    r = await o.c.post(B + "/menu-imports", headers={"X-CSRF-Token": o.csrf}, data={"branch_id": o.branch},
                       files={"file": ("menu.png", png, "image/png")})
    assert r.json()["status"] == "needs_ai" and r.json()["rows"] == []
    fake = await o.c.post(B + "/menu-imports", headers={"X-CSRF-Token": o.csrf}, data={"branch_id": o.branch},
                          files={"file": ("x.png", b"not a png", "image/png")})
    assert fake.status_code == 422
    exe = await o.c.post(B + "/menu-imports", headers={"X-CSRF-Token": o.csrf}, data={"branch_id": o.branch},
                         files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert exe.status_code == 422


async def test_public_qr_page(ref_data, client):
    ing, dish = ref_data
    o = await make_owner("owner@a.com", "Dal & <Co>")
    B = f"/api/v1/business/{o.bid}"
    _, item, _ = await dish_with_recipe(o, ing, dish)
    await o.put(B + f"/menu-items/{item['id']}", {"display_name": "Dal Tadka", "status": "published",
                                                  "recipe_id": item["recipe_id"], "canonical_dish_id": dish["Dal Tadka"]})
    est = (await o.post(B + "/menu-items", {"branch_id": o.branch, "display_name": "Masala Dosa",
                                            "canonical_dish_id": dish["Masala Dosa"]})).json()
    await o.put(B + f"/menu-items/{est['id']}", {"display_name": "Masala Dosa", "status": "published",
                                                 "canonical_dish_id": dish["Masala Dosa"]})
    await o.post(B + "/menu-items", {"branch_id": o.branch, "display_name": "Draft only"})
    qr = (await o.get(f"/api/v1/branches/{o.branch}/qr")).json()
    assert qr["svg"].startswith("<svg") and qr["url"].endswith(f"/q/{qr['branch_code']}")

    page = await client.get(f"/q/{qr['branch_code']}")  # anonymous
    html = page.text
    assert page.status_code == 200 and "<script" not in html
    assert "Dal &amp; &lt;Co&gt; Main" in html                      # escaped
    assert "Restaurant-declared" in html and "~ Estimated" in html
    assert "Allergen status unknown" in html and "Contains: milk" in html
    assert "Draft only" not in html
    assert f"ref={qr['branch_code']}" in html
    assert (await client.get("/q/nope1234")).status_code == 404
