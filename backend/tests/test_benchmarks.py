"""Benchmark recipes from backend/seed. Expected values were computed by hand-written arithmetic directly
from the seed files, independently of the engine.

PENDING REVIEW: the spec requires these to be hand-checked by a nutrition professional. The ingredient
values are builder placeholders, so these tests prove the engine's arithmetic, not the nutrition facts.
"""
import pytest

from app.services.nutrition.engine import calculate, combine
from app.services.trust import rules
from app.services.trust.service import thresholds
from tests.engine_fixtures import dish_band, recipe, serving

# (reference recipe, kcal per serving, protein g per serving, fat g per serving)
BENCHMARKS = [
    ("Paneer Butter Masala", 543.10, 23.65, 43.93),            # gravy with a sub-recipe
    ("Hyderabadi Chicken Dum Biryani", 609.23, 24.91, 24.28),  # biryani
    ("Kolkata Chicken Biryani", 652.31, 23.48, 24.67),         # regional variant
    ("Plain Dosa", 261.24, 6.90, 6.46),                        # dosa
    ("Masala Dosa", 430.35, 10.14, 12.99),
    ("Idli", 246.76, 8.18, 0.55),
    ("Sambar", 122.28, 5.59, 2.82),
    ("Dal Tadka", 170.05, 8.15, 4.84),
    ("Samosa", 249.19, 3.67, 14.38),                           # fried item (retained oil)
    ("Chicken Tikka", 412.78, 46.95, 22.11),
    ("Chicken 65", 580.66, 39.05, 41.16),                      # fried item
    ("Roti", 194.29, 6.86, 1.09),
]


@pytest.mark.parametrize("name,kcal,protein,fat", BENCHMARKS)
def test_benchmark_per_serving(name, kcal, protein, fat):
    res = calculate(recipe(name), serving(name))
    assert res.per_serving["energy_kcal"] == pytest.approx(kcal, abs=0.01)
    assert res.per_serving["protein_g"] == pytest.approx(protein, abs=0.01)
    assert res.per_serving["fat_g"] == pytest.approx(fat, abs=0.01)


@pytest.mark.parametrize("name", [b[0] for b in BENCHMARKS])
def test_benchmark_within_dish_band_and_passes_checks(name):
    res = calculate(recipe(name), serving(name))
    lo, hi = dish_band(name)
    assert lo <= res.per_100g["energy_kcal"] <= hi
    assert rules.plausibility_checks(res, thresholds(), (lo, hi), (serving(name),)) == []


def test_benchmark_thali_component_by_component():
    parts = [("Dal Tadka", 1.0), ("Jeera Rice", 1.0), ("Roti", 1.0), ("Aloo Gobi", 1.0), ("Curd (katori)", 0.5)]
    eaten = [calculate(recipe(n), serving(n), share_fraction=s).eaten for n, s in parts]
    total = combine(eaten)
    assert total["energy_kcal"] == pytest.approx(170.05 + 281.21 + 194.29 + 151.09 + 61.00 * 0.5, abs=0.05)


def test_sodium_unknown_propagates_through_sub_recipe():
    res = calculate(recipe("Paneer Butter Masala"), 250)
    assert res.per_serving["sodium_mg"] is None   # kasuri methi has no sodium value in the seed
