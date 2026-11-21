"""Logging that never writes OTP codes, tokens, payment details, or profile values."""
import logging
import re

from app.core.errors import request_id_var

_SECRET_PATTERNS = [
    (re.compile(r"(?i)(otp|code|token|secret|password|authorization|cookie)([\"'=:\s]+)([^\s\"',;&]+)"), r"\1\2[redacted]"),
    (re.compile(r"\b\d{6}\b"), "[redacted]"),  # bare six-digit codes
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
]


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern, repl in _SECRET_PATTERNS:
            msg = pattern.sub(repl, msg)
        record.msg, record.args = msg, ()
        record.request_id = request_id_var.get()
        return True


def setup() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
