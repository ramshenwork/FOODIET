"""Minimal Razorpay Subscriptions client (REST, basic auth). Card and UPI details never reach our servers:
the diner pays in Razorpay Checkout, and Razorpay tells us by webhook.

Endpoints used (verify against Razorpay's current docs before going live):
  POST /v1/subscriptions                    create
  POST /v1/subscriptions/{id}/cancel        cancel (at cycle end)
  GET  /v1/subscriptions/{id}               fetch, for reconciliation
"""
import httpx

from app.core.settings import get_settings

BASE = "https://api.razorpay.com/v1"
TOTAL_COUNT = {"monthly": 120, "yearly": 10}   # billing cycles before Razorpay ends the mandate


class RazorpayError(Exception):
    pass


_transport = None   # tests inject an httpx.MockTransport


def set_transport(t) -> None:
    global _transport
    _transport = t


def _client() -> httpx.AsyncClient:
    s = get_settings()
    if not (s.RAZORPAY_KEY_ID and s.RAZORPAY_KEY_SECRET):
        raise RazorpayError("Razorpay keys are not configured.")
    return httpx.AsyncClient(base_url=BASE, auth=(s.RAZORPAY_KEY_ID, s.RAZORPAY_KEY_SECRET), timeout=20,
                             transport=_transport)


async def _call(method: str, path: str, json: dict | None = None) -> dict:
    async with _client() as c:
        try:
            r = await c.request(method, path, json=json)
        except httpx.HTTPError as e:
            raise RazorpayError("Could not reach Razorpay.") from e
    if r.status_code >= 300:
        raise RazorpayError(f"Razorpay returned {r.status_code}.")
    return r.json()


async def create_subscription(plan_id: str, cycle: str, notes: dict) -> dict:
    return await _call("POST", "/subscriptions", {"plan_id": plan_id, "total_count": TOTAL_COUNT[cycle], "quantity": 1,
                                                  "customer_notify": 1, "notes": notes})


async def cancel_subscription(sub_id: str) -> dict:
    return await _call("POST", f"/subscriptions/{sub_id}/cancel", {"cancel_at_cycle_end": 1})


async def fetch_subscription(sub_id: str) -> dict:
    return await _call("GET", f"/subscriptions/{sub_id}")
