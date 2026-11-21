"""The only backend functions the assistant can call (spec section 8). Each wraps an existing service, so the
user's stated diet, restrictions and allergies are already applied; a dish declaring the user's allergen is
never described."""
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.services.ai.schemas import ToolSpec

NUM = {"type": ["number", "null"]}


def _dish(d) -> dict:
    return {"dish_id": str(d.id), "name": d.name, "restaurant": d.restaurant_name, "distance": d.distance_display,
            "energy": d.energy["display"] if d.energy else "not available",
            "protein": d.protein["display"] if d.protein else "not available",
            "protein_low_g": round(d.protein["low"]) if d.protein else None,   # for ordering by protein
            "trust_label": d.trust["label"], "price_inr": d.price_inr, "fits_meal_budget": d.fits,
            "allergen_note": d.allergen_warning}


def build(session: AsyncSession, user_id: uuid.UUID, lat: float | None, lng: float | None) -> list[ToolSpec]:
    from app.services.diary import service as diary
    from app.services.profile import service as profile
    from app.services.search import service as search

    def need_location():
        return {"error": "The user hasn't shared their location, so nearby search isn't possible."}

    async def search_dishes(a: dict) -> dict:
        if lat is None or lng is None:
            return need_location()
        r = await search.search(session, user_id, lat, lng, a.get("query"), a.get("max_kcal"), a.get("min_protein"),
                                a.get("max_price_inr"), a.get("max_km"), set(), 8, None)
        return {"dishes": [_dish(d) for d in r.dishes]}

    async def search_restaurants(a: dict) -> dict:
        if lat is None or lng is None:
            return need_location()
        r = await search.nearby(session, user_id, lat, lng)
        return {"meal_budget": r.meal_budget_display, "restaurants": [
            {"restaurant_id": str(c.id), "name": c.name, "distance": c.distance_display,
             "typical_meal": c.typical_meal.display if c.typical_meal else None, "fit": c.fit_display} for c in r.restaurants[:8]]}

    async def get_dish_nutrition(a: dict) -> dict:
        try:
            p = await search.dish_page(session, user_id, uuid.UUID(str(a["dish_id"])))
        except (AppError, ValueError, KeyError):
            return {"error": "No such dish."}
        if p.allergy_conflict:
            return {"dish_id": str(p.id), "unavailable": "This dish declares an allergen the user listed, so it can't be suggested."}
        n = p.nutrition
        return {"dish_id": str(p.id), "name": p.name, "restaurant": p.restaurant_name, "trust_label": n.trust["label"],
                "trust_meaning": n.trust["meaning"], "serving": n.serving_label,
                "nutrients": {k: (v["display"] if v else "not available") for k, v in n.nutrients.items()},
                "allergens": p.allergens["display"], "protein_per_100_inr": n.protein_per_100_inr,
                "fit": n.fit["display"] if n.fit else None, "options": [m.label for g in p.modifier_groups for m in g.modifiers]}

    async def compare_dishes(a: dict) -> dict:
        ids = list(a.get("dish_ids") or [])[:4]
        return {"dishes": [await get_dish_nutrition({"dish_id": i}) for i in ids]}

    async def get_remaining_targets(a: dict) -> dict:
        d = await diary.day(session, user_id, diary.today(), False)
        if not d.rings:
            return {"error": "No targets set."}
        return {"today": {k: r.display for k, r in d.rings.items()}, "remaining": d.remaining_display,
                "note": "Targets are estimates, not medical advice."}

    async def get_diary(a: dict) -> dict:
        try:
            when = date.fromisoformat(a["date"]) if a.get("date") else diary.today()
        except ValueError:
            return {"error": "Use a date like 2026-11-20."}
        d = await diary.day(session, user_id, when, False)
        return {"date": str(when), "meals": [{"meal": e.meal_type, "restaurant": e.restaurant,
                                              "items": [f"{i.name} ({i.share_display}): {i.energy['display'] if i.energy else 'not available'}" for i in e.items]}
                                             for e in d.entries],
                "totals": {k: (v["display"] if v else "not available") for k, v in d.totals.items()}}

    async def get_profile(a: dict) -> dict:
        p = await profile.get(session, user_id)
        return {"goal": p.goal, "diet": p.diet_type, "restrictions": p.restrictions, "allergies": p.allergies,
                "targets": p.targets.model_dump() if p.targets else None}

    obj = lambda props, req=(): {"type": "object", "properties": props, "required": list(req), "additionalProperties": False}  # noqa: E731
    return [
        ToolSpec("search_dishes", "Find dishes near the user. Diet, restrictions and allergies are applied automatically. "
                 "Returns at most 8 dishes with energy and protein as display text.",
                 obj({"query": {"type": ["string", "null"]}, "max_kcal": NUM, "min_protein": NUM, "max_price_inr": NUM, "max_km": NUM}),
                 search_dishes),
        ToolSpec("search_restaurants", "Restaurants near the user, with how many dishes fit them.", obj({"max_km": NUM}), search_restaurants),
        ToolSpec("get_dish_nutrition", "Full nutrition, trust label, allergens and options for one dish.",
                 obj({"dish_id": {"type": "string"}}, ["dish_id"]), get_dish_nutrition),
        ToolSpec("compare_dishes", "Nutrition for up to 4 dishes side by side.",
                 obj({"dish_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 4}}, ["dish_ids"]), compare_dishes),
        ToolSpec("get_remaining_targets", "What the user has eaten today against their targets.", obj({}), get_remaining_targets),
        ToolSpec("get_diary", "The user's logged meals for a day (default today).", obj({"date": {"type": ["string", "null"]}}), get_diary),
        ToolSpec("get_profile", "The user's goal, diet, restrictions, allergies and targets.", obj({}), get_profile),
    ]
