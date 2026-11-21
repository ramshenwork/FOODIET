"""Client address. Never read X-Forwarded-For here: a client can set it to anything. In production uvicorn runs
with --proxy-headers behind Render's proxy, which puts the real client address in request.client."""
from fastapi import Request


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
