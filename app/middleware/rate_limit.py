from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings


class InMemoryRateLimiter:
    """Single-process rate limiter.

    Production deployments with multiple workers should replace this with a
    shared Redis-backed limiter. The interface is intentionally small.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        window_start = now - window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            if now - self._last_cleanup > 300:
                self._cleanup(now, max(window_seconds, 60))
                self._last_cleanup = now
            return True, 0

    def _cleanup(self, now: float, window_seconds: int) -> None:
        cutoff = now - window_seconds
        stale = [key for key, bucket in self._events.items() if not bucket or bucket[-1] < cutoff]
        for key in stale:
            self._events.pop(key, None)


limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        if not settings.RATE_LIMIT_ENABLED or request.url.path in {"/health", "/ready"}:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        path = request.url.path
        is_login = path.endswith("/auth/login")
        limit = settings.LOGIN_RATE_LIMIT if is_login else settings.GLOBAL_RATE_LIMIT
        window = settings.LOGIN_RATE_WINDOW_SECONDS if is_login else settings.GLOBAL_RATE_WINDOW_SECONDS
        allowed, retry_after = limiter.check(f"{client}:{path}", limit, window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Too many requests. Please try again later.",
                    "error_code": "RATE_LIMITED",
                    "details": None,
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
