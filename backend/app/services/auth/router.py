from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import access
from app.core.access import ACCESS_COOKIE, CSRF_HEADER, Principal
from app.core.database import get_session
from app.core.net import client_ip
from app.core.errors import Forbidden
from app.core.security import constant_time_equal
from app.core.settings import get_settings
from app.services.auth import service
from app.services.auth.schemas import Ok, OtpRequest, OtpRequested, OtpVerify, SessionOut
from app.services.users import service as users

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE, CSRF_COOKIE, REFRESH_PATH = "refresh_token", "csrf_token", "/api/v1/auth"


def _ip(request: Request) -> str:
    return client_ip(request)


def _set_cookies(response: Response, issued: service.Issued) -> None:
    s = get_settings()
    secure = s.APP_BASE_URL.startswith("https://")
    response.set_cookie(ACCESS_COOKIE, issued.access_token, httponly=True, secure=secure, samesite="lax",
                        max_age=s.ACCESS_TOKEN_TTL_MINUTES * 60, path="/")
    response.set_cookie(REFRESH_COOKIE, issued.refresh_token, httponly=True, secure=secure, samesite="strict",
                        max_age=s.REFRESH_TOKEN_TTL_DAYS * 86400, path=REFRESH_PATH)
    # Readable by the web app so it can echo it in the X-CSRF-Token header.
    response.set_cookie(CSRF_COOKIE, issued.csrf_token, httponly=False, secure=secure, samesite="lax",
                        max_age=s.REFRESH_TOKEN_TTL_DAYS * 86400, path="/")


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")


@router.post("/otp/request", response_model=OtpRequested, status_code=202, dependencies=[access.public()])
async def otp_request(body: OtpRequest, request: Request, session: AsyncSession = Depends(get_session)):
    await service.request_otp(session, body.email, _ip(request))
    s = get_settings()
    # Same answer whether or not the account exists.
    return OtpRequested(message="If that address can receive mail, a six-digit code is on its way.",
                        ttl_minutes=s.OTP_TTL_MINUTES)


@router.post("/otp/verify", response_model=SessionOut, dependencies=[access.public()])
async def otp_verify(body: OtpVerify, request: Request, response: Response,
                     session: AsyncSession = Depends(get_session)):
    issued = await service.verify_otp(session, body.email, body.code, body.role, body.device_id,
                                      request.headers.get("user-agent"), _ip(request))
    _set_cookies(response, issued)
    return SessionOut(user=await users.me(session, issued.user_id), csrf_token=issued.csrf_token)


@router.post("/refresh", response_model=SessionOut, dependencies=[access.refresh_cookie()])
async def refresh(request: Request, response: Response, session: AsyncSession = Depends(get_session)):
    # Double-submit CSRF check: header must match the csrf cookie.
    if not constant_time_equal(request.headers.get(CSRF_HEADER, ""), request.cookies.get(CSRF_COOKIE, "") or "-"):
        raise Forbidden("Missing or invalid CSRF token")
    issued = await service.refresh(session, request.cookies.get(REFRESH_COOKIE))
    _set_cookies(response, issued)
    return SessionOut(user=await users.me(session, issued.user_id), csrf_token=issued.csrf_token)


@router.post("/logout", response_model=Ok)
async def logout(response: Response, p: Principal = access.signed_in(),
                 session: AsyncSession = Depends(get_session)):
    await service.logout(session, p.session_id)
    _clear_cookies(response)
    return Ok()
