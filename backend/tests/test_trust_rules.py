"""Trust labels, display, expiry and plausibility (spec section 9)."""
from datetime import UTC, datetime, timedelta

import pytest

from app.services.nutrition.engine import Line, RecipeData, calculate
from app.services.trust import rules
from app.services.trust.service import thresholds
from tests.engine_fixtures import ingredients, recipe, serving

T = thresholds()
NOW = datetime(2026, 11, 18, tzinfo=UTC)


@pytest.mark.parametrize("label,mode", [("verified", "single"), ("declared", "band"), ("estimated", "range")])
def test_default_spreads_give_expected_modes(label, mode):
    trust = rules.effective_trust(label, T, NOW, verified_expires_at=NOW + timedelta(days=1),
                                  declared_confirmed_at=NOW)
    low, _, high = rules.apply_spread(520.0, trust.spread)
    assert rules.display_mode(low, high, T) == mode


def test_display_strings_match_spec_examples():
    assert rules.display_value("energy_kcal", 505, 520, 535, "single")["display"] == "520 kcal"
    assert rules.display_value("energy_kcal", 460, 520, 580, "band")["display"] == "520 kcal, give or take 60"
    assert rules.display_value("energy_kcal", 450, 580, 700, "range")["display"] == "450 to 700 kcal"
    assert rules.display_value("protein_g", 15.4, 18.2, 21.3, "range")["display"] == "15 to 21 g"
    assert rules.display_value("energy_kcal", 1234, 1234, 1234, "single")["display"] == "1,230 kcal"


def test_unknown_value_is_null_never_zero():
    assert rules.display_value("sodium_mg", None, None, None, "single") is None
    out = rules.display_nutrients({"energy_kcal": 500.0, "protein_g": 20.0, "carbs_g": 50.0, "fat_g": 20.0,
                                   "fibre_g": 3.0, "sodium_mg": None},
                                  rules.EffectiveTrust("declared", T.spread_declared, None), T)
    assert out["nutrients"]["sodium_mg"] is None and out["nutrients"]["energy_kcal"]["mid"] == 500


def test_mode_boundaries_and_exclusion():
    assert rules.display_mode(100, 125, T) == "single"
    assert rules.display_mode(100, 150, T) == "band"
    assert rules.display_mode(100, 151, T) == "range"
    assert not rules.excluded_from_ranking(100, 250, T)
    assert rules.excluded_from_ranking(100, 251, T)


def test_hysteresis_prevents_flicker():
    assert rules.display_mode(100, 152, T, previous="band") == "band"      # just over 1.5
    assert rules.display_mode(100, 156, T, previous="band") == "range"     # clearly over
    assert rules.display_mode(100, 147, T, previous="range") == "range"    # just under
    assert rules.display_mode(100, 140, T, previous="range") == "band"


def test_verified_falls_back_after_90_days_time_shifted():
    granted = NOW
    expires = granted + timedelta(days=T.expiry_days)
    assert rules.effective_trust("verified", T, NOW + timedelta(days=89), verified_expires_at=expires,
                                 declared_confirmed_at=NOW).label == "verified"
    later = rules.effective_trust("verified", T, NOW + timedelta(days=91), verified_expires_at=expires,
                                  declared_confirmed_at=NOW + timedelta(days=60))
    assert later.label == "declared" and later.spread == T.spread_declared


def test_unconfirmed_declared_keeps_label_gains_note_and_estimated_spread():
    t = rules.effective_trust("declared", T, NOW, declared_confirmed_at=NOW - timedelta(days=91))
    assert t.label == "declared" and t.spread == T.spread_estimated and t.note.startswith("Not reconfirmed since")


def test_estimated_uses_wider_reference_spread():
    assert rules.effective_trust("estimated", T, NOW).spread == T.spread_estimated
    assert rules.effective_trust("estimated", T, NOW, reference_spread=0.4).spread == 0.4
    assert rules.effective_trust("estimated", T, NOW, reference_spread=0.1).spread == T.spread_estimated


def test_heavier_checkins_widen_high_up_to_next_label():
    assert rules.widened_high_spread("declared", T.spread_declared, 1, T) == pytest.approx(T.spread_declared + T.heavier_step)
    assert rules.widened_high_spread("declared", T.spread_declared, 50, T) == pytest.approx(T.spread_estimated)
    assert rules.widened_high_spread("verified", T.spread_verified, 50, T) == pytest.approx(T.spread_declared)
    low, mid, high = rules.apply_spread(500, 0.15, high_spread=0.25)
    assert (low, mid, high) == (pytest.approx(425), 500, pytest.approx(625))


def test_allergens_never_claimed_absent():
    assert rules.allergen_display("estimated", ("milk",))["display"] == "Allergen status unknown"
    assert rules.allergen_display("no_data", ())["status"] == "unknown"
    declared = rules.allergen_display("declared", ())
    assert "free" not in declared["display"].lower()


# ------------------------------------------------------------------ plausibility

def rules_hit(result, **kw):
    return {f.rule for f in rules.plausibility_checks(result, T, **kw)}


def test_500g_oil_in_250g_serving_is_held():
    oil = ingredients()["Vegetable oil (refined)"]
    potato = ingredients()["Potato"]
    r = RecipeData(id="x", name="Oily", cooked_yield_g=250, lines=(Line(500, oil), Line(100, potato)))
    hit = rules_hit(calculate(r, 250), serving_weights_g=(250,))
    assert "fat_share_high" in hit


def test_yield_and_serving_checks():
    r = RecipeData(id="x", name="X", cooked_yield_g=100, lines=(Line(1000, ingredients()["Potato"]),))
    assert {"yield_implausible", "serving_exceeds_batch"} <= rules_hit(calculate(r), serving_weights_g=(150,))


def test_energy_far_outside_dish_band():
    res = calculate(recipe("Samosa"), 85)
    assert "energy_out_of_range" not in rules_hit(res, expected_kcal_100g=(240, 360))
    assert "energy_out_of_range" in rules_hit(res, expected_kcal_100g=(60, 120))


def test_protein_far_below_what_meat_implies():
    fake_chicken = ingredients()["Potato"].__class__(**{**ingredients()["Potato"].__dict__, "category": "poultry", "name": "Chicken?"})
    r = RecipeData(id="x", name="X", cooked_yield_g=900, lines=(Line(1000, fake_chicken),))
    assert "protein_low" in rules_hit(calculate(r))
    assert "protein_low" not in rules_hit(calculate(recipe("Chicken Tikka")))


def test_energy_change_from_previous_version():
    res = calculate(recipe("Dal Tadka"))
    e = res.per_100g["energy_kcal"]
    assert "energy_changed" not in rules_hit(res, previous_energy_100g=e * 1.2)
    assert "energy_changed" in rules_hit(res, previous_energy_100g=e * 1.5)
