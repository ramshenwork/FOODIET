"""Builds engine inputs straight from backend/seed/*.json, without a database."""
import json
from functools import lru_cache
from pathlib import Path

from app.services.nutrition.engine import IngredientData, Line, RecipeData

SEED = Path(__file__).resolve().parents[1] / "seed"


@lru_cache
def ingredients(cleared: bool = True) -> dict[str, IngredientData]:
    return {i["name"]: IngredientData(id=i["name"], name=i["name"], state=i["state"], per_100g=i["per_100g"],
                                      category=i["category"], allergens=tuple(i["allergens"]), licence_cleared=cleared)
            for i in json.loads((SEED / "ingredients.json").read_text())}


@lru_cache
def _refs() -> dict:
    return {r["name"]: r for r in json.loads((SEED / "reference_recipes.json").read_text())}


@lru_cache
def dishes() -> dict:
    return {d["name"]: d for d in json.loads((SEED / "canonical_dishes.json").read_text())}


def recipe(name: str, cleared: bool = True) -> RecipeData:
    r = _refs()[name]
    lines = []
    for l in r["lines"]:
        if "i" in l:
            lines.append(Line(quantity_g=l["g"], ingredient=ingredients(cleared)[l["i"]], oil_retained_g=l.get("oil_retained_g")))
        else:
            lines.append(Line(quantity_g=l["g"], sub_recipe=recipe(l["sub"], cleared)))
    return RecipeData(id=name, name=name, lines=tuple(lines), cooked_yield_g=r["cooked_yield_g"], cooking_method=r["cooking_method"])


def serving(name: str) -> float:
    return _refs()[name]["serving_weight_g"]


def dish_band(name: str) -> tuple[float, float]:
    return tuple(dishes()[_refs()[name]["dish"]]["expected_kcal_100g"])
