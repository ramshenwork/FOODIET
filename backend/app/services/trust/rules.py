"""Trust labels, ranges, display modes, expiry and plausibility checks (spec section 9).

Pure functions: thresholds are passed in (built from .env by trust/service.py), never read here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.services.nutrition.engine import NUTRIENTS, Result

LABELS = ("verified", "declared", "estimated", "no_data")
MODES = ("single", "band", "range")
UNITS = {"energy_kcal": "kcal", "protein_g": "g", "carbs_g": "g", "fat_g": "g", "fibre_g": "g", "sodium_mg": "mg"}
ROUND_TO = {"energy_kcal": 10, "protein_g": 1, "carbs_g": 1, "fat_g": 1, "fibre_g": 1, "sodium_mg": 10}

# Typical protein per gram of raw food, for the "protein far below what the recipe implies" check.
PROTEIN_DENSITY = {"poultry": 0.18, "meat": 0.17, "fish": 0.16, "egg": 0.12, "paneer": 0.16, "pulse": 0.20}


@dataclass(frozen=True)
class Thresholds:
    spread_verified: float
    spread_declared: float
    spread_estimated: float
    ratio_band: float
    ratio_range: float
    ratio_exclude: float
    hysteresis: float
    expiry_days: int
    energy_margin: float          # how far outside the dish's expected kcal/100 g counts as "wide"
    yield_min: float
    yield_max: float
    max_fat_share: float          # fat (g) as a share of cooked batch weight
    protein_min_ratio: float      # computed protein vs. protein implied by meat/paneer/pulse quantities
    max_energy_change: float      # versus the previous version
    heavier_step: float           # how much each "heavier than expected" signal widens `high`


# ------------------------------------------------------------------ labels and expiry

@dataclass(frozen=True)
class EffectiveTrust:
    label: str
    spread: float
    note: str | None


def effective_trust(label: str, t: Thresholds, now: datetime, verified_expires_at: datetime | None = None,
                    declared_confirmed_at: datetime | None = None, reference_spread: float | None = None) -> EffectiveTrust:
    """Apply expiry: Verified falls back to Declared after expiry; an unconfirmed Declared recipe keeps
    its label, gains a note, and takes the Estimated spread."""
    if label not in LABELS:
        raise ValueError(f"unknown trust label {label!r}")
    if label == "verified":
        if verified_expires_at and now < verified_expires_at:
            return EffectiveTrust("verified", t.spread_verified, None)
        label = "declared"  # fall back, then apply the declared rules below
    if label == "declared":
        if declared_confirmed_at and now - declared_confirmed_at <= timedelta(days=t.expiry_days):
            return EffectiveTrust("declared", t.spread_declared, None)
        since = declared_confirmed_at.strftime("%-d %b %Y") if declared_confirmed_at else "publication"
        return EffectiveTrust("declared", t.spread_estimated, f"Not reconfirmed since {since}")
    if label == "estimated":
        return EffectiveTrust("estimated", max(t.spread_estimated, reference_spread or 0.0), None)
    return EffectiveTrust("no_data", 0.0, None)


NEXT_SPREAD = {"verified": "spread_declared", "declared": "spread_estimated", "estimated": None}


def widened_high_spread(label: str, spread: float, heavier_signals: int, t: Thresholds) -> float:
    """Repeated 'heavier than expected' check-ins from different users widen `high`, up to the next label's spread."""
    widened = spread + heavier_signals * t.heavier_step
    cap_attr = NEXT_SPREAD.get(label)
    cap = getattr(t, cap_attr) if cap_attr else max(spread, t.spread_estimated) + 2 * t.heavier_step
    return min(widened, max(cap, spread))


def apply_spread(mid: float | None, spread: float, high_spread: float | None = None) -> tuple:
    if mid is None:
        return None, None, None
    return mid * (1 - spread), mid, mid * (1 + (high_spread if high_spread is not None else spread))


# ------------------------------------------------------------------ display

def _mode_for(ratio: float, t: Thresholds) -> str:
    if ratio <= t.ratio_band:
        return "single"
    if ratio <= t.ratio_range:
        return "band"
    return "range"


def display_mode(low: float, high: float, t: Thresholds, previous: str | None = None) -> str:
    """Decided by high / low. A mode changes only when the ratio crosses a boundary by more than the hysteresis."""
    if low <= 0:
        ratio = float("inf") if high > 0 else 1.0
    else:
        ratio = high / low
    mode = _mode_for(ratio, t)
    if previous is None or previous == mode or previous not in MODES:
        return mode
    up = MODES.index(mode) > MODES.index(previous)
    candidate = _mode_for(ratio - t.hysteresis if up else ratio + t.hysteresis, t)
    pick = max if up else min
    return MODES[pick(MODES.index(candidate), MODES.index(previous))]


def excluded_from_ranking(low: float | None, high: float | None, t: Thresholds) -> bool:
    if low is None or high is None:
        return True
    return low <= 0 or high / low > t.ratio_exclude


def _round(n: str, v: float) -> int:
    step = ROUND_TO[n]
    return int(round(v / step) * step)


def _fmt(v: int) -> str:
    return f"{v:,}"


