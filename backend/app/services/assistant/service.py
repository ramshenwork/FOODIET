"""Assistant grounded in the catalogue and the user's diary, with a daily cap.

AI mode: a model calls the backend tools; its answer is accepted only if every number in it came from those
tools (fixed rule 2), and it may cite only dishes the tools returned. Basic mode (no AI provider configured, or
the monthly AI budget reached): simple question patterns answered directly from the same tools."""
import json
import re
import uuid
from datetime import datetime, time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.errors import AppError
from app.core.settings import get_settings
from app.models.activity import AssistantMessage
from app.services.ai import service as ai
from app.services.ai.providers import ProviderError
from app.services.assistant import repository, tools as tools_mod
from app.services.assistant.schemas import AnswerOut, CitedDish, ConversationOut, MessageOut, QueryIn
from app.services.diary.service import TZ, today
from app.services.events import service as events

SYSTEM = """You help people choose restaurant dishes in India that fit their goals.

Answer only from the tool results. Every number you write (energy, protein, prices, distances, counts) must be copied
from a tool result exactly as shown; if the tools don't give a number, don't state one. Never estimate nutrition.
When you mention a dish, cite it as [dish:<dish_id>] using the id from the tool result. If the tools return nothing
useful, say so plainly. Dishes are already filtered for the user's diet, restrictions and allergies; never suggest a
dish a tool marked unavailable. Ranges and trust labels matter: say "estimated" for estimated dishes. You are not a
doctor: for medical questions, suggest a professional. Keep answers short: two to five sentences."""

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
CITE = re.compile(r"\[dish:([0-9a-fA-F-]{36})\]")


def _day_start() -> datetime:
    return datetime.combine(today(), time.min, TZ)


async def _remaining(session: AsyncSession, user_id: uuid.UUID) -> tuple[int, int]:
    limit = get_settings().ASSISTANT_DAILY_QUESTIONS or 0
    used = await repository.questions_since(session, user_id, _day_start())
    return max(limit - used, 0), limit


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").rstrip("0").rstrip(".") if "." in n else n.replace(",", "") for n in NUMBER.findall(text)}


def grounded(answer: str, evidence: str) -> bool:
    """True if every number in the answer appears in the evidence (tool results and the question).
    Small counting words like 2 or 3 are allowed."""
    allowed = _numbers(evidence) | {str(i) for i in range(11)}
    return _numbers(CITE.sub("", answer)) <= allowed   # citation ids are not numbers


def _cards_from(results: list[dict]) -> dict[str, CitedDish]:
    cards = {}
    def visit(o):
        if isinstance(o, dict):
            if "dish_id" in o and "name" in o and "unavailable" not in o:
                n = o.get("nutrients") or {}
                cards[o["dish_id"]] = CitedDish(id=o["dish_id"], name=o["name"], restaurant=o.get("restaurant"),
                                                energy=o.get("energy") or n.get("energy_kcal"),
                                                protein=o.get("protein") or n.get("protein_g"),
                                                trust=o.get("trust_label", "no_data"))
            for v in o.values():
                visit(v)
        elif isinstance(o, list):
            for v in o:
                visit(v)
    visit(results)
    return cards


def _render_citations(text: str, cards: dict[str, CitedDish]) -> tuple[str, list[CitedDish]]:
    cited, seen = [], set()
    def sub(m):
        c = cards.get(m.group(1).lower())
        if c is None:
            return ""  # never cite a dish the tools didn't return
        if c.id not in seen:
            seen.add(c.id)
            cited.append(c)
        return c.name
    return re.sub(r"\s{2,}", " ", CITE.sub(sub, text)).strip(), cited


# ------------------------------------------------------------------ basic mode

KCAL = re.compile(r"(?:under|below|less than|within|max(?:imum)?)\s*(\d{2,4})\s*(?:kcal|cal|calories)", re.I)
PRICE = re.compile(r"(?:under|below|less than|within)\s*(?:₹|rs\.?|inr)?\s*(\d{2,5})\s*(?:₹|rs|rupees|inr)?\b(?!\s*(?:kcal|cal))", re.I)
PROTEIN = re.compile(r"(\d{1,3})\s*g(?:rams?)?\s*(?:of\s*)?protein", re.I)
STOP = set("a an the me i my show find give what which where is are with for near nearby dish dishes food something "
           "under below less than high low protein kcal calories cal rupees rs inr g grams of to eat can in good best "
           "some any please options option and or that fits fit around".split())


