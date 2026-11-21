"""Unit tests for the pure nutrition engine (spec section 9)."""
import pytest

from app.services.nutrition.engine import (Delta, EngineError, IngredientData, Line, Modifier, RecipeData,
                                           calculate, clamp_user_target, combine, mifflin_st_jeor, modifier_key,
                                           suggested_targets)
from tests.engine_fixtures import ingredients, recipe

FULL = {"energy_kcal": 100, "protein_g": 10, "carbs_g": 10, "fat_g": 2, "fibre_g": 1, "sodium_mg": 50}


def ing(name, state="raw", cleared=True, **per):
    return IngredientData(id=name, name=name, state=state, per_100g={**FULL, **per}, licence_cleared=cleared)


def simple(yield_g=200, *lines):
    return RecipeData(id="r", name="R", lines=tuple(lines), cooked_yield_g=yield_g)


def test_formula_batch_per_100g_serving_and_share():
    r = simple(200, Line(150, ing("a", energy_kcal=200)), Line(50, ing("b", energy_kcal=400)))
    res = calculate(r, serving_weight_g=120, share_fraction=0.5)
    assert res.per_batch["energy_kcal"] == pytest.approx(150 * 2 + 50 * 4)          # 500
    assert res.per_100g["energy_kcal"] == pytest.approx(500 / 200 * 100)             # 250
    assert res.per_serving["energy_kcal"] == pytest.approx(250 * 120 / 100)          # 300
    assert res.eaten["energy_kcal"] == pytest.approx(150)


def test_results_are_unrounded():
    r = simple(300, Line(100, ing("a", energy_kcal=101)))
    assert calculate(r).per_100g["energy_kcal"] == pytest.approx(101 / 3)


def test_frying_oil_counts_retained_not_added():
    oil = ing("oil", energy_kcal=900, fat_g=100)
    r = simple(500, Line(400, ing("potato", energy_kcal=80)), Line(1000, oil, oil_retained_g=60))
    res = calculate(r)
    assert res.per_batch["energy_kcal"] == pytest.approx(400 * 0.8 + 60 * 9)
    assert res.raw_total_g == pytest.approx(460)


def test_retained_oil_cannot_exceed_added():
    with pytest.raises(EngineError):
        calculate(simple(100, Line(10, ing("oil"), oil_retained_g=20)))


def test_sub_recipe_contributes_its_per_100g():
    gravy = simple(500, Line(500, ing("g", energy_kcal=120)))  # 120 kcal/100 g
    gravy = RecipeData(id="gravy", name="Gravy", lines=gravy.lines, cooked_yield_g=400)  # reduced: 150 kcal/100 g
    dish = RecipeData(id="dish", name="Dish", cooked_yield_g=300,
                      lines=(Line(200, sub_recipe=gravy), Line(100, ing("p", energy_kcal=260))))
    assert calculate(dish).per_batch["energy_kcal"] == pytest.approx(200 * 1.5 + 260)


def test_sub_recipe_loop_is_rejected():
    a = RecipeData(id="a", name="A", cooked_yield_g=100, lines=(Line(10, ing("x")),))
    b = RecipeData(id="b", name="B", cooked_yield_g=100, lines=(Line(10, sub_recipe=a),))
    looped = RecipeData(id="a", name="A", cooked_yield_g=100, lines=(Line(10, sub_recipe=b),))
    with pytest.raises(EngineError, match="loop"):
        calculate(looped)


def test_unknown_nutrient_is_unknown_not_partial_sum():
    r = simple(200, Line(100, ing("a")), Line(5, ing("herb", sodium_mg=None)))
    res = calculate(r, serving_weight_g=100)
    assert res.per_100g["sodium_mg"] is None and res.per_serving["sodium_mg"] is None
    assert res.per_100g["energy_kcal"] is not None


def test_ingredient_without_state_is_rejected_but_stated_mix_is_allowed():
    with pytest.raises(EngineError, match="raw or cooked"):
        calculate(simple(100, Line(50, ing("rice", state=None))))
    ok = calculate(simple(300, Line(100, ing("rice", state="raw")), Line(100, ing("cooked rice", state="cooked"))))
    assert ok.per_batch["energy_kcal"] == pytest.approx(200)


@pytest.mark.parametrize("bad", [0, -5])
def test_yield_must_be_positive(bad):
    with pytest.raises(EngineError):
        calculate(simple(bad, Line(10, ing("a"))))


def test_same_inputs_same_outputs():
    assert calculate(recipe("Butter Chicken"), 250) == calculate(recipe("Butter Chicken"), 250)


def test_allergens_collected_through_sub_recipes():
    res = calculate(recipe("Paneer Butter Masala"), 250)
    assert set(res.allergens) == {"milk", "tree_nut"}