def display_value(nutrient: str, low: float | None, mid: float | None, high: float | None, mode: str) -> dict | None:
    """The API's nutrient object. Values are stored unrounded; only `display` is rounded. None = unknown."""
    if mid is None:
        return None
    unit = UNITS[nutrient]
    sep = "" if unit == "%" else " "
    if mode == "single":
        text = f"{_fmt(_round(nutrient, mid))}{sep}{unit}"
    elif mode == "band":
        half = max(_round(nutrient, (high - low) / 2), ROUND_TO[nutrient])
        text = f"{_fmt(_round(nutrient, mid))}{sep}{unit}, give or take {_fmt(half)}"
    else:
        text = f"{_fmt(_round(nutrient, low))} to {_fmt(_round(nutrient, high))}{sep}{unit}"
    return {"low": low, "mid": mid, "high": high, "unit": unit, "display": text, "display_mode": mode}


def display_nutrients(values: dict, trust: EffectiveTrust, t: Thresholds, high_spread: float | None = None,
                      previous_mode: str | None = None) -> dict:
    """All nutrients for one result. Energy decides the display mode; every nutrient uses it."""
    ranges = {n: apply_spread(values.get(n), trust.spread, high_spread) for n in NUTRIENTS}
    e_low, _, e_high = ranges["energy_kcal"]
    mode = display_mode(e_low, e_high, t, previous_mode) if e_low is not None else "range"
    return {
        "display_mode": mode,
        "excluded_from_ranking": excluded_from_ranking(e_low, e_high, t),
        "nutrients": {n: display_value(n, *ranges[n], mode) for n in NUTRIENTS},
    }


def allergen_display(label: str, declared_allergens: tuple[str, ...]) -> dict:
    """Never claims a dish is free of an allergen. Estimated dishes: status unknown."""
    if label in ("estimated", "no_data"):
        return {"status": "unknown", "display": "Allergen status unknown", "allergens": []}
    return {"status": "declared", "allergens": list(declared_allergens),
            "display": ("Contains: " + ", ".join(declared_allergens)) if declared_allergens
            else "No allergens declared by the restaurant"}


# ------------------------------------------------------------------ plausibility

@dataclass(frozen=True)
class Flag:
    rule: str
    message: str        # plain language, shown to the restaurant
    detail: dict


def plausibility_checks(result: Result, t: Thresholds, expected_kcal_100g: tuple[float, float] | None = None,
                        serving_weights_g: tuple[float, ...] = (), previous_energy_100g: float | None = None) -> list[Flag]:
    flags: list[Flag] = []
    e100 = result.per_100g.get("energy_kcal")

    if expected_kcal_100g and e100 is not None:
        lo, hi = expected_kcal_100g
        if e100 < lo * (1 - t.energy_margin) or e100 > hi * (1 + t.energy_margin):
            flags.append(Flag("energy_out_of_range",
                              f"Energy works out at {e100:.0f} kcal per 100 g; this dish is usually {lo:.0f} to {hi:.0f}.",
                              {"energy_100g": e100, "expected_low": lo, "expected_high": hi}))

    ratio = result.cooked_yield_g / result.raw_total_g if result.raw_total_g > 0 else float("inf")
    if not t.yield_min <= ratio <= t.yield_max:
        flags.append(Flag("yield_implausible",
                          f"The cooked yield is {ratio:.2f} times the raw ingredients; expected between "
                          f"{t.yield_min} and {t.yield_max}.",
                          {"yield_ratio": ratio, "raw_total_g": result.raw_total_g, "cooked_yield_g": result.cooked_yield_g}))

    for w in serving_weights_g:
        if w > result.cooked_yield_g:
            flags.append(Flag("serving_exceeds_batch",
                              f"A {w:.0f} g serving is larger than the whole {result.cooked_yield_g:.0f} g batch.",
                              {"serving_weight_g": w, "cooked_yield_g": result.cooked_yield_g}))

    fat = result.per_batch.get("fat_g")
    if fat is not None and result.cooked_yield_g > 0 and fat / result.cooked_yield_g > t.max_fat_share:
        flags.append(Flag("fat_share_high",
                          f"Fat and oil make up {fat / result.cooked_yield_g:.0%} of the cooked dish, above "
                          f"{t.max_fat_share:.0%}. Check the oil quantity and how much oil stays in the food.",
                          {"fat_g": fat, "cooked_yield_g": result.cooked_yield_g}))

    implied = sum(PROTEIN_DENSITY[c] * g for c, g in result.lines_by_category.items() if c in PROTEIN_DENSITY)
    protein = result.per_batch.get("protein_g")
    if implied > 0 and protein is not None and protein < implied * t.protein_min_ratio:
        flags.append(Flag("protein_low",
                          f"Protein works out at {protein:.0f} g, far below the {implied:.0f} g the stated meat, "
                          f"paneer or pulses imply. Check the ingredient choices.",
                          {"protein_g": protein, "implied_g": implied}))

    if previous_energy_100g and e100 is not None:
        change = abs(e100 - previous_energy_100g) / previous_energy_100g
        if change > t.max_energy_change:
            flags.append(Flag("energy_changed",
                              f"Energy changed by {change:.0%} from the previous version.",
                              {"energy_100g": e100, "previous_energy_100g": previous_energy_100g}))
    return flags
