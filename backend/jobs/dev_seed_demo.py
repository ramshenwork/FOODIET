"""DEVELOPMENT ONLY: three demo restaurants in Hyderabad with published dishes, for trying discovery locally.

Refuses to run unless APP_ENV is development or staging (the test server). Recipes are copies of the placeholder reference recipes.
Run from backend/:  ../.venv/bin/python -m jobs.dev_seed_demo
"""
import asyncio

from sqlalchemy import select

from app.core import database
from app.core.settings import get_settings
from app.models.business import Business
from app.models.nutrition import ReferenceRecipe
from app.models.ontology import CanonicalDish
from app.services.businesses import service as businesses
from app.services.businesses.schemas import BranchIn, BusinessIn
from app.services.menus import service as menus
from app.services.menus.schemas import ItemIn, ItemUpdate
from app.services.recipes import service as recipes
from app.services.recipes.schemas import LineIn, RecipeIn, ServingIn, VersionIn
from app.services.users import service as users

DEMO = [
    ("Paradise Corner (demo)", "demo.paradise@example.com", 17.4239, 78.4738, 350, [
        ("Hyderabadi Chicken Biryani", "Hyderabadi Chicken Dum Biryani", "non_veg", 380, True, []),
        ("Chicken 65", "Chicken 65", "non_veg", 290, True, []),
        ("Paneer Butter Masala", "Paneer Butter Masala", "veg", 260, True, []),
        ("Jeera Rice", "Jeera Rice", "veg", 150, True, ["jain"]),
        ("Veg Biryani", None, "veg", 280, False, []),
    ]),
    ("Udupi Tiffins (demo)", "demo.udupi@example.com", 17.4156, 78.4512, 180, [
        ("Masala Dosa", "Masala Dosa", "veg", 110, True, []),
        ("Plain Dosa", "Plain Dosa", "veg", 80, True, ["jain"]),
        ("Idli (4)", "Idli", "veg", 70, True, ["jain", "vrat"]),
        ("Sambar", "Sambar", "veg", 40, False, []),
    ]),
    ("Tandoor House (demo)", "demo.tandoor@example.com", 17.4301, 78.4420, 450, [
        ("Chicken Tikka", "Chicken Tikka", "non_veg", 340, True, ["halal"]),
        ("Butter Chicken", "Butter Chicken", "non_veg", 380, True, ["halal"]),
        ("Dal Tadka", "Dal Tadka", "veg", 220, True, []),
        ("Palak Paneer", "Palak Paneer", "veg", 260, True, []),
        ("Roti", "Roti", "veg", 30, True, ["jain"]),
        ("Chana Masala", "Chana Masala", "veg", 200, False, []),
    ]),
]


async def main() -> None:
    if get_settings().APP_ENV not in ("development", "staging"):
        raise SystemExit("Refusing: this command only runs with APP_ENV=development or staging.")
    async with database.sessionmaker()() as s:
        refs = {r.name: r for r in (await s.scalars(select(ReferenceRecipe))).all()}
        dishes = {d.id: d for d in (await s.scalars(select(CanonicalDish))).all()}
        for name, email, lat, lng, cost, items in DEMO:
            if await s.scalar(select(Business.id).where(Business.name == name)):
                continue
            owner = await users.get_or_create(s, email, "business")
            biz = await businesses.create(s, owner.id, BusinessIn(name=name, first_branch=BranchIn(
                name=name.replace(" (demo)", ""), region="hyderabad", latitude=lat, longitude=lng, cost_for_one_inr=cost,
                address="Hyderabad (demo data)")))
            branch = biz.branches[0].id
            for label, ref_name, diet, price, declared, tags in items:
                ref = refs.get(ref_name) if ref_name else None
                dish_id = ref.canonical_dish_id if ref else None
                if ref_name is None:
                    dish_id = None
                recipe_id = None
                if declared and ref:
                    r = await recipes.create_recipe(s, owner.id, biz.id, RecipeIn(name=label))
                    recipe_id = r.id
                item = await menus.add_item(s, owner.id, biz.id, ItemIn(branch_id=branch, display_name=label, price_inr=price,
                                                                       diet_class=diet, canonical_dish_id=dish_id or (
                                                                           next((d.id for d in dishes.values() if d.name == label), None)),
                                                                       recipe_id=recipe_id, diet_tags=tags))
                if declared and ref:
                    await recipes.add_serving(s, owner.id, biz.id, item.id, ServingIn(label="Serving", weight_g=ref.serving_weight_g,
                                                                                      unit="plate", is_default=True))
                    lines = [LineIn(ingredient_id=l["ingredient_id"], quantity=l["quantity_g"], unit="g",
                                    oil_retained_g=l.get("oil_retained_g")) for l in ref.ingredients if "ingredient_id" in l]
                    subs = [l for l in ref.ingredients if "sub_reference_id" in l]
                    for sub_line in subs:  # expand reference sub-recipes inline, scaled to the quantity used
                        sub = next(x for x in refs.values() if str(x.id) == sub_line["sub_reference_id"])
                        k = sub_line["quantity_g"] / sub.cooked_yield_g
                        lines += [LineIn(ingredient_id=l["ingredient_id"], quantity=l["quantity_g"] * k, unit="g") for l in sub.ingredients]
                    from app.services.recipes import repository as rrepo
                    await recipes.create_version(s, owner.id, biz.id, await rrepo.recipe(s, biz.id, recipe_id),
                                                 VersionIn(cooking_method=ref.cooking_method, cooked_yield_g=ref.cooked_yield_g, lines=lines))
                await menus.update_item(s, owner.id, biz.id, item.id, ItemUpdate(
                    display_name=label, price_inr=price, diet_class=diet, canonical_dish_id=item.canonical_dish_id,
                    recipe_id=recipe_id, diet_tags=tags, status="published"))
            print(f"Created {name}")
        await s.commit()


if __name__ == "__main__":
    asyncio.run(main())
