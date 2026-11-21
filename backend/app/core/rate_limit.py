"""In-process sliding-window rate limiter.

Enough for one Render instance at launch (the spec rules out Redis until measured need).
If the service scales to several instances, move this to a Postgres-backed counter.
"""
import time
from collections import defaultdict, deque

from app.core.errors import RateLimited

_hits: dict[str, deque] = defaultdict(deque)


def check(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_seconds:
        q.popleft()
    if len(q) >= limit:
        raise RateLimited()
    q.append(now)


def reset() -> None:
    _hits.clear()
