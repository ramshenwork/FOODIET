"""Request-level protections: a per-IP request ceiling, request size limits, and security headers."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core import rate_limit
from app.core.errors import RateLimited, request_id_var
from app.core.net import client_ip
from app.core.settings import get_settings

UPLOAD_PATH_SUFFIX = "/menu-imports"
UPLOAD_MAX = 11 * 1024 * 1024

APP_CSP = ("default-src 'self'; script-src 'self' https://checkout.razorpay.com; "
           "frame-src https://api.razorpay.com https://checkout.razorpay.com; connect-src 'self' https://api.razorpay.com https://lumberjack.razorpay.com; "
           "img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; font-src 'self'; object-src 'none'; "
           "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
QR_CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'; "
          "frame-ancestors 'none'")


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "request_id": request_id_var.get()}}, status_code=status)


def install(app: FastAPI) -> None:
    s = get_settings()

    @app.middleware("http")
    async def protections(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/v1/billing/webhooks/"):
            try:
                rate_limit.check(f"ip:{client_ip(request)}", limit=s.API_RATE_PER_MINUTE_PER_IP, window_seconds=60)
            except RateLimited as e:
                return _error(429, e.code, e.message)
            length = request.headers.get("content-length")
            limit = UPLOAD_MAX if path.endswith(UPLOAD_PATH_SUFFIX) else s.MAX_JSON_BYTES
            if length and length.isdigit() and int(length) > limit:
                return _error(413, "request_too_large", "That request is too large.")
        response = await call_next(request)
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=(), payment=(self)")
        h.setdefault("Content-Security-Policy", QR_CSP if path.startswith("/q/") else APP_CSP)
        if path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")   # personal and paid data is never cached by browsers or proxies
        if s.is_production:
            h.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response
