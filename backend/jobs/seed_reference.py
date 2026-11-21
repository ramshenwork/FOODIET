"""Load reference data from backend/seed/*.json. Idempotent: rows are matched by name and updated.

Run from backend/:  ../.venv/bin/python -m jobs.seed_reference
"""
import asyncio
import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.models.ingredients import Ingredient, NutrientProfile
from app.models.nutrition import NUTRIENTS, ReferenceRecipe
from app.models.ontology import CanonicalDish, DishAlias, RegionalVariant
from app.services.events import service as events
from app.services.nutrition import service as nutrition
from app.services.trust import service as trust

SEED = Path(__file__).resolve().parents[1] / "seed"


def _load(name: str):
    return json.loads((SEED / name).read_text())


async def seed_ingredients(s: AsyncSession) -> dict[str, Ingredient]:
    out = {}
    for row in _load("ingredients.json"):
        ing = await s.scalar(select(Ingredient).where(Ingredient.name == row["name"]))
        if ing is None:
            ing = Ingredient(name=row["name"])
            s.add(ing)
        ing.category, ing.state, ing.allergen_flags = row["category"], row["state"], row["allergens"]
        await s.flush()
        prof = await s.scalar(select(NutrientProfile).where(NutrientProfile.ingredient_id == ing.id,
                                                            NutrientProfile.source == "placeholder"))
        if prof is None:  # source, version and licence are set once; an admin decision is never overwritten
            prof = NutrientProfile(ingredient_id=ing.id, source="placeholder", licence_status="pending",
                                   source_version="builder-placeholder")
            s.add(prof)
        for n in NUTRIENTS:
            setattr(prof, n, row["per_100g"].get(n))
        out[ing.name] = ing
    return out


async def seed_dishes(s: AsyncSession) -> dict[str, CanonicalDish]:
    out = {}
    for row in _load("canonical_dishes.json"):
        d = await s.scalar(select(CanonicalDish).where(CanonicalDish.name == row["name"]))
        if d is None:
            d = CanonicalDish(name=row["name"])
            s.add(d)
        d.cuisine, d.region, d.diet_class = row["cuisine"], row["region"], row["diet_class"]
        d.expected_kcal_100g_low, d.expected_kcal_100g_high = row["expected_kcal_100g"]
        await s.flush()
        await s.execute(delete(DishAlias).where(DishAlias.canonical_dish_id == d.id))
        await s.execute(delete(RegionalVariant).where(RegionalVariant.canonical_dish_id == d.id))
        for alias, lang in row.get("aliases", []):
            s.add(DishAlias(canonical_dish_id=d.id, alias=alias, language=lang))
        for region, name in row.get("variants", []):
            s.add(RegionalVariant(canonical_dish_id=d.id, region=region, name=name))
        out[d.name] = d
    return out


async def seed_references(s: AsyncSession, ings: dict, dishes: dict) -> dict[str, ReferenceRecipe]:
    rows = _load("reference_recipes.json")
    out: dict[str, ReferenceRecipe] = {}
    pending = list(rows)
    while pending:  # sub-recipes first
        progressed = False
        for row in list(pending):
            subs = [l["sub"] for l in row["lines"] if "sub" in l]
            if any(sub not in out for sub in subs):
                continue
            lines = []
            for l in row["lines"]:
                if "i" in l:
                    if l["i"] not in ings:
                        raise SystemExit(f"{row['name']}: unknown ingredient {l['i']!r}")
                    line = {"ingredient_id": str(ings[l["i"]].id), "quantity_g": l["g"]}
                else:
                    line = {"sub_reference_id": str(out[l["sub"]].id), "quantity_g": l["g"]}
                if "oil_retained_g" in l:
                    line["oil_retained_g"] = l["oil_retained_g"]
                lines.append(line)
            ref = await s.scalar(select(ReferenceRecipe).where(ReferenceRecipe.name == row["name"]))
            if ref is None:
                ref = ReferenceRecipe(name=row["name"])
                s.add(ref)
            ref.canonical_dish_id = dishes[row["dish"]].id if row["dish"] else None
            ref.region, ref.cooking_method = row["region"], row["cooking_method"]
            ref.cooked_yield_g, ref.serving_weight_g = row["cooked_yield_g"], row["serving_weight_g"]
            ref.ingredients, ref.spread = lines, row.get("spread")
            ref.notes = "Builder placeholder. Not reviewed by a nutrition professional." if not row["reviewed"] else None
            await s.flush()
            out[row["name"]] = ref
            pending.remove(row)
            progressed = True
        if not progressed:
            raise SystemExit("Reference recipes reference unknown or circular sub-recipes: "
                             + ", ".join(r["name"] for r in pending))
    return out


async def report(s: AsyncSession, refs: dict, dishes: dict) -> list[str]:
    """Development report: per-100 g energy against each dish's expected band, plus plausibility flags.
    Uses placeholder data (require_cleared=False); nothing here is stored or published."""
    lines = []
    for name, ref in refs.items():
        res = await nutrition.calculate_reference(s, ref.id, require_cleared=False)
        dish = next((d for d in dishes.values() if d.id == ref.canonical_dish_id), None)
        band = (dish.expected_kcal_100g_low, dish.expected_kcal_100g_high) if dish else None
        flags = trust.check(res, band, [ref.serving_weight_g] if ref.serving_weight_g else [])
        e = res.per_100g["energy_kcal"]
        serving = res.per_serving["energy_kcal"] if res.per_serving else None
        sodium = "unknown" if res.per_100g["sodium_mg"] is None else f"{res.per_100g['sodium_mg']:.0f} mg"
        lines.append(f"{name:34} {e:6.0f} kcal/100g  band {band or '-'!s:12} serving "
                     f"{'' if serving is None else f'{serving:5.0f} kcal'}  sodium/100g {sodium:9} "
                     f"flags: {', '.join(f.rule for f in flags) or 'none'}")
    return lines


async def main() -> None:
    async with database.sessionmaker()() as s:
        async with events.job_run(s, "seed_reference"):
            ings = await seed_ingredients(s)
            dishes = await seed_dishes(s)
            refs = await seed_references(s, ings, dishes)
        await s.commit()
        print(f"Seeded {len(ings)} ingredients, {len(dishes)} canonical dishes, {len(refs)} reference recipes.")
        print("All nutrient profiles are placeholders with licence_status=pending.\n")
        for line in await report(s, refs, dishes):
            print(line)


if __name__ == "__main__":
    asyncio.run(main())
