"""Tests for rate limiting middleware and components."""

from __future__ import annotations

import time
from collections import deque
from unittest.mock import AsyncMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from vpo.config.models import RateLimitConfig
from vpo.server.rate_limit import (
    RateLimiter,
    SlidingWindowCounter,
    create_rate_limit_middleware,
)


class TestSlidingWindowCounter:
    """Tests for SlidingWindowCounter."""

    def test_first_request_allowed(self) -> None:
        """First request should always be allowed."""
        counter = SlidingWindowCounter()
        now = time.monotonic()
        assert counter.record_and_check(now, max_requests=10, window_seconds=60) is True

    def test_within_limit_allowed(self) -> None:
        """Requests within the limit should be allowed."""
        counter = SlidingWindowCounter()
        now = time.monotonic()
        for i in range(10):
            assert (
                counter.record_and_check(
                    now + i * 0.01, max_requests=10, window_seconds=60
                )
                is True
            )

    def test_over_limit_blocked(self) -> None:
        """Requests over the limit should be blocked."""
        counter = SlidingWindowCounter()
        now = time.monotonic()
        for i in range(10):
            counter.record_and_check(now + i * 0.01, max_requests=10, window_seconds=60)
        assert (
            counter.record_and_check(now + 0.5, max_requests=10, window_seconds=60)
            is False
        )

    def test_window_expiration_resets(self) -> None:
        """Expired requests should be pruned, allowing new ones."""
        counter = SlidingWindowCounter()
        now = time.monotonic()
        # Fill up the window
        for i in range(10):
            counter.record_and_check(now, max_requests=10, window_seconds=60)
        # Should be blocked
        assert (
            counter.record_and_check(now + 0.1, max_requests=10, window_seconds=60)
            is False
        )
        # After window expires, should be allowed
        assert (
            counter.record_and_check(now + 61, max_requests=10, window_seconds=60)
            is True
        )

    def test_seconds_until_available_empty(self) -> None:
        """Empty counter should return 0."""
        counter = SlidingWindowCounter()
        assert (
            counter.seconds_until_available(time.monotonic(), window_seconds=60) == 0.0
        )

    def test_seconds_until_available_with_requests(self) -> None:
        """Should return time until oldest request expires."""
        counter = SlidingWindowCounter()
        now = time.monotonic()
        counter.requests = deque([now - 50])  # 50 seconds ago
        result = counter.seconds_until_available(now, window_seconds=60)
        assert 9.0 <= result <= 11.0  # ~10 seconds remaining

    def test_uses_deque(self) -> None:
        """Counter should use deque for O(1) popleft."""
        counter = SlidingWindowCounter()
        assert isinstance(counter.requests, deque)

    def test_popleft_pruning(self) -> None:
        """Only expired entries at the front should be removed."""
        counter = SlidingWindowCounter()
        now = time.monotonic()
        # Add old and new timestamps
        counter.requests = deque([now - 100, now - 90, now - 5, now - 1])
        counter.record_and_check(now, max_requests=100, window_seconds=60)
        # Old entries removed, new entries + the new one remain
        assert len(counter.requests) == 3


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def _make_config(self, **kwargs) -> RateLimitConfig:
        return RateLimitConfig(**kwargs)

    def test_get_uses_get_limit(self) -> None:
        """GET requests should use get_max_requests limit."""
        config = self._make_config(get_max_requests=2, mutate_max_requests=100)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False

    def test_post_uses_mutate_limit(self) -> None:
        """POST requests should use mutate_max_requests limit."""
        config = self._make_config(get_max_requests=100, mutate_max_requests=2)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "POST", "/api/plans/bulk-approve")[0] is True
        assert limiter.check("1.2.3.4", "POST", "/api/plans/bulk-approve")[0] is True
        assert limiter.check("1.2.3.4", "POST", "/api/plans/bulk-approve")[0] is False

    def test_put_uses_mutate_limit(self) -> None:
        """PUT requests should use mutate_max_requests limit."""
        config = self._make_config(mutate_max_requests=1)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "PUT", "/api/policies/test")[0] is True
        assert limiter.check("1.2.3.4", "PUT", "/api/policies/test")[0] is False

    def test_delete_uses_mutate_limit(self) -> None:
        """DELETE requests should use mutate_max_requests limit."""
        config = self._make_config(mutate_max_requests=1)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "DELETE", "/api/something")[0] is True
        assert limiter.check("1.2.3.4", "DELETE", "/api/something")[0] is False

    def test_patch_uses_mutate_limit(self) -> None:
        """PATCH requests should use mutate_max_requests limit."""
        config = self._make_config(mutate_max_requests=1)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "PATCH", "/api/something")[0] is True
        assert limiter.check("1.2.3.4", "PATCH", "/api/something")[0] is False

    def test_separate_clients_independent(self) -> None:
        """Different client IPs should have independent counters."""
        config = self._make_config(get_max_requests=1)
        limiter = RateLimiter(config)

        assert limiter.check("1.1.1.1", "GET", "/api/files")[0] is True
        assert limiter.check("1.1.1.1", "GET", "/api/files")[0] is False
        # Different client should still be allowed
        assert limiter.check("2.2.2.2", "GET", "/api/files")[0] is True

    def test_get_and_mutate_counters_independent(self) -> None:
        """GET and mutate counters should not interfere."""
        config = self._make_config(get_max_requests=1, mutate_max_requests=1)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False
        # POST should still work (separate counter)
        assert limiter.check("1.2.3.4", "POST", "/api/plans/bulk-approve")[0] is True

    def test_exempt_paths_bypass(self) -> None:
        """Exempt paths should always be allowed."""
        config = self._make_config(get_max_requests=1)
        limiter = RateLimiter(config)

        # Exhaust the limit
        limiter.check("1.2.3.4", "GET", "/api/files")
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False

        # Exempt paths still work
        assert limiter.check("1.2.3.4", "GET", "/health")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/about")[0] is True

    def test_disabled_config_passes_all(self) -> None:
        """When disabled, all requests should be allowed."""
        config = self._make_config(enabled=False, get_max_requests=1)
        limiter = RateLimiter(config)

        for _ in range(100):
            assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True

    def test_retry_after_returned_when_blocked(self) -> None:
        """When blocked, retry_after should be positive."""
        config = self._make_config(get_max_requests=1, window_seconds=60)
        limiter = RateLimiter(config)

        limiter.check("1.2.3.4", "GET", "/api/files")
        allowed, retry_after = limiter.check("1.2.3.4", "GET", "/api/files")
        assert allowed is False
        assert retry_after > 0

    def test_cleanup_removes_stale_counters(self) -> None:
        """Stale counters should be removed after cleanup interval."""
        config = self._make_config(get_max_requests=10, window_seconds=60)
        limiter = RateLimiter(config)

        # Create counters for several IPs
        for i in range(5):
            limiter.check(f"1.2.3.{i}", "GET", "/api/files")
        assert len(limiter._get_counters) == 5

        # Force cleanup by advancing past the interval and window
        limiter._last_cleanup = time.monotonic() - 400
        # Make all existing timestamps old enough to be stale
        for counter in limiter._get_counters.values():
            counter.requests = deque([time.monotonic() - 120])

        # Next check triggers cleanup
        limiter.check("10.0.0.1", "GET", "/api/files")

        # Stale IPs removed, only the new one remains
        assert "1.2.3.0" not in limiter._get_counters
        assert "10.0.0.1" in limiter._get_counters

    def test_cleanup_preserves_active_counters(self) -> None:
        """Active counters should not be removed during cleanup."""
        config = self._make_config(get_max_requests=10, window_seconds=60)
        limiter = RateLimiter(config)

        # Make a recent request
        limiter.check("1.2.3.4", "GET", "/api/files")

        # Force cleanup
        limiter._last_cleanup = time.monotonic() - 400
        limiter.check("10.0.0.1", "GET", "/api/files")

        # Active counter preserved
        assert "1.2.3.4" in limiter._get_counters


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    @pytest.mark.asyncio
    async def test_allows_non_api_paths(self) -> None:
        """Non-API paths should bypass rate limiting."""
        config = RateLimitConfig(get_max_requests=1)
        limiter = RateLimiter(config)
        middleware = create_rate_limit_middleware(limiter)

        handler = AsyncMock(return_value=web.Response(text="ok"))
        request = make_mocked_request("GET", "/files")
        request._match_info = {}

        response = await middleware(request, handler)
        handler.assert_called_once()
        assert response.text == "ok"

    @pytest.mark.asyncio
    async def test_allows_within_limit(self) -> None:
        """API requests within limit should pass through."""
        config = RateLimitConfig(get_max_requests=10)
        limiter = RateLimiter(config)
        middleware = create_rate_limit_middleware(limiter)

        handler = AsyncMock(return_value=web.Response(text="ok"))
        request = make_mocked_request("GET", "/api/files")
        request._match_info = {}

        response = await middleware(request, handler)
        handler.assert_called_once()
        assert response.text == "ok"

    @pytest.mark.asyncio
    async def test_returns_429_when_blocked(self) -> None:
        """Should return 429 with Retry-After when rate limited."""
        config = RateLimitConfig(get_max_requests=1, window_seconds=60)
        limiter = RateLimiter(config)
        middleware = create_rate_limit_middleware(limiter)

        handler = AsyncMock(return_value=web.Response(text="ok"))

        # First request allowed
        request1 = make_mocked_request("GET", "/api/files")
        request1._match_info = {}
        await middleware(request1, handler)

        # Second request should be blocked
        request2 = make_mocked_request("GET", "/api/files")
        request2._match_info = {}
        response = await middleware(request2, handler)

        assert response.status == 429
        assert "Retry-After" in response.headers
        assert int(response.headers["Retry-After"]) >= 1

    @pytest.mark.asyncio
    async def test_429_response_body_format(self) -> None:
        """429 response should have JSON error body."""
        config = RateLimitConfig(get_max_requests=1, window_seconds=60)
        limiter = RateLimiter(config)
        middleware = create_rate_limit_middleware(limiter)

        handler = AsyncMock(return_value=web.Response(text="ok"))

        # Exhaust limit
        request1 = make_mocked_request("GET", "/api/files")
        request1._match_info = {}
        await middleware(request1, handler)

        # Get blocked response
        request2 = make_mocked_request("GET", "/api/files")
        request2._match_info = {}
        response = await middleware(request2, handler)

        assert response.content_type == "application/json"

    @pytest.mark.asyncio
    async def test_exempt_paths_pass_through(self) -> None:
        """Exempt API paths should bypass rate limiting."""
        config = RateLimitConfig(get_max_requests=1)
        limiter = RateLimiter(config)
        middleware = create_rate_limit_middleware(limiter)

        handler = AsyncMock(return_value=web.Response(text="ok"))

        # Exhaust limit on regular API path
        request1 = make_mocked_request("GET", "/api/files")
        request1._match_info = {}
        await middleware(request1, handler)

        # /api/about should still work (exempt)
        request2 = make_mocked_request("GET", "/api/about")
        request2._match_info = {}
        response = await middleware(request2, handler)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_disabled_passes_all(self) -> None:
        """When disabled, all API requests should pass through."""
        config = RateLimitConfig(enabled=False, get_max_requests=1)
        limiter = RateLimiter(config)
        middleware = create_rate_limit_middleware(limiter)

        handler = AsyncMock(return_value=web.Response(text="ok"))

        for _ in range(10):
            request = make_mocked_request("GET", "/api/files")
            request._match_info = {}
            response = await middleware(request, handler)
            assert response.status == 200

    @pytest.mark.asyncio
    async def test_fails_open_on_exception(self) -> None:
        """Middleware should allow request if rate limiter throws."""
        config = RateLimitConfig(get_max_requests=10)
        limiter = RateLimiter(config)

        # Break the limiter's check method
        def broken_check(*args, **kwargs):
            raise RuntimeError("simulated failure")

        limiter.check = broken_check  # type: ignore[assignment]
        middleware = create_rate_limit_middleware(limiter)

        handler = AsyncMock(return_value=web.Response(text="ok"))
        request = make_mocked_request("GET", "/api/files")
        request._match_info = {}

        response = await middleware(request, handler)
        handler.assert_called_once()
        assert response.status == 200
