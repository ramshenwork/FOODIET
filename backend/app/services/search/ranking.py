"""Hard filters and goal-fit ranking (spec section 9). Pure functions; weights come from configuration.

Filters run before ranking. Ranking uses goal fit and data trust only; no paid boost exists (fixed rule 13).
For calorie fit the upper estimate (high) is used; for protein fit the lower estimate (low).
"""
from __future__ import annotations

from dataclasses import dataclass, field

DIET_ALLOWS = {"veg": {"veg"}, "egg": {"veg", "egg"}, "non_veg": {"veg", "egg", "non_veg"}}
TRUST_SCORE = {"verified": 1.0, "declared": 0.8, "estimated": 0.4}


@dataclass(frozen=True)
class Facts:
    """What ranking needs to know about one dish, all computed by the server."""
    diet_class: str | None
    diet_tags: frozenset
    label: str                         # verified | declared | estimated | no_data
    allergen_status: str               # declared | unknown
    declared_allergens: frozenset
    energy_low: float | None
    energy_high: float | None
    protein_low: float | None
    excluded_from_ranking: bool
    price_inr: float | None
    relevance: float = 1.0


@dataclass(frozen=True)
class Stated:
    diet_type: str | None
    restrictions: frozenset = field(default_factory=frozenset)
    allergies: frozenset = field(default_factory=frozenset)


@dataclass(frozen=True)
class Weights:
    calorie: float
    protein: float
    trust: float
    relevance: float


def passes_hard_filters(f: Facts, s: Stated) -> bool:
    """Stated diet, restrictions and allergies. Never overridden by learned behaviour (fixed rule 10)."""
    if s.diet_type and (f.diet_class is None or f.diet_class not in DIET_ALLOWS[s.diet_type]):
        return False
    if not s.restrictions <= f.diet_tags:  # a restriction passes only if the restaurant declared it
        return False
    if s.allergies & f.declared_allergens:
        return False
    return True


def allergen_unknown_for(f: Facts, s: Stated) -> bool:
    """For a user with allergies, a dish whose allergen status is unknown can't be shown as safe."""
    return bool(s.allergies) and f.allergen_status != "declared"


def rankable(f: Facts, s: Stated) -> bool:
    return (f.label in TRUST_SCORE and not f.excluded_from_ranking and f.energy_high is not None
            and not allergen_unknown_for(f, s))


def fits_budget(f: Facts, meal_budget_kcal: float | None) -> bool:
    return meal_budget_kcal is not None and f.energy_high is not None and f.energy_high <= meal_budget_kcal


def score(f: Facts, meal_budget_kcal: float | None, meal_protein_g: float | None, w: Weights) -> float:
    if meal_budget_kcal and f.energy_high is not None:
        over = max(f.energy_high - meal_budget_kcal, 0)
        cal = max(0.0, 1 - over / meal_budget_kcal)
    else:
        cal = 0.5
    if meal_protein_g and f.protein_low is not None:
        pro = min(1.0, f.protein_low / meal_protein_g)
    else:
        pro = 0.5
    return w.calorie * cal + w.protein * pro + w.trust * TRUST_SCORE.get(f.label, 0) + w.relevance * f.relevance