async def _basic(tools: dict, q: str) -> tuple[str, list[dict]]:
    ql = q.lower()
    if re.search(r"\b(left|remaining|how much more|budget today|eaten today)\b", ql):
        r = await tools["get_remaining_targets"]({})
        if "error" in r:
            return "You haven't set targets yet. Finish your profile to see what's left today.", [r]
        return f"So far today: {r['today']['energy']}. {r['remaining']}. {r['note']}", [r]
    m = re.search(r"compare (.+?) (?:and|vs\.?|with) (.+)", ql)
    if m:
        found = []
        for name in m.groups():
            s = await tools["search_dishes"]({"query": name.strip(" ?.")})
            if s.get("dishes"):
                found.append(s["dishes"][0]["dish_id"])
        if len(found) < 2:
            return "I couldn't find both dishes near you to compare.", []
        r = await tools["compare_dishes"]({"dish_ids": found})
        parts = [f"[dish:{d['dish_id']}] at {d['restaurant']}: {d['nutrients']['energy_kcal']}, protein {d['nutrients']['protein_g']} ({d['trust_label']})"
                 for d in r["dishes"] if "nutrients" in d]
        return "; ".join(parts) + ".", [r]
    args = {}
    if (k := KCAL.search(q)):
        args["max_kcal"] = float(k.group(1))
    by_protein = "protein" in ql
    if (p := PROTEIN.search(q)):
        args["min_protein"] = float(p.group(1))
    if (pr := PRICE.search(q)) and not (k and pr.group(1) == k.group(1)):
        args["max_price_inr"] = float(pr.group(1))
    words = [w for w in re.findall(r"[a-z]+", ql) if w not in STOP and len(w) > 2]
    if words:
        args["query"] = " ".join(words[:3])
    r = await tools["search_dishes"](args)
    if "error" in r:
        return r["error"], [r]
    dishes = r.get("dishes", [])
    if not dishes and "query" in args:   # retry without the words, keeping the filters
        args.pop("query")
        r = await tools["search_dishes"](args)
        dishes = r.get("dishes", [])
    if not dishes:
        limits = [f"under {args['max_kcal']:.0f} kcal" if "max_kcal" in args else "",
                  f"at least {args['min_protein']:.0f} g protein" if "min_protein" in args else "",
                  f"under ₹{args['max_price_inr']:.0f}" if "max_price_inr" in args else ""]
        said = ", ".join(x for x in limits if x)
        return (f"Nothing near you fits {said} and your diet settings. Try a wider limit." if said
                else "I couldn't find dishes near you that match."), [r]
    if by_protein:   # "high protein" with no number: highest protein first (worst-case estimate)
        dishes = sorted(dishes, key=lambda d: -(d.get("protein_low_g") or 0))
    top = dishes[:3]
    names = [f"[dish:{d['dish_id']}] at {d['restaurant']}" for d in top]   # the cards carry the numbers
    lead = "Highest protein first" if by_protein else "Here's what fits near you"
    return f"{lead}: " + "; ".join(names) + ".", [r]


# ------------------------------------------------------------------ entry points

async def conversation(session: AsyncSession, user_id: uuid.UUID) -> ConversationOut:
    rows = await repository.since(session, user_id, _day_start())
    remaining, limit = await _remaining(session, user_id)
    ok, _ = await ai.available(session)
    return ConversationOut(messages=[MessageOut(role=r.role, content=r.content, cited=[CitedDish(**c) for c in (r.cited or [])],
                                                mode=r.mode, at=r.created_at) for r in rows],
                           remaining_today=remaining, limit=limit, mode="ai" if ok else "basic")


async def ask(session: AsyncSession, user_id: uuid.UUID, body: QueryIn) -> AnswerOut:
    rate_limit.check(f"assistant:{user_id}", limit=6, window_seconds=60)
    remaining, limit = await _remaining(session, user_id)
    if remaining <= 0:
        raise AppError(429, "assistant_limit", f"You've used today's {limit} questions. They reset at midnight.",
                       {"remaining_today": 0, "limit": limit})
    q = body.question.strip()
    await repository.add(session, AssistantMessage(user_id=user_id, role="user", content=q, mode=None))
    specs = tools_mod.build(session, user_id, body.lat, body.lng)
    handlers = {t.name: t.handler for t in specs}
    ok, why = await ai.available(session)
    mode, notice, text, results = "basic", None, "", []
    if ok:
        history = [{"role": r.role, "content": r.content} for r in (await repository.since(session, user_id, _day_start()))[-7:-1]]
        try:
            out = await ai.chat(session, user_id, SYSTEM, history + [{"role": "user", "content": q}], specs)
            evidence = json.dumps(out.tool_results, default=str) + " " + q
            if out.refused or not out.text:
                notice = "I couldn't answer that one, so here's a simple search instead."
            elif not grounded(out.text, evidence):
                notice = "I checked the answer and couldn't confirm every number, so here's a simple search instead."
            else:
                mode, text, results = "ai", out.text, out.tool_results
        except ProviderError:
            notice = "The assistant is busy, so here's a simple search instead."
    elif why != "not_configured":   # not configured: the screen already says basic mode
        notice = "The assistant is in basic mode for the rest of the month."
    if mode == "basic":
        text, results = await _basic(handlers, q)
    answer, cited = _render_citations(text, _cards_from(results))
    await repository.add(session, AssistantMessage(user_id=user_id, role="assistant", content=answer,
                                                   cited=[c.model_dump(mode="json") for c in cited], mode=mode))
    await events.track(session, "assistant_query", user_id, mode=mode)
    remaining, limit = await _remaining(session, user_id)
    return AnswerOut(answer=answer, cited=cited, mode=mode, notice=notice, remaining_today=remaining, limit=limit)


async def export(session: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    return [{"role": r.role, "content": r.content, "at": r.created_at.isoformat()} for r in await repository.all_for(session, user_id)]


async def delete_all(session: AsyncSession, user_id: uuid.UUID) -> None:
    await repository.delete_all(session, user_id)
