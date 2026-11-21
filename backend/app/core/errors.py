"""One error shape for every failure: {"error": {"code", "message", "request_id"}}."""
import logging
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}


class NotFound(AppError):
    def __init__(self, message: str = "Not found"):
        super().__init__(404, "not_found", message)


class Unauthorized(AppError):
    def __init__(self, message: str = "Sign in required"):
        super().__init__(401, "unauthorized", message)


class Forbidden(AppError):
    def __init__(self, message: str = "Not allowed"):
        super().__init__(403, "forbidden", message)


class PaymentRequired(AppError):
    def __init__(self, paywall: dict):
        super().__init__(402, "subscription_required", "A subscription is needed for this.", {"paywall": paywall})


class RateLimited(AppError):
    def __init__(self, message: str = "Too many requests. Try again shortly."):
        super().__init__(429, "rate_limited", message)


def _body(code: str, message: str, extra: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id_var.get()}, **(extra or {})}


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = uuid.uuid4().hex[:16]
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, exc.extra), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body("invalid_request", "Some fields are invalid.", {"fields": fields}), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse(_body("internal_error", "Something went wrong on our side."), status_code=500)
