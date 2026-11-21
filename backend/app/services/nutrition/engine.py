"""The nutrition engine (spec section 9). Pure Python: no database, network, or AI access.

Same inputs always give the same outputs. Results are unrounded; rounding happens only at display.
A nutrient is None (unknown) if any contributing ingredient lacks it, never a partial sum.

    ingredient_nutrient = quantity_g / 100 * nutrient_per_100g
    batch_nutrient      = sum over ingredients (a sub-recipe contributes its own per-100 g values;
                          frying oil contributes oil_retained_g, not oil added)
    per_100g            = batch_nutrient / cooked_yield_g * 100
    per_serving         = per_100g * serving_weight_g / 100
    eaten               = per_serving * share_fraction
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

NUTRIENTS = ("energy_kcal", "protein_g", "carbs_g", "fat_g", "fibre_g", "sodium_mg")
STATES = ("raw", "cooked")

Nutrients = dict[str, float | None]


class EngineError(ValueError):
    """The recipe cannot be calculated as given. The message is safe to show the recipe author."""


# ------------------------------------------------------------------ inputs

@dataclass(frozen=True)
class IngredientData:
    id: str
    name: str
    state: str | None                      # 'raw' | 'cooked'; None is rejected
    per_100g: Nutrients                    # None = unknown
    category: str | None = None            # e.g. 'poultry', 'paneer', 'pulse' (used by plausibility checks)
    allergens: tuple[str, ...] = ()
    licence_cleared: bool = False


@dataclass(frozen=True)
class Line:
    quantity_g: float
    ingredient: IngredientData | None = None
    sub_recipe: RecipeData | None = None
    oil_retained_g: float | None = None    # frying oil: what stays in the food

    def __post_init__(self):
        if (self.ingredient is None) == (self.sub_recipe is None):
            raise EngineError("Each line needs exactly one ingredient or sub-recipe.")


@dataclass(frozen=True)
class RecipeData:
    id: str
    name: str
    lines: tuple[Line, ...]
    cooked_yield_g: float
    cooking_method: str | None = None


@dataclass(frozen=True)
class Delta:
    ingredient: IngredientData
    delta_g: float                          # per serving: "no butter" = -10 g butter


@dataclass(frozen=True)
class Modifier:
    id: str
    group_id: str
    exclusive: bool
    kind: str                               # 'delta' | 'method_swap'
    deltas: tuple[Delta, ...] = ()
    cooking_method: str | None = None       # method_swap: the replacement step
    oil_retained_g: float | None = None     # method_swap: new retention for every frying line (0 = none)
    cooked_yield_g: float | None = None     # method_swap: new batch yield, if the method changes it


# ------------------------------------------------------------------ outputs

@dataclass(frozen=True)
class Result:
    per_batch: Nutrients
    per_100g: Nutrients
    per_serving: Nutrients | None
    eaten: Nutrients | None
    raw_total_g: float
    cooked_yield_g: float
    serving_weight_g: float | None
    allergens: tuple[str, ...]
    uncleared_sources: tuple[str, ...]      # ingredient names whose data licence is not cleared
    modifier_key: str
    cooking_method: str | None = None
    lines_by_category: dict = field(default_factory=dict)  # category -> grams (batch), for plausibility


# ------------------------------------------------------------------ helpers

def _empty() -> Nutrients:
    return dict.fromkeys(NUTRIENTS, 0.0)


def _add(total: Nutrients, part: Nutrients) -> None:
    for n in NUTRIENTS:
        total[n] = None if total[n] is None or part[n] is None else total[n] + part[n]


def _scale(values: Nutrients, factor: float) -> Nutrients:
    return {n: None if v is None else v * factor for n, v in values.items()}


def _for_quantity(per_100g: Nutrients, grams: float) -> Nutrients:
    return {n: None if per_100g.get(n) is None else grams / 100 * per_100g[n] for n in NUTRIENTS}


def modifier_key(modifiers: list[Modifier] | tuple[Modifier, ...]) -> str:
    """Cache key part: the sorted modifier set."""
    return ",".join(sorted(m.id for m in modifiers))


def validate_modifiers(modifiers: list[Modifier]) -> None:
    seen: dict[str, str] = {}
    for m in modifiers:
        if m.kind not in ("delta", "method_swap"):
            raise EngineError(f"Unknown modifier kind {m.kind!r}.")
        if m.exclusive:
            if m.group_id in seen:
                raise EngineError("Those options can't be combined: pick one from each group.")
            seen[m.group_id] = m.id
    if sum(m.kind == "method_swap" for m in modifiers) > 1:
        raise EngineError("Only one cooking-method change can apply at a time.")


# ------------------------------------------------------------------ batch calculation

@dataclass
class _Batch:
    nutrients: Nutrients
    raw_total_g: float
    allergens: set
    uncleared: set
    categories: dict


def _batch(recipe: RecipeData, stack: tuple[str, ...] = ()) -> _Batch:
    if recipe.id in stack:
        raise EngineError(f"Sub-recipe loop through {recipe.name!r}.")
    if not recipe.lines:
        raise EngineError(f"{recipe.name!r} has no ingredients.")
    if recipe.cooked_yield_g is None or recipe.cooked_yield_g <= 0:
        raise EngineError(f"{recipe.name!r} needs a cooked yield above zero.")

    total, raw_total, allergens, uncleared, cats = _empty(), 0.0, set(), set(), {}
    for line in recipe.lines:
        if line.quantity_g < 0 or (line.oil_retained_g is not None and line.oil_retained_g < 0):
            raise EngineError("Quantities can't be negative.")
        if line.oil_retained_g is not None and line.oil_retained_g > line.quantity_g:
            raise EngineError("Retained oil can't be more than the oil added.")
        grams = line.oil_retained_g if line.oil_retained_g is not None else line.quantity_g
        raw_total += grams
        if line.ingredient is not None:
            ing = line.ingredient
            if ing.state not in STATES:
                raise EngineError(f"{ing.name!r} must be marked raw or cooked.")
            _add(total, _for_quantity(ing.per_100g, grams))
            allergens.update(ing.allergens)
            if not ing.licence_cleared:
                uncleared.add(ing.name)
            if ing.category:
                cats[ing.category] = cats.get(ing.category, 0.0) + grams
        else:
            sub = line.sub_recipe
            inner = _batch(sub, stack + (recipe.id,))
            sub_per_100 = _scale(inner.nutrients, 100 / sub.cooked_yield_g)
            _add(total, _for_quantity(sub_per_100, grams))
            allergens |= inner.allergens
            uncleared |= inner.uncleared
            share = grams / sub.cooked_yield_g
            for c, g in inner.categories.items():
                cats[c] = cats.get(c, 0.0) + g * share
    return _Batch(total, raw_total, allergens, uncleared, cats)


def _swap_method(recipe: RecipeData, m: Modifier) -> RecipeData:
    lines = tuple(
        replace(l, oil_retained_g=min(m.oil_retained_g, l.quantity_g))
        if (l.oil_retained_g is not None and m.oil_retained_g is not None) else l
        for l in recipe.lines
    )
    return replace(recipe, lines=lines, cooking_method=m.cooking_method or recipe.cooking_method,
                   cooked_yield_g=m.cooked_yield_g or recipe.cooked_yield_g)


def calculate(recipe: RecipeData, serving_weight_g: float | None = None, share_fraction: float = 1.0,
              modifiers: list[Modifier] | tuple[Modifier, ...] = (), require_cleared: bool = False) -> Result:
    """Calculate a recipe version, optionally for one serving, a share, and a set of modifiers.

    require_cleared=True is used for published values: every nutrient source must have a cleared licence.
    """
    modifiers = list(modifiers)
    validate_modifiers(modifiers)
    if not 0 < share_fraction <= 1:
        raise EngineError("The share must be more than 0 and at most the whole serving.")
    if serving_weight_g is not None and serving_weight_g <= 0:
        raise EngineError("A serving must weigh more than 0 g.")

    for m in modifiers:
        if m.kind == "method_swap":
            recipe = _swap_method(recipe, m)

    b = _batch(recipe)
    per_100g = _scale(b.nutrients, 100 / recipe.cooked_yield_g)
    per_serving = eaten = None
    allergens, uncleared = set(b.allergens), set(b.uncleared)

    if serving_weight_g is not None:
        per_serving = _scale(per_100g, serving_weight_g / 100)
        for m in modifiers:
            for d in m.deltas:  # deltas are stated per serving
                if d.ingredient.state not in STATES:
                    raise EngineError(f"{d.ingredient.name!r} must be marked raw or cooked.")
                _add(per_serving, _for_quantity(d.ingredient.per_100g, d.delta_g))
                if d.delta_g > 0:
                    allergens.update(d.ingredient.allergens)
                if not d.ingredient.licence_cleared:
                    uncleared.add(d.ingredient.name)
        per_serving = {n: None if v is None else max(v, 0.0) for n, v in per_serving.items()}
        eaten = _scale(per_serving, share_fraction)
    elif any(m.deltas for m in modifiers):
        raise EngineError("Modifiers that add or remove ingredients need a serving size.")

    if require_cleared and uncleared:
        raise EngineError("Some nutrient data is not cleared for use: " + ", ".join(sorted(uncleared)))

    return Result(
        per_batch=b.nutrients, per_100g=per_100g, per_serving=per_serving, eaten=eaten,
        raw_total_g=b.raw_total_g, cooked_yield_g=recipe.cooked_yield_g, serving_weight_g=serving_weight_g,
        allergens=tuple(sorted(allergens)), uncleared_sources=tuple(sorted(uncleared)),
        modifier_key=modifier_key(modifiers), cooking_method=recipe.cooking_method,
        lines_by_category=b.categories,
    )


def combine(parts: list[Nutrients]) -> Nutrients:
    """Sum several eaten portions (thali or buffet components). Unknown stays unknown."""
    total = _empty()
    for p in parts:
        _add(total, p)
    return total


# ------------------------------------------------------------------ personal targets

ACTIVITY_FACTORS = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}
GOAL_ADJUSTMENT = {"lose": -0.20, "maintain": 0.0, "gain": 0.10}
PROTEIN_G_PER_KG = {"lose": 1.6, "maintain": 1.2, "gain": 1.6}


def mifflin_st_jeor(sex: str, weight_kg: float, height_cm: float, age_years: int) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age_years
    if sex == "male":
        return base + 5
    if sex == "female":
        return base - 161
    raise EngineError("Sex for the energy estimate must be 'male' or 'female'.")


def suggested_targets(sex: str, weight_kg: float, height_cm: float, age_years: int,
                      activity: str, goal: str, calorie_floor_kcal: float) -> dict:
    """Suggested daily targets. Labelled as estimates; never below the configured floor."""
    if age_years < 18:
        raise EngineError("Targets are only available for adults.")
    if activity not in ACTIVITY_FACTORS or goal not in GOAL_ADJUSTMENT:
        raise EngineError("Unknown activity level or goal.")
    if calorie_floor_kcal is None:
        raise EngineError("The calorie floor is not configured.")
    tdee = mifflin_st_jeor(sex, weight_kg, height_cm, age_years) * ACTIVITY_FACTORS[activity]
    kcal = max(tdee * (1 + GOAL_ADJUSTMENT[goal]), calorie_floor_kcal)
    protein = PROTEIN_G_PER_KG[goal] * weight_kg
    fat = kcal * 0.30 / 9
    carbs = max(kcal - protein * 4 - fat * 9, 0) / 4
    return {"energy_kcal": kcal, "protein_g": protein, "fat_g": fat, "carbs_g": carbs,
            "floor_applied": kcal == calorie_floor_kcal, "is_estimate": True}


def clamp_user_target(requested_kcal: float, calorie_floor_kcal: float) -> float:
    """A user may edit the suggestion, but never below the floor."""
    if calorie_floor_kcal is None:
        raise EngineError("The calorie floor is not configured.")
    return max(requested_kcal, calorie_floor_kcal)


# Stored with every result so a later engine change can be traced. Set once here; changing it is an
# owner decision (fixed rule 21).
ENGINE_VERSION = "1"
