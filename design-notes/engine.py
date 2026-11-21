"""Nutrition engine: recipe version + modifier set -> P10/P50/P90 per serving.

Pure Python, no dependencies. Deterministic: the RNG is seeded from the cache key,
so the same inputs always give the same stored numbers (needed for the audit trail).
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field, replace

ENGINE_VERSION = "1.0.0"
NUTRIENTS = ("kcal", "protein", "fat", "carb")

# Default spread applied to a line declared as a single number, by tier.
TIER_SPREAD = {"A": 0.07, "B": 0.15, "C": 0.25, "D": 0.35}

DEFAULT_CONFIG = {
    "band_ratio": 1.25,
    "range_ratio": 1.50,
    "unranked_ratio": 2.50,
    "unranked_min_width_kcal": 150,
    "hysteresis": 0.05,
    "requested_compliance": 0.70,
    "fat_correlation": 0.80,  # share of draws where a fat line follows the kitchen-wide draw
}


@dataclass(frozen=True)
class Ingredient:
    name: str
    per_100g: dict  # nutrient -> value per 100 g raw
    added_fat: bool = False  # oil/ghee/butter/cream: quantities move together within a kitchen


@dataclass(frozen=True)
class Method:
    id: str
    absorb: tuple = (0.0, 0.0, 0.0)  # (min, mode, max) oil uptake as fraction of food weight


@dataclass(frozen=True)
class Line:
    key: str
    ingredient: Ingredient
    qty: tuple  # (min, mode, max) grams; equal values = declared as a point
    stage: str
    method: Method


@dataclass(frozen=True)
class Recipe:
    version_id: int
    lines: tuple
    tier: str
    servings: float = 1.0
    frying_oil: Ingredient | None = None


@dataclass(frozen=True)
class Modifier:
    id: int
    group: str
    kind: str  # 'delta' | 'method_swap'
    assurance: str  # 'requested' | 'measured'
    # delta: {"scale": {line_key: factor}, "add": [Line, ...]}
    # method_swap: {"stage": str, "method": Method}
    spec: dict = field(hash=False, compare=False)


class InvalidModifiers(ValueError):
    pass


# ------------------------------------------------------------------ modifiers

def validate(modifiers: list[Modifier]) -> None:
    seen = {}
    for m in modifiers:
        if m.group in seen:
            raise InvalidModifiers(f"'{seen[m.group]}' and modifier {m.id} are in exclusive group '{m.group}'")
        seen[m.group] = m.id


def cache_key(recipe: Recipe, modifiers: list[Modifier], ingredient_db_version: str) -> str:
    mods = ",".join(str(i) for i in sorted(m.id for m in modifiers))
    return f"{recipe.version_id}|{mods}|{ENGINE_VERSION}|{ingredient_db_version}"


def _apply_method_swaps(recipe: Recipe, modifiers: list[Modifier]) -> Recipe:
    """Method swaps replace a step, so they rebuild the recipe rather than subtracting."""
    lines = list(recipe.lines)
    for m in modifiers:
        if m.kind == "method_swap":
            lines = [replace(l, method=m.spec["method"]) if l.stage == m.spec["stage"] else l for l in lines]
    return replace(recipe, lines=tuple(lines))


# ------------------------------------------------------------------ sampling

def _widen(qty: tuple, tier: str) -> tuple:
    lo, mode, hi = qty
    if lo == hi:  # declared as a point: tier sets the uncertainty
        s = TIER_SPREAD[tier]
        return (mode * (1 - s), mode, mode * (1 + s))
    return qty


def _tri_quantile(tri: tuple, u: float) -> float:
    """Inverse CDF of a triangular distribution."""
    lo, mode, hi = tri
    if lo == hi:
        return lo
    c = (mode - lo) / (hi - lo)
    if u < c:
        return lo + ((hi - lo) * (mode - lo) * u) ** 0.5
    return hi - ((hi - lo) * (hi - mode) * (1 - u)) ** 0.5


def _sample(rng: random.Random, tri: tuple) -> float:
    return _tri_quantile(tri, rng.random())


def _line_nutrients(rng, line: Line, grams: float, frying_oil, out: dict) -> None:
    for n in NUTRIENTS:
        out[n] += grams * line.ingredient.per_100g[n] / 100
    if line.method.absorb[2] > 0 and frying_oil is not None:
        oil_g = grams * _sample(rng, line.method.absorb)
        for n in NUTRIENTS:
            out[n] += oil_g * frying_oil.per_100g[n] / 100


def compute(recipe: Recipe, modifiers: list[Modifier], ingredient_db_version: str = "v1",
            draws: int = 2000, config: dict = DEFAULT_CONFIG) -> dict:
    validate(modifiers)
    key = cache_key(recipe, modifiers, ingredient_db_version)
    rng = random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:16], 16))

    # Method swaps are applied deterministically; 'requested' swaps are still treated as
    # compliance-uncertain per draw below.
    swapped = _apply_method_swaps(recipe, [m for m in modifiers if m.kind == "method_swap"])
    deltas = [m for m in modifiers if m.kind == "delta"]
    swaps = [m for m in modifiers if m.kind == "method_swap"]

    samples = {n: [] for n in NUTRIENTS}
    for _ in range(draws):
        complied = {m.id: (m.assurance == "measured" or rng.random() < config["requested_compliance"])
                    for m in modifiers}
        base = swapped if all(complied[m.id] for m in swaps) else recipe
        scale = {}
        extra = []
        for m in deltas:
            if complied[m.id]:
                for k, f in m.spec.get("scale", {}).items():
                    scale[k] = scale.get(k, 1.0) * f
                extra.extend(m.spec.get("add", []))
        tot = dict.fromkeys(NUTRIENTS, 0.0)
        # One "heavy hand" draw shared by all added-fat lines, blended with per-line noise.
        # Independent sampling lets butter/cream/oil highs and lows cancel and understates the range.
        fat_u = rng.random()
        rho = config["fat_correlation"]
        for line in (*base.lines, *extra):
            u = rng.random()
            if line.ingredient.added_fat:
                u = fat_u if rng.random() < rho else u
            g = _tri_quantile(_widen(line.qty, recipe.tier), u) * scale.get(line.key, 1.0)
            _line_nutrients(rng, line, g, recipe.frying_oil, tot)
        for n in NUTRIENTS:
            samples[n].append(tot[n] / recipe.servings)

    result = {"cache_key": key, "tier": recipe.tier}
    for n in NUTRIENTS:
        s = sorted(samples[n])
        result[n] = tuple(round(s[int(q * (draws - 1))], 1) for q in (0.1, 0.5, 0.9))
    return result


# ------------------------------------------------------------------ display and ranking

_MODES = ("single", "band", "range", "range_unranked")


def _ratio(kcal: tuple) -> float:
    return kcal[2] / kcal[0] if kcal[0] > 0 else float("inf")


def display_mode(kcal: tuple, previous: str | None = None, config: dict = DEFAULT_CONFIG) -> str:
    """Pick a display mode; with a previous mode, only move once the ratio clears the boundary by `hysteresis`."""
    r = _ratio(kcal)
    width = kcal[2] - kcal[0]
    bounds = (config["band_ratio"], config["range_ratio"], config["unranked_ratio"])

    def raw(ratio):
        idx = sum(ratio > b for b in bounds)
        if idx == 3 and width < config["unranked_min_width_kcal"]:
            idx = 2  # wide in ratio but small in absolute kcal (e.g. a salad): still rankable
        return _MODES[idx]

    mode = raw(r)
    if previous is None or mode == previous:
        return mode
    h = config["hysteresis"]
    # Moving up needs ratio > boundary + h; moving down needs ratio < boundary - h.
    up = _MODES.index(mode) > _MODES.index(previous)
    candidate = _MODES.index(raw(r - h if up else r + h))
    pick = max if up else min
    return _MODES[pick(candidate, _MODES.index(previous))]


def rank_score(result: dict, goal: str, mode: str) -> float | None:
    """Conservative score: fat loss uses the upper kcal estimate, protein the lower protein estimate.
    Returns None when the dish must not appear in 'fits your goal' rankings."""
    if mode == "range_unranked":
        return None
    if goal == "fat_loss":
        return -result["kcal"][2]
    if goal == "protein":
        return result["protein"][0] / max(result["kcal"][2], 1) * 100  # g protein per 100 kcal, worst case
    raise ValueError(goal)


def best_healthify(recipe: Recipe, candidates: list[Modifier], goal: str, **kw) -> tuple:
    """Precomputed per dish and goal: the single valid modifier that most improves the conservative score."""
    base = compute(recipe, [], **kw)
    base_score = rank_score(base, goal, "range")
    best = (None, 0.0)
    for m in candidates:
        gain = rank_score(compute(recipe, [m], **kw), goal, "range") - base_score
        if gain > best[1]:
            best = (m.id, round(gain, 1))
    return best
