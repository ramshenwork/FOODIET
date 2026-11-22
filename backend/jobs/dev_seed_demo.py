"""DEVELOPMENT ONLY: demo restaurants in Hyderabad with published dishes, for trying discovery locally.

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

# More restaurants for the test server. Their dishes need the extra reference data in seed/demo.
DEMO_MORE = [
    ("Nawab's Kitchen (demo)", "demo.nawab@example.com", 17.3616, 78.4747, 400, [
        ("Mutton Biryani", "Mutton Biryani", "non_veg", 420, True, ["halal"], 1.1),
        ("Hyderabadi Chicken Biryani", "Hyderabadi Chicken Dum Biryani", "non_veg", 340, True, ["halal"], 1.1),
        ("Mutton Rogan Josh", "Mutton Rogan Josh", "non_veg", 390, True, ["halal"]),
        ("Roti", "Roti", "veg", 25, True, []),
        ("Double Ka Meetha", None, "veg", 120, False, []),
    ]),
    ("Coastal Spice (demo)", "demo.coastal@example.com", 17.4483, 78.3915, 550, [
        ("Kerala Fish Curry", "Fish Curry", "non_veg", 420, True, []),
        ("Prawn Masala", "Prawn Masala", "non_veg", 480, True, []),
        ("Steamed Rice", "Steamed Rice", "veg", 90, True, ["jain"]),
        ("Lemon Rice", "Lemon Rice", "veg", 160, False, []),
    ]),
    ("Punjab Da Dhaba (demo)", "demo.dhaba@example.com", 17.4948, 78.3996, 300, [
        ("Rajma Chawal", "Rajma", "veg", 220, True, [], 1.3),
        ("Dal Tadka", "Dal Tadka", "veg", 190, True, [], 1.3),
        ("Chana Masala", "Chana Masala", "veg", 200, True, [], 1.3),
        ("Butter Chicken", "Butter Chicken", "non_veg", 360, True, [], 1.2),
        ("Tandoori Roti", "Roti", "veg", 25, True, []),
        ("Lassi", None, "veg", 90, False, []),
    ]),
    ("Wok This Way (demo)", "demo.wok@example.com", 17.4325, 78.4071, 450, [
        ("Veg Hakka Noodles", "Veg Hakka Noodles", "veg", 240, True, []),
        ("Chilli Paneer (dry)", "Chilli Paneer", "veg", 290, True, []),
        ("Dragon Chicken 65", "Chicken 65", "non_veg", 320, False, []),
        ("Veg Manchurian", None, "veg", 250, False, []),
    ]),
    ("Mumbai Street Bites (demo)", "demo.mumbai@example.com", 17.4375, 78.4482, 200, [
        ("Pav Bhaji", "Pav Bhaji", "veg", 160, True, []),
        ("Samosa (2)", "Samosa", "veg", 40, True, [], 2.0),
        ("Egg Bhurji Pav", "Egg Bhurji", "egg", 120, True, []),
        ("Kanda Poha", "Poha", "veg", 60, True, ["vrat"]),
    ]),
    ("Green Bowl Kitchen (demo)", "demo.greenbowl@example.com", 17.4401, 78.3489, 400, [
        ("Moong Dal Bowl", "Moong Dal", "veg", 210, True, ["jain"], 1.2),
        ("Mixed Veg Curry", "Mixed Veg Curry", "veg", 230, True, []),
        ("Palak Paneer (light)", "Palak Paneer", "veg", 290, True, [], 0.85),
        ("Brown Rice", "Steamed Rice", "veg", 120, False, [], 0.8),
        ("Curd Bowl", "Curd (katori)", "veg", 60, True, ["jain", "vrat"]),
        ("Grilled Chicken Tikka", "Chicken Tikka", "non_veg", 360, True, ["halal"], 0.9),
    ]),
    ("Andhra Meals (demo)", "demo.andhra@example.com", 17.4447, 78.4664, 250, [
        ("Lemon Rice", "Lemon Rice", "veg", 120, True, []),
        ("Sambar Rice", "Sambar", "veg", 140, True, [], 1.5),
        ("Egg Curry", "Egg Curry", "egg", 170, True, []),
        ("Chicken 65", "Chicken 65", "non_veg", 260, True, []),
        ("Curd Rice", None, "veg", 100, False, []),
    ]),
    ("Morning Tiffin Centre (demo)", "demo.tiffin@example.com", 17.4239, 78.4590, 120, [
        ("Rava Upma", "Upma", "veg", 60, True, []),
        ("Poha", "Poha", "veg", 50, True, ["vrat"]),
        ("Idli (2)", "Idli", "veg", 40, True, ["jain"], 0.5),
        ("Masala Dosa", "Masala Dosa", "veg", 90, True, []),
        ("Coconut Chutney", "Coconut Chutney", "veg", 20, True, ["jain"]),
    ]),
    ("Anda Bhai Corner (demo)", "demo.anda@example.com", 17.4040, 78.4630, 150, [
        ("Masala Omelette", "Masala Omelette", "egg", 70, True, []),
        ("Egg Bhurji", "Egg Bhurji", "egg", 90, True, []),
        ("Egg Curry", "Egg Curry", "egg", 140, False, []),
        ("Roti", "Roti", "veg", 20, True, []),
    ]),
    ("Biryani Junction (demo)", "demo.junction@example.com", 17.4050, 78.4970, 300, [
        ("Chicken Dum Biryani", "Hyderabadi Chicken Dum Biryani", "non_veg", 300, True, ["halal"]),
        ("Kolkata Biryani", "Kolkata Chicken Biryani", "non_veg", 320, True, ["halal"]),
        ("Veg Pulao", "Veg Pulao", "veg", 200, True, []),
        ("Mutton Biryani (family pack)", "Mutton Biryani", "non_veg", 1100, False, ["halal"], 3.0),
    ]),
]


async def main(more: bool = False) -> None:
    if get_settings().APP_ENV not in ("development", "staging"):
        raise SystemExit("Refusing: this command only runs with APP_ENV=development or staging.")
    async with database.sessionmaker()() as s:
        refs = {r.name: r for r in (await s.scalars(select(ReferenceRecipe))).all()}
        dishes = {d.id: d for d in (await s.scalars(select(CanonicalDish))).all()}
        for name, email, lat, lng, cost, items in DEMO + (DEMO_MORE if more else []):
            if await s.scalar(select(Business.id).where(Business.name == name)):
                continue
            owner = await users.get_or_create(s, email, "business")
            biz = await businesses.create(s, owner.id, BusinessIn(name=name, first_branch=BranchIn(
                name=name.replace(" (demo)", ""), region="hyderabad", latitude=lat, longitude=lng, cost_for_one_inr=cost,
                address="Hyderabad (demo data)")))
            branch = biz.branches[0].id
            for label, ref_name, diet, price, declared, tags, *portion in items:
                portion = portion[0] if portion else 1.0  # this restaurant's serving size against the reference
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
                    await recipes.add_serving(s, owner.id, biz.id, item.id, ServingIn(label="Serving", weight_g=round(ref.serving_weight_g * portion),
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
