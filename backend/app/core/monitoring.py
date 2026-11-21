"""Error monitoring (Sentry), on only when SENTRY_DSN is set. No personal data is sent: no request bodies,
cookies, headers, user emails or query strings."""
import logging

from app.core.settings import get_settings

log = logging.getLogger("app.monitoring")
SENSITIVE = ("cookie", "authorization", "x-csrf-token", "x-razorpay-signature")


def _scrub(event, hint):
    req = event.get("request") or {}
    req.pop("data", None)
    req.pop("cookies", None)
    req.pop("query_string", None)
    req["headers"] = {k: v for k, v in (req.get("headers") or {}).items() if k.lower() not in SENSITIVE}
    event["request"] = req
    event.pop("user", None)
    return event


def setup() -> None:
    s = get_settings()
    if not s.SENTRY_DSN:
        return
    import sentry_sdk
    sentry_sdk.init(dsn=s.SENTRY_DSN, environment=s.APP_ENV, send_default_pii=False, traces_sample_rate=0.05,
                    before_send=_scrub, max_request_body_size="never")
    log.info("error monitoring enabled")
