"""Rate limiting middleware for API endpoints.

Provides per-IP sliding window rate limiting with separate counters
for GET (read) and mutating (POST/PUT/DELETE/PATCH) requests.

Note: Rate limiter state is in-memory and per-process. If the daemon
is deployed with multiple worker processes, each process has its own
independent rate limiter.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from aiohttp import web

from vpo.config.models import RateLimitConfig

logger = logging.getLogger(__name__)


@dataclass
class SlidingWindowCounter:
    """Sliding window counter for rate limiting.

    Uses a deque of monotonic timestamps for O(1) amortized expiry.
    Timestamps are appended in order, so the oldest is always at the left.
    """

    requests: deque[float] = field(default_factory=deque)

    def record_and_check(
        self, now: float, max_requests: int, window_seconds: int
    ) -> bool:
        """Record a request and check if within limit.

        Args:
            now: Current monotonic timestamp.
            max_requests: Maximum allowed requests in window.
            window_seconds: Window duration in seconds.

        Returns:
            True if the request is allowed, False if rate limited.
        """
        cutoff = now - window_seconds
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
        if len(self.requests) >= max_requests:
            return False
        self.requests.append(now)
        return True

    def seconds_until_available(self, now: float, window_seconds: int) -> float:
        """Calculate seconds until the next request slot opens.

        Must be called after record_and_check() which prunes expired entries.

        Args:
            now: Current monotonic timestamp.
            window_seconds: Window duration in seconds.

        Returns:
            Seconds until a request slot becomes available.
        """
        if not self.requests:
            return 0.0
        # Oldest entry is always at index 0 (monotonic append order)
        return max(0.0, window_seconds - (now - self.requests[0]))


class RateLimiter:
    """Per-IP rate limiter with separate GET and mutate counters."""

    EXEMPT_PATHS: frozenset[str] = frozenset({"/health", "/api/about"})
    _MUTATING_METHODS: frozenset[str] = frozenset({"POST", "PUT", "DELETE", "PATCH"})
    _CLEANUP_INTERVAL = 300  # seconds between stale counter cleanup

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._get_counters: dict[str, SlidingWindowCounter] = defaultdict(
            SlidingWindowCounter
        )
        self._mutate_counters: dict[str, SlidingWindowCounter] = defaultdict(
            SlidingWindowCounter
        )
        self._last_cleanup = time.monotonic()

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

        now = time.monotonic()
        self._maybe_cleanup(now)

        if method in self._MUTATING_METHODS:
            counters = self._mutate_counters
            max_req = self._config.mutate_max_requests
        else:
            counters = self._get_counters
            max_req = self._config.get_max_requests

        counter = counters[client_ip]
        window = self._config.window_seconds
        allowed = counter.record_and_check(now, max_req, window)
        if allowed:
            return (True, 0.0)
        return (False, counter.seconds_until_available(now, window))

    def _maybe_cleanup(self, now: float) -> None:
        """Remove counters with no recent requests (amortized)."""
        if now - self._last_cleanup < self._CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        window = self._config.window_seconds
        for store in (self._get_counters, self._mutate_counters):
            stale_keys = [
                ip
                for ip, counter in store.items()
                if not counter.requests or (now - counter.requests[-1]) >= window
            ]
            for key in stale_keys:
                del store[key]


@web.middleware
async def _rate_limit_middleware(
    request: web.Request, handler: web.RequestHandler
) -> web.StreamResponse:
    """Rate limiting middleware for API requests.

    Checks per-IP rate limits for /api/* paths. Non-API paths and
    requests that pass the limit are forwarded to the handler. If
    the rate limiter itself raises, the request is allowed through
    (fail-open).
    """
    if not request.path.startswith("/api/"):
        return await handler(request)

    rate_limiter: RateLimiter | None = request.app.get("rate_limiter")
    if rate_limiter is None:
        return await handler(request)

    try:
        client_ip = request.remote or "unknown"
        allowed, retry_after = rate_limiter.check(
            client_ip, request.method, request.path
        )
        if not allowed:
            retry_after_int = max(1, math.ceil(retry_after))
            logger.warning(
                "Rate limited %s %s from %s (retry_after=%ds)",
                request.method,
                request.path,
                client_ip,
                retry_after_int,
            )
            return web.json_response(
                {"error": "Rate limit exceeded. Please wait before retrying."},
                status=429,
                headers={"Retry-After": str(retry_after_int)},
            )
    except Exception:
        logger.exception("Rate limiter error, allowing request through")

    return await handler(request)
