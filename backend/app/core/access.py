"""Access declarations. Every /api route must depend on exactly one of these, or startup fails.

The server decides access on every request; the frontend never does.
"""
import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import Forbidden, PaymentRequired, Unauthorized
from app.core.security import constant_time_equal, csrf_token_for, decode_access_token

ACCESS_COOKIE = "access_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

FULL_ACCESS = {"free", "trial", "subscriber", "grace"}  # "free": payments off (testing)


@dataclass
class Principal:
    user_id: uuid.UUID
    session_id: uuid.UUID
    role: str  # consumer | business | admin
    via_cookie: bool


def _read_principal(request: Request) -> Principal | None:
    token, via_cookie = request.cookies.get(ACCESS_COOKIE), True
    auth = request.headers.get("Authorization", "")
    if not token and auth.startswith("Bearer "):
        token, via_cookie = auth[7:], False  # future phone app
    payload = decode_access_token(token) if token else None
    if not payload:
        return None
    return Principal(uuid.UUID(payload["sub"]), uuid.UUID(payload["sid"]), payload["role"], via_cookie)


def _check_csrf(request: Request, p: Principal) -> None:
    if request.method in SAFE_METHODS or not p.via_cookie:
        return
    sent = request.headers.get(CSRF_HEADER, "")
    if not constant_time_equal(sent, csrf_token_for(p.session_id)):
        raise Forbidden("Missing or invalid CSRF token")


async def _signed_in(request: Request, session: AsyncSession) -> Principal:
    p = _read_principal(request)
    if p is None:
        raise Unauthorized()
    from app.services.auth.service import session_is_active  # service-to-service via service.py
    if not await session_is_active(session, p.session_id):
        raise Unauthorized("Session ended. Sign in again.")
    _check_csrf(request, p)
    return p


async def _require_level(session: AsyncSession, p: Principal, allowed: set[str]) -> None:
    from app.services.entitlement.service import access_level, paywall_for
    level = await access_level(session, p.user_id)
    if level not in allowed:
        raise PaymentRequired(await paywall_for(session, p.user_id, level))


def _mark(fn, name: str):
    fn.__access__ = name
    return fn


# ------------------------------------------------------------------ declarations

def public():
    async def dep() -> None:
        return None
    return Depends(_mark(dep, "public"))


def webhook():
    """Authenticated by the provider's signature inside the endpoint, not by a session."""
    async def dep() -> None:
        return None
    return Depends(_mark(dep, "webhook"))


def signed_in():
    async def dep(request: Request, session: AsyncSession = Depends(get_session)) -> Principal:
        return await _signed_in(request, session)
    return Depends(_mark(dep, "signed_in"))


def subscriber():
    async def dep(request: Request, session: AsyncSession = Depends(get_session)) -> Principal:
        p = await _signed_in(request, session)
        await _require_level(session, p, FULL_ACCESS)
        return p
    return Depends(_mark(dep, "subscriber"))


def subscriber_or_lapsed_read():
    """Lapsed users keep read access to their own history (diary, export)."""
    async def dep(request: Request, session: AsyncSession = Depends(get_session)) -> Principal:
        p = await _signed_in(request, session)
        allowed = FULL_ACCESS | ({"lapsed"} if request.method in SAFE_METHODS else set())
        await _require_level(session, p, allowed)
        return p
    return Depends(_mark(dep, "subscriber_or_lapsed_read"))


def business_member():
    """A business (or admin) account; ownership of each business row is checked in the repository layer."""
    async def dep(request: Request, session: AsyncSession = Depends(get_session)) -> Principal:
        p = await _signed_in(request, session)
        if p.role not in ("business", "admin"):
            raise Forbidden("This needs a restaurant account.")
        return p
    return Depends(_mark(dep, "business_member"))


def admin():
    async def dep(request: Request, session: AsyncSession = Depends(get_session)) -> Principal:
        p = await _signed_in(request, session)
        if p.role != "admin":
            raise Forbidden()
        from app.services.events.service import audit  # every admin request is logged
        await audit(session, p.user_id, "admin_request", "route", f"{request.method} {request.url.path}"[:64])
        return p
    return Depends(_mark(dep, "admin"))


# ------------------------------------------------------------------ startup check

def _declared(dependant) -> list[str]:
    found = []
    for d in dependant.dependencies:
        name = getattr(d.call, "__access__", None)
        if name:
            found.append(name)
        found.extend(_declared(d))
    return found


def _api_routes(router):
    for route in router.routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):  # nested include in newer FastAPI versions
            yield from _api_routes(route.original_router)


def assert_all_routes_declared(routers) -> int:
    """Fail startup if any API endpoint lacks exactly one access declaration. Returns routes checked."""
    missing, multiple, checked = [], [], 0
    for router in routers:
        for route in _api_routes(router):
            checked += 1
            names = _declared(route.dependant)
            label = f"{','.join(sorted(route.methods))} {router.prefix}{route.path}"
            if not names:
                missing.append(label)
            elif len(set(names)) > 1:
                multiple.append(f"{label}: {names}")
    if missing or multiple:
        raise RuntimeError(f"Access declarations invalid. Missing: {missing}. Conflicting: {multiple}")
    return checked


def refresh_cookie():
    """Authenticated by the rotating refresh-token cookie (the access token may have expired)."""
    async def dep() -> None:
        return None
    return Depends(_mark(dep, "refresh_cookie"))
