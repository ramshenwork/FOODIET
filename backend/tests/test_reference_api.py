"""Seeded reference data in the database: autocomplete endpoints and Estimated nutrition."""
import pytest
from sqlalchemy import select

from app.core import database
from app.core.errors import AppError
from app.models.nutrition import ReferenceRecipe
from app.services.nutrition import service as nutrition
from jobs import seed_reference
from tests.conftest import sign_in


@pytest.fixture
async def seeded():
    async with database.sessionmaker()() as s:
        ings = await seed_reference.seed_ingredients(s)
        dishes = await seed_reference.seed_dishes(s)
        await seed_reference.seed_references(s, ings, dishes)
        await s.commit()


async def test_seed_is_idempotent(seeded):
    async with database.sessionmaker()() as s:
        ings = await seed_reference.seed_ingredients(s)
        dishes = await seed_reference.seed_dishes(s)
        refs = await seed_reference.seed_references(s, ings, dishes)
        await s.commit()
        count = len((await s.scalars(select(ReferenceRecipe))).all())
    assert count == len(refs) == 20


async def test_ingredient_autocomplete_tolerates_typos(client, seeded):
    await sign_in(client, "chef@example.com", role="business")
    r = await client.get("/api/v1/ingredients", params={"q": "paneer"})
    assert r.status_code == 200 and r.json()[0]["name"] == "Paneer"
    hit = r.json()[0]
    assert hit["licence_cleared"] is False and hit["allergens"] == ["milk"]
    typo = await client.get("/api/v1/ingredients", params={"q": "panner"})
    assert "Paneer" in [h["name"] for h in typo.json()]


async def test_dish_autocomplete_matches_aliases(client, seeded):
    await sign_in(client, "chef@example.com", role="business")
    r = await client.get("/api/v1/canonical-dishes", params={"q": "chole"})
    assert r.json()[0]["name"] == "Chana Masala" and r.json()[0]["matched_alias"] == "Chole"
    r = await client.get("/api/v1/canonical-dishes", params={"q": "biryani"})
    assert r.json()[0]["name"] == "Chicken Biryani"


async def test_reference_endpoints_need_a_business_account(client, seeded):
    await sign_in(client, "diner@example.com", role="consumer")
    assert (await client.get("/api/v1/ingredients", params={"q": "paneer"})).status_code == 403
    assert (await client.get("/api/v1/canonical-dishes", params={"q": "dal"})).status_code == 403


async def _ref_id(name):
    async with database.sessionmaker()() as s:
        return await s.scalar(select(ReferenceRecipe.id).where(ReferenceRecipe.name == name))


async def test_placeholder_data_cannot_be_published(seeded):
    rid = await _ref_id("Paneer Butter Masala")
    async with database.sessionmaker()() as s:
        with pytest.raises(AppError, match="not cleared"):
            await nutrition.estimated_nutrition(s, rid, require_cleared=True)


async def test_estimated_display_from_database(seeded):
    rid = await _ref_id("Paneer Butter Masala")
    async with database.sessionmaker()() as s:
        out = await nutrition.estimated_nutrition(s, rid, require_cleared=False)
    assert out.trust == {"label": "estimated", "note": None}
    assert out.display_mode == "range"
    assert out.nutrients["energy_kcal"].display == "380 to 710 kcal"
    assert out.nutrients["sodium_mg"] is None
    assert out.allergens["display"] == "Allergen status unknown"
