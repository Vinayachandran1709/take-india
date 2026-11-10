"""Small, process-local abuse limit for the public waitlist route."""

import asyncio
import ipaddress
import os
import time
from collections import deque

from fastapi import Request

from app.core.exceptions import AppError

WINDOW_SECONDS = 600
MAX_REQUESTS = 60
MAX_CLIENTS = 10_000


class WaitlistRateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, client: str, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        async with self._lock:
            if len(self._requests) >= MAX_CLIENTS:
                self._requests = {
                    key: times
                    for key, times in self._requests.items()
                    if times and times[-1] > current - WINDOW_SECONDS
                }
            if client not in self._requests and len(self._requests) >= MAX_CLIENTS:
                raise AppError("RATE_LIMITED", "Please wait before trying again.", 429)
            times = self._requests.setdefault(client, deque())
            while times and times[0] <= current - WINDOW_SECONDS:
                times.popleft()
            if len(times) >= MAX_REQUESTS:
                raise AppError("RATE_LIMITED", "Please wait before trying again.", 429)
            times.append(current)


limiter = WaitlistRateLimiter()


def client_address(request: Request) -> str:
    # Railway's public edge supplies X-Real-IP for the remote client.
    if os.environ.get("RAILWAY_ENVIRONMENT_ID"):
        forwarded = request.headers.get("x-real-ip", "")
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    # Render's public edge overwrites this header. Never trust it off Render.
    if os.environ.get("RENDER") == "true":
        forwarded = request.headers.get("cf-connecting-ip", "")
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return request.client.host if request.client else "unknown"


async def check_waitlist_rate_limit(request: Request) -> None:
    await limiter.check(client_address(request))