def test_require_cleared_blocks_uncleared_sources():
    with pytest.raises(EngineError, match="not cleared"):
        calculate(recipe("Dal Tadka", cleared=False), 180, require_cleared=True)
    assert calculate(recipe("Dal Tadka", cleared=False), 180).uncleared_sources  # still reported in previews


# ------------------------------------------------------------------ modifiers

BUTTER = ingredients()["Butter, salted"]
NO_BUTTER = Modifier("m-no-butter", "butter", True, "delta", deltas=(Delta(BUTTER, -10),))
EXTRA_BUTTER = Modifier("m-extra-butter", "butter", True, "delta", deltas=(Delta(BUTTER, 10),))
NO_CREAM = Modifier("m-no-cream", "cream", True, "delta",
                    deltas=(Delta(ingredients()["Fresh cream (25% fat)"], -15),))


def test_delta_modifier_removes_exact_quantity_per_serving():
    base = calculate(recipe("Butter Chicken"), 250)
    less = calculate(recipe("Butter Chicken"), 250, modifiers=[NO_BUTTER])
    assert base.per_serving["energy_kcal"] - less.per_serving["energy_kcal"] == pytest.approx(71.7)
    assert base.per_serving["fat_g"] - less.per_serving["fat_g"] == pytest.approx(8.1)


def test_exclusive_group_cannot_combine():
    with pytest.raises(EngineError, match="can't be combined"):
        calculate(recipe("Butter Chicken"), 250, modifiers=[NO_BUTTER, EXTRA_BUTTER])
    calculate(recipe("Butter Chicken"), 250, modifiers=[NO_BUTTER, NO_CREAM])  # different groups: fine


def test_modifier_key_is_sorted_set():
    assert modifier_key([NO_CREAM, NO_BUTTER]) == modifier_key([NO_BUTTER, NO_CREAM]) == "m-no-butter,m-no-cream"
    assert calculate(recipe("Butter Chicken"), 250, modifiers=[NO_CREAM, NO_BUTTER]).modifier_key == "m-no-butter,m-no-cream"


def test_method_swap_replaces_oil_retention_and_recalculates():
    grilled = Modifier("m-grill", "method", True, "method_swap", cooking_method="grill", oil_retained_g=0, cooked_yield_g=950)
    fried = calculate(recipe("Chicken 65"), 200)
    swapped = calculate(recipe("Chicken 65"), 200, modifiers=[grilled])
    assert swapped.cooking_method == "grill"
    assert swapped.per_batch["fat_g"] == pytest.approx(fried.per_batch["fat_g"] - 150)
    assert swapped.per_serving["energy_kcal"] < fried.per_serving["energy_kcal"] - 150


def test_delta_needs_a_serving():
    with pytest.raises(EngineError, match="serving"):
        calculate(recipe("Butter Chicken"), modifiers=[NO_BUTTER])


def test_delta_never_drives_a_value_negative():
    r = simple(100, Line(5, ing("a")))
    big = Modifier("m", "g", True, "delta", deltas=(Delta(ing("a"), -500),))
    assert calculate(r, 100, modifiers=[big]).per_serving["energy_kcal"] == 0


@pytest.mark.parametrize("share", [0, 1.5, -0.2])
def test_share_must_be_a_fraction_of_the_serving(share):
    with pytest.raises(EngineError):
        calculate(recipe("Roti"), 80, share_fraction=share)


# ------------------------------------------------------------------ combine and targets

def test_combine_keeps_unknown_unknown():
    a = {"energy_kcal": 100.0, "protein_g": 5.0, "carbs_g": 1.0, "fat_g": 1.0, "fibre_g": 1.0, "sodium_mg": 10.0}
    b = {**a, "sodium_mg": None}
    total = combine([a, b])
    assert total["energy_kcal"] == 200 and total["sodium_mg"] is None


def test_mifflin_st_jeor_reference_values():
    assert mifflin_st_jeor("male", 70, 175, 30) == pytest.approx(1648.75)
    assert mifflin_st_jeor("female", 60, 160, 30) == pytest.approx(1289.0)


def test_targets_respect_floor_and_age():
    t = suggested_targets("female", 45, 150, 40, "sedentary", "lose", calorie_floor_kcal=1400)
    assert t["energy_kcal"] == 1400 and t["floor_applied"] and t["is_estimate"]
    with pytest.raises(EngineError):
        suggested_targets("male", 60, 170, 17, "light", "maintain", 1400)
    with pytest.raises(EngineError, match="floor"):
        suggested_targets("male", 60, 170, 30, "light", "maintain", None)
    assert clamp_user_target(900, 1400) == 1400 and clamp_user_target(2100, 1400) == 2100
