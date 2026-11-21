"""Run: python3 -m unittest test_engine -v
Ingredient values are rough illustrative figures, not IFCT data."""
import unittest

from engine import (Ingredient, InvalidModifiers, Line, Method, Modifier, Recipe, best_healthify,
                    compute, display_mode, rank_score)

ING = {
    "chicken": Ingredient("chicken boneless", {"kcal": 120, "protein": 21, "fat": 4, "carb": 0}),
    "butter": Ingredient("butter", {"kcal": 720, "protein": 0.9, "fat": 81, "carb": 0.1}, added_fat=True),
    "cream": Ingredient("cream 25%", {"kcal": 245, "protein": 2, "fat": 25, "carb": 3}, added_fat=True),
    "oil": Ingredient("oil", {"kcal": 900, "protein": 0, "fat": 100, "carb": 0}, added_fat=True),
    "tomato": Ingredient("tomato", {"kcal": 20, "protein": 0.9, "fat": 0.2, "carb": 3.6}),
    "cashew": Ingredient("cashew", {"kcal": 580, "protein": 18, "fat": 46, "carb": 30}),
    "besan": Ingredient("besan", {"kcal": 360, "protein": 22, "fat": 6, "carb": 58}),
}
SIMMER = Method("simmer")
DEEP_FRY = Method("deep_fry", (0.08, 0.12, 0.20))
GRILL = Method("grill")


def butter_chicken(tier="D"):
    return Recipe(1, (
        Line("chicken", ING["chicken"], (150, 150, 150), "gravy", SIMMER),
        Line("butter", ING["butter"], (10, 20, 35), "finish", SIMMER),
        Line("cream", ING["cream"], (15, 30, 60), "finish", SIMMER),
        Line("oil", ING["oil"], (5, 10, 20), "tadka", SIMMER),
        Line("tomato", ING["tomato"], (100, 120, 140), "gravy", SIMMER),
        Line("cashew", ING["cashew"], (5, 10, 15), "gravy", SIMMER),
    ), tier=tier)


def chicken_pakora():
    return Recipe(2, (
        Line("chicken", ING["chicken"], (200, 200, 200), "fry", DEEP_FRY),
        Line("besan", ING["besan"], (40, 40, 40), "fry", DEEP_FRY),
    ), tier="C", frying_oil=ING["oil"])


HALF_BUTTER_REQ = Modifier(10, "butter_level", "delta", "requested", {"scale": {"butter": 0.5}})
HALF_BUTTER_MEAS = Modifier(11, "butter_level", "delta", "measured", {"scale": {"butter": 0.5}})
NO_CREAM = Modifier(12, "cream_level", "delta", "measured", {"scale": {"cream": 0}})
GRILLED = Modifier(20, "method", "method_swap", "measured", {"stage": "fry", "method": GRILL})


class Engine(unittest.TestCase):
    def test_butter_chicken_range_matches_hand_calc(self):
        r = compute(butter_chicken(), [])
        p10, p50, p90 = r["kcal"]
        self.assertTrue(520 < p50 < 680, r["kcal"])
        self.assertTrue(420 < p10 < 520 and 700 < p90 < 870, r["kcal"])
        # Fat lines drive the spread: protein is relatively tighter than calories.
        self.assertLess(r["protein"][2] / r["protein"][0], p90 / p10)

    def test_deterministic(self):
        self.assertEqual(compute(butter_chicken(), []), compute(butter_chicken(), []))

    def test_cache_key_order_independent_and_versioned(self):
        a = compute(butter_chicken(), [NO_CREAM, HALF_BUTTER_MEAS])
        b = compute(butter_chicken(), [HALF_BUTTER_MEAS, NO_CREAM])
        self.assertEqual(a, b)
        self.assertNotEqual(a["cache_key"], compute(butter_chicken(), [NO_CREAM, HALF_BUTTER_MEAS],
                                                    ingredient_db_version="v2")["cache_key"])

    def test_exclusive_group(self):
        with self.assertRaises(InvalidModifiers):
            compute(butter_chicken(), [HALF_BUTTER_REQ, HALF_BUTTER_MEAS])

    def test_requested_modifier_shifts_less_and_stays_wider(self):
        base = compute(butter_chicken(), [])["kcal"]
        req = compute(butter_chicken(), [HALF_BUTTER_REQ])["kcal"]
        meas = compute(butter_chicken(), [HALF_BUTTER_MEAS])["kcal"]
        self.assertLess(meas[1], req[1])
        self.assertLess(req[1], base[1])
        self.assertGreater(req[2] - req[0], meas[2] - meas[0])
        self.assertGreater(req[2] - meas[2], 25)  # kitchen may ignore it: upper bound stays higher

    def test_method_swap_removes_absorbed_oil(self):
        fried = compute(chicken_pakora(), [])
        grilled = compute(chicken_pakora(), [GRILLED])
        self.assertGreater(fried["kcal"][1] - grilled["kcal"][1], 150)
        self.assertAlmostEqual(fried["protein"][1], grilled["protein"][1], delta=1)

    def test_point_declarations_widen_by_tier(self):
        c = compute(chicken_pakora(), [GRILLED])["kcal"]
        a = compute(Recipe(2, chicken_pakora().lines, "A", frying_oil=ING["oil"]), [GRILLED])["kcal"]
        self.assertLess(a[2] - a[0], c[2] - c[0])


class Display(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(display_mode((500, 550, 600)), "single")
        self.assertEqual(display_mode((500, 600, 700)), "band")
        self.assertEqual(display_mode((450, 600, 800)), "range")
        self.assertEqual(display_mode((300, 600, 900)), "range_unranked")

    def test_small_absolute_width_stays_ranked(self):
        self.assertEqual(display_mode((50, 90, 140)), "range")  # 2.8x but only 90 kcal wide

    def test_hysteresis(self):
        self.assertEqual(display_mode((100, 0, 152), previous="band"), "band")    # just over 1.5
        self.assertEqual(display_mode((100, 0, 156), previous="band"), "range")   # clearly over
        self.assertEqual(display_mode((100, 0, 148), previous="range"), "range")  # just under
        self.assertEqual(display_mode((100, 0, 152), previous="single"), "band")  # big jump lands one step short

    def test_conservative_ranking(self):
        tight = {"kcal": (580, 600, 620), "protein": (30, 31, 32)}
        wide = {"kcal": (380, 550, 820), "protein": (24, 31, 38)}
        # Wide dish has the better midpoint but loses on its worst case.
        self.assertGreater(rank_score(tight, "fat_loss", "single"), rank_score(wide, "fat_loss", "range"))
        self.assertIsNone(rank_score(wide, "fat_loss", "range_unranked"))

    def test_healthify_picks_biggest_fat_cut(self):
        mod_id, gain = best_healthify(butter_chicken(), [HALF_BUTTER_MEAS, NO_CREAM], "fat_loss")
        self.assertIn(mod_id, (11, 12))
        self.assertGreater(gain, 30)


if __name__ == "__main__":
    unittest.main()
