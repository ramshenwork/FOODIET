"""Phase 6: check-ins, reports, aggregates, fingerprint, trends, insights, reminders."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.core import database
from app.models.activity import Event
from jobs import nightly, reminders
from tests.test_business import make_owner
from tests.test_consumer import HERE, _item_id, demo, diner  # noqa: F401


async def _age_entries(minutes: int):
    async with database.sessionmaker()() as s:
        await s.execute(text(f"UPDATE meal_entries SET eaten_at = now() - interval '{minutes} minutes'"))
        await s.commit()


async def _log(d, name, share=1.0):
    r = await d.post("/diary/entries", {"meal_type": "lunch", "items": [{"menu_item_id": await _item_id(name), "share_fraction": share}]})
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ check-ins

async def test_checkin_flow(demo):
    d = await diner()
    entry = await _log(d, "Masala Dosa")
    assert (await d.get("/checkins/pending")).json() is None          # too soon after the meal
    await _age_entries(120)
    card = (await d.get("/checkins/pending")).json()
    assert card["meal_entry_id"] == entry["id"] and card["restaurant"] == "Udupi Tiffins"
    assert card["dishes"] == ["Masala Dosa"] and {"Idli (4)", "Sambar"} <= {m["name"] for m in card["menu"]}
    other = await _item_id("Chicken Tikka")
    bad = await d.post("/checkins", {"meal_entry_id": entry["id"], "recommended_item_id": other})
    assert bad.status_code == 422
    ok = await d.post("/checkins", {"meal_entry_id": entry["id"], "felt": "heavier", "recommend": True,
                                    "recommended_item_id": await _item_id("Idli (4)")})
    assert ok.status_code == 204
    assert (await d.post("/checkins", {"meal_entry_id": entry["id"]})).status_code == 409
    assert (await d.get("/checkins/pending")).json() is None


async def test_dismissing_a_checkin(demo):
    d = await diner()
    entry = await _log(d, "Idli (4)")
    await _age_entries(120)
    assert (await d.post("/checkins", {"meal_entry_id": entry["id"]})).status_code == 204
    assert (await d.get("/checkins/pending")).json() is None


# ------------------------------------------------------------------ reports

async def test_reports(demo):
    d = await diner()
    item = await _item_id("Masala Dosa")
    r = await d.post("/reports", {"menu_item_id": item, "type": "allergen_concern", "detail": "Tasted of cashew"})
    assert r.status_code == 201 and "Allergen concerns are reviewed first" in r.json()["message"]
    assert (await d.post("/reports", {"menu_item_id": item, "type": "allergen_concern"})).status_code == 409
    assert (await d.post("/reports", {"menu_item_id": item, "type": "portion_wrong"})).status_code == 201
    preview = await diner("p@example.com", subscribe=False)
    assert (await preview.post("/reports", {"menu_item_id": item, "type": "menu_changed"})).status_code == 402


# ------------------------------------------------------------------ heavier-than-expected widening

async def test_heavier_checkins_widen_high_for_current_version(demo):
    item = await _item_id("Masala Dosa")
    first = await diner("u0@example.com", device="dev-00000000")
    before = (await first.get(f"/dishes/{item}")).json()["nutrition"]["nutrients"]["energy_kcal"]
    for i in range(3):
        d = first if i == 0 else await diner(f"u{i}@example.com", device=f"dev-0000000{i}")
        entry = await _log(d, "Masala Dosa")
        await _age_entries(120)
        await d.post("/checkins", {"meal_entry_id": entry["id"], "felt": "heavier"})
    await nightly.main()
    after = (await first.get(f"/dishes/{item}")).json()["nutrition"]["nutrients"]["energy_kcal"]
    assert after["mid"] == pytest.approx(before["mid"]) and after["low"] == pytest.approx(before["low"])
    assert after["high"] > before["high"]


# ------------------------------------------------------------------ learned preferences and fingerprint

async def test_fingerprint_needs_consent_and_removals_stick(demo):
    d = await diner()
    for name in ("Masala Dosa", "Masala Dosa", "Idli (4)", "Plain Dosa"):
        await _log(d, name)
    await nightly.main()
    fp = (await d.get("/me/fingerprint")).json()
    assert fp["consented"] is False and fp["learned"] == []
    await d.post("/me/consents", {"purpose": "learned_preferences", "granted": True})
    await nightly.main()
    fp = (await d.get("/me/fingerprint")).json()
    values = {x["value"] for x in fp["learned"]}
    assert {"South Indian", "Masala Dosa"} <= values and fp["most_repeated"] == ["Masala Dosa"]
    assert fp["avg_protein_eating_out"].startswith("About")
    dosa = next(x for x in fp["learned"] if x["value"] == "Masala Dosa")
    assert (await d.delete(f"/me/fingerprint/{dosa['id']}")).status_code == 204
    await nightly.main()
    assert "Masala Dosa" not in {x["value"] for x in (await d.get("/me/fingerprint")).json()["learned"]}
    # Learned preferences never change stated filters: a veg user still never sees meat.
    prof = (await d.get("/me/profile")).json()
    assert prof["diet_type"] == "non_veg"
    await d.post("/me/consents", {"purpose": "learned_preferences", "granted": False})
    async with database.sessionmaker()() as s:
        assert await s.scalar(text("SELECT count(*) FROM learned_preferences")) == 0


# ------------------------------------------------------------------ outlet band from logged meals

async def test_outlet_band_switches_to_logged_with_enough_people(demo):
    item = await _item_id("Idli (4)")
    people = []
    for i in range(15):
        d = await diner(f"band{i}@example.com", device=f"band-device-{i:04d}")
        people.append(d)
        await _log(d, "Idli (4)")
        await _log(d, "Masala Dosa")
    await nightly.main()
    page = (await people[0].get("/restaurants/" + (await people[0].get(f"/dishes/{item}")).json()["restaurant_id"], params=HERE)).json()
    assert page["typical_meal"]["source"] == "logged" and page["typical_meal"]["label"] == "what our users eat here, from 30 meals"


# ------------------------------------------------------------------ trends

async def test_trends_and_recap(demo):
    d = await diner()
    await _log(d, "Masala Dosa")
    t = (await d.get("/diary/trends", params={"weeks": 4})).json()
    assert len(t["weeks"]) == 4 and t["weeks"][-1]["days_logged"] == 1
    assert t["weeks"][-1]["avg_energy_kcal"] > 0 and t["weeks"][-1]["energy_target"] > 0
    assert t["recap"]["lines"][0] == "You logged 1 day this week."


# ------------------------------------------------------------------ restaurant insights (aggregate only)

async def test_insights_aggregate_only_and_plan_gated(demo):
    for i in range(5):
        d = await diner(f"s{i}@example.com", device=f"search-dev-{i:04d}")
        r = (await d.get("/search", params={**HERE, "q": "sushi"})).json()
        assert r["dishes"] == []
    async with database.sessionmaker()() as s:
        ev = (await s.scalars(select(Event).where(Event.name == "search"))).first()
        assert ev.properties["lat"] == round(HERE["lat"], 2)
    owner = await make_owner("insight.owner@example.com", "Insight Cafe")
    # Put the owner's branch near the searches.
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE branches SET location = 'SRID=4326;POINT(78.461 17.421)' WHERE business_id = :b"), {"b": owner.bid})
        await s.commit()
    free = (await owner.get(f"/api/v1/business/{owner.bid}/insights/feedback")).json()
    assert free["detailed"] is False and free["dishes"] == [] and free["unmet_demand"] == []
    assert free["unmet_summary"].startswith("5 searches near you")
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE businesses SET plan='paid' WHERE id = :b"), {"b": owner.bid})
        await s.commit()
    paid = (await owner.get(f"/api/v1/business/{owner.bid}/insights/feedback")).json()
    assert paid["unmet_demand"][0]["display"] == "5 searches within 2 km for 'sushi' (veg) found nothing" or \
        paid["unmet_demand"][0]["display"].startswith("5 searches within 2 km for 'sushi'")
    blob = str(paid).lower()
    assert "@example.com" not in blob and "user_id" not in blob
    assert paid["checkins_30d"].startswith("Shown once at least")


async def test_unmet_demand_hidden_below_minimum(demo):
    for i in range(4):
        d = await diner(f"few{i}@example.com", device=f"few-dev-{i:04d}")
        await d.get("/search", params={**HERE, "q": "ramen"})
    owner = await make_owner("few.owner@example.com", "Few Cafe")
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE branches SET location = 'SRID=4326;POINT(78.461 17.421)' WHERE business_id = :b"), {"b": owner.bid})
        await s.execute(text("UPDATE businesses SET plan='paid' WHERE id = :b"), {"b": owner.bid})
        await s.commit()
    r = (await owner.get(f"/api/v1/business/{owner.bid}/insights/feedback")).json()
    assert r["unmet_demand"] == []


# ------------------------------------------------------------------ reminders

async def test_expiry_reminders_sent_once(demo):
    async with database.sessionmaker()() as s:
        await s.execute(text("UPDATE trust_records SET expires_at = now() + interval '10 days' WHERE id = "
                             "(SELECT id FROM trust_records WHERE label = 'declared' LIMIT 1)"))
        await s.commit()
        assert await reminders.run(s) == 1
        assert await reminders.run(s) == 0
        await s.execute(text("UPDATE trust_records SET expires_at = now() + interval '2 days' "
                             "WHERE expires_at < now() + interval '11 days' AND label = 'declared'"))
        assert await reminders.run(s) == 1   # the 3-day reminder is a separate one
        await s.commit()
