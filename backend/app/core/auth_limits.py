"""Bounded per-instance limits for public authentication endpoints."""

import asyncio
import time
from collections import deque

from fastapi import Request

from app.core.exceptions import AppError
from app.core.waitlist_rate_limit import client_address


class AuthRateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = {}
        self._windows: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def check(
        self, key: str, *, max_requests: int, window_seconds: int, now: float | None = None
    ) -> None:
        current = time.monotonic() if now is None else now
        async with self._lock:
            if len(self._requests) >= 10_000:
                self._requests = {
                    name: times
                    for name, times in self._requests.items()
                    if times and times[-1] > current - self._windows[name]
                }
                self._windows = {name: self._windows[name] for name in self._requests}
            if key not in self._requests and len(self._requests) >= 10_000:
                raise AppError("RATE_LIMITED", "Please wait before trying again.", 429)
            times = self._requests.setdefault(key, deque())
            self._windows[key] = window_seconds
            while times and times[0] <= current - window_seconds:
                times.popleft()
            if len(times) >= max_requests:
                raise AppError("RATE_LIMITED", "Please wait before trying again.", 429)
            times.append(current)


limiter = AuthRateLimiter()


async def limit_auth_request(request: Request, flow: str) -> None:
    budgets = {
        "login": (10, 600),
        "signup": (5, 3600),
        "slug": (60, 600),
    }
    max_requests, window_seconds = budgets[flow]
    await limiter.check(
        f"{flow}:{client_address(request)}",
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
