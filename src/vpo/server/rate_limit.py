"""Rate limiting middleware for API endpoints.

Provides per-IP sliding window rate limiting with separate counters
for GET (read) and mutating (POST/PUT/DELETE) requests.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from aiohttp import web

from vpo.config.models import RateLimitConfig


@dataclass
class SlidingWindowCounter:
    """Sliding window counter for rate limiting."""

    requests: list[float] = field(default_factory=list)

    def record_and_check(
        self, now: float, max_requests: int, window_seconds: int
    ) -> bool:
        """Record a request and check if within limit.

        Args:
            now: Current timestamp.
            max_requests: Maximum allowed requests in window.
            window_seconds: Window duration in seconds.

        Returns:
            True if the request is allowed, False if rate limited.
        """
        self.requests = [t for t in self.requests if now - t < window_seconds]
        if len(self.requests) >= max_requests:
            return False
        self.requests.append(now)
        return True

    def seconds_until_available(self, now: float, window_seconds: int) -> float:
        """Calculate seconds until the next request slot opens.

        Args:
            now: Current timestamp.
            window_seconds: Window duration in seconds.

        Returns:
            Seconds until a request slot becomes available.
        """
        if not self.requests:
            return 0.0
        return max(0.0, window_seconds - (now - min(self.requests)))


class RateLimiter:
    """Per-IP rate limiter with separate GET and mutate counters."""

    EXEMPT_PATHS: frozenset[str] = frozenset({"/health", "/api/about"})

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._get_counters: dict[str, SlidingWindowCounter] = defaultdict(
            SlidingWindowCounter
        )
        self._mutate_counters: dict[str, SlidingWindowCounter] = defaultdict(
            SlidingWindowCounter
        )

    def check(self, client_ip: str, method: str, path: str) -> tuple[bool, float]:
        """Check if a request is allowed.

        Args:
            client_ip: Client's IP address.
            method: HTTP method (GET, POST, etc.).
            path: Request path.

        Returns:
            Tuple of (allowed, retry_after_seconds).
        """
        if not self._config.enabled or path in self.EXEMPT_PATHS:
            return (True, 0.0)

        is_mutating = method in ("POST", "PUT", "DELETE")
        counters = self._mutate_counters if is_mutating else self._get_counters
        max_req = (
            self._config.mutate_max_requests
            if is_mutating
            else self._config.get_max_requests
        )
        counter = counters[client_ip]
        now = time.time()
        allowed = counter.record_and_check(now, max_req, self._config.window_seconds)
        retry_after = (
            0.0
            if allowed
            else counter.seconds_until_available(now, self._config.window_seconds)
        )
        return (allowed, retry_after)


def create_rate_limit_middleware(
    rate_limiter: RateLimiter,
) -> web.middleware:
    """Create aiohttp middleware for rate limiting API requests.

    Args:
        rate_limiter: RateLimiter instance to use for checks.

    Returns:
        aiohttp middleware function.
    """

    @web.middleware
    async def rate_limit_middleware(
        request: web.Request, handler: web.RequestHandler
    ) -> web.StreamResponse:
        if not request.path.startswith("/api/"):
            return await handler(request)

        client_ip = request.remote or "unknown"
        allowed, retry_after = rate_limiter.check(
            client_ip, request.method, request.path
        )
        if not allowed:
            retry_after_int = max(1, int(retry_after) + 1)
            return web.json_response(
                {"error": "Rate limit exceeded. Please wait before retrying."},
                status=429,
                headers={"Retry-After": str(retry_after_int)},
            )
        return await handler(request)

    return rate_limit_middleware
