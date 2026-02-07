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
    rate_limit_middleware,
)


def _make_api_request(
    method: str, path: str, *, rate_limiter: RateLimiter
) -> web.Request:
    """Create a mocked request with a rate limiter attached to its app."""
    app = web.Application()
    app["rate_limiter"] = rate_limiter
    return make_mocked_request(method, path, app=app)


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

    def test_get_uses_get_limit(self) -> None:
        """GET requests should use get_max_requests limit."""
        config = RateLimitConfig(get_max_requests=2, mutate_max_requests=100)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False

    def test_post_uses_mutate_limit(self) -> None:
        """POST requests should use mutate_max_requests limit."""
        config = RateLimitConfig(get_max_requests=100, mutate_max_requests=2)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "POST", "/api/plans/bulk-approve")[0] is True
        assert limiter.check("1.2.3.4", "POST", "/api/plans/bulk-approve")[0] is True
        assert limiter.check("1.2.3.4", "POST", "/api/plans/bulk-approve")[0] is False

    def test_put_uses_mutate_limit(self) -> None:
        """PUT requests should use mutate_max_requests limit."""
        limiter = RateLimiter(RateLimitConfig(mutate_max_requests=1))

        assert limiter.check("1.2.3.4", "PUT", "/api/policies/test")[0] is True
        assert limiter.check("1.2.3.4", "PUT", "/api/policies/test")[0] is False

    def test_delete_uses_mutate_limit(self) -> None:
        """DELETE requests should use mutate_max_requests limit."""
        limiter = RateLimiter(RateLimitConfig(mutate_max_requests=1))

        assert limiter.check("1.2.3.4", "DELETE", "/api/something")[0] is True
        assert limiter.check("1.2.3.4", "DELETE", "/api/something")[0] is False

    def test_patch_uses_mutate_limit(self) -> None:
        """PATCH requests should use mutate_max_requests limit."""
        limiter = RateLimiter(RateLimitConfig(mutate_max_requests=1))

        assert limiter.check("1.2.3.4", "PATCH", "/api/something")[0] is True
        assert limiter.check("1.2.3.4", "PATCH", "/api/something")[0] is False

    def test_separate_clients_independent(self) -> None:
        """Different client IPs should have independent counters."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=1))

        assert limiter.check("1.1.1.1", "GET", "/api/files")[0] is True
        assert limiter.check("1.1.1.1", "GET", "/api/files")[0] is False
        # Different client should still be allowed
        assert limiter.check("2.2.2.2", "GET", "/api/files")[0] is True

    def test_get_and_mutate_counters_independent(self) -> None:
        """GET and mutate counters should not interfere."""
        config = RateLimitConfig(get_max_requests=1, mutate_max_requests=1)
        limiter = RateLimiter(config)

        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False
        # POST should still work (separate counter)
        assert limiter.check("1.2.3.4", "POST", "/api/plans/bulk-approve")[0] is True

    def test_exempt_paths_bypass(self) -> None:
        """Exempt paths should always be allowed."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=1))

        # Exhaust the limit
        limiter.check("1.2.3.4", "GET", "/api/files")
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False

        # Exempt paths still work
        assert limiter.check("1.2.3.4", "GET", "/health")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/about")[0] is True

    def test_disabled_config_passes_all(self) -> None:
        """When disabled, all requests should be allowed."""
        limiter = RateLimiter(RateLimitConfig(enabled=False, get_max_requests=1))

        for _ in range(100):
            assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True

    def test_retry_after_returned_when_blocked(self) -> None:
        """When blocked, retry_after should be positive."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=1, window_seconds=60))

        limiter.check("1.2.3.4", "GET", "/api/files")
        allowed, retry_after = limiter.check("1.2.3.4", "GET", "/api/files")
        assert allowed is False
        assert retry_after > 0

    def test_cleanup_removes_stale_counters(self) -> None:
        """Stale counters should be removed after cleanup interval."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=10, window_seconds=60))

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
        limiter = RateLimiter(RateLimitConfig(get_max_requests=10, window_seconds=60))

        # Make a recent request
        limiter.check("1.2.3.4", "GET", "/api/files")

        # Force cleanup
        limiter._last_cleanup = time.monotonic() - 400
        limiter.check("10.0.0.1", "GET", "/api/files")

        # Active counter preserved
        assert "1.2.3.4" in limiter._get_counters


class TestRateLimiterReconfigure:
    """Tests for RateLimiter.reconfigure()."""

    def test_reconfigured_limits_take_effect(self) -> None:
        """New limits should apply to subsequent check() calls."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=2))

        # Exhaust the original limit
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False

        # Reconfigure with a higher limit
        limiter.reconfigure(RateLimitConfig(get_max_requests=10))

        # Previously blocked IP should now be allowed (only 2 in window, limit is 10)
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True

    def test_reconfigure_preserves_existing_counters(self) -> None:
        """Per-IP counters should survive reconfiguration."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=5))

        # Record 3 requests
        for _ in range(3):
            limiter.check("1.2.3.4", "GET", "/api/files")

        # Reconfigure with same limit
        limiter.reconfigure(RateLimitConfig(get_max_requests=5))

        # Should only allow 2 more (3 already recorded)
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False

    def test_reconfigure_disable_bypasses_checks(self) -> None:
        """Disabling via reconfigure should allow all requests."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=1))

        # Exhaust the limit
        limiter.check("1.2.3.4", "GET", "/api/files")
        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False

        # Disable via reconfigure
        limiter.reconfigure(RateLimitConfig(enabled=False))

        # All requests should now pass
        for _ in range(10):
            assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is True

    def test_reconfigure_tighter_limit_blocks_immediately(self) -> None:
        """Lowering the limit should block IPs that already exceed it."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=10))

        # Record 5 requests
        for _ in range(5):
            limiter.check("1.2.3.4", "GET", "/api/files")

        # Reconfigure with a limit of 3 (already have 5 in window)
        limiter.reconfigure(RateLimitConfig(get_max_requests=3))

        assert limiter.check("1.2.3.4", "GET", "/api/files")[0] is False

    def test_reconfigure_applies_to_mutate_counters(self) -> None:
        """Reconfigured mutate limits should take effect."""
        limiter = RateLimiter(RateLimitConfig(mutate_max_requests=2))

        # Exhaust the original mutate limit
        assert limiter.check("1.2.3.4", "POST", "/api/jobs")[0] is True
        assert limiter.check("1.2.3.4", "POST", "/api/jobs")[0] is True
        assert limiter.check("1.2.3.4", "POST", "/api/jobs")[0] is False

        # Reconfigure with a higher mutate limit
        limiter.reconfigure(RateLimitConfig(mutate_max_requests=10))

        # Previously blocked IP should now be allowed
        assert limiter.check("1.2.3.4", "POST", "/api/jobs")[0] is True

    def test_reconfigure_window_change_prunes_old_timestamps(self) -> None:
        """Shrinking the window should cause old timestamps to be pruned."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=10, window_seconds=60))
        now = time.monotonic()

        # Manually inject timestamps 15 seconds ago (within 60s window)
        counter = limiter._get_counters["1.2.3.4"]
        for i in range(5):
            counter.requests.append(now - 15 + i * 0.01)

        # Reconfigure with a 10s window — those 15s-old timestamps are now stale
        limiter.reconfigure(RateLimitConfig(get_max_requests=10, window_seconds=10))

        # Next check should prune the old timestamps, so all 10 slots open
        allowed, _ = limiter.check("1.2.3.4", "GET", "/api/files")
        assert allowed is True
        # Only the fresh request should remain (old ones pruned)
        assert len(limiter._get_counters["1.2.3.4"].requests) == 1

    def test_reconfigure_logs_disable_transition(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Disabling should log a specific transition message."""
        import logging

        limiter = RateLimiter(RateLimitConfig(enabled=True))
        with caplog.at_level(logging.INFO):
            limiter.reconfigure(RateLimitConfig(enabled=False))
        assert "Rate limiting disabled via config reload" in caplog.text

    def test_reconfigure_logs_enable_transition(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Enabling should log a specific transition message."""
        import logging

        limiter = RateLimiter(RateLimitConfig(enabled=False))
        with caplog.at_level(logging.INFO):
            limiter.reconfigure(RateLimitConfig(enabled=True))
        assert "Rate limiting enabled via config reload" in caplog.text

    def test_reconfigure_no_transition_log_when_unchanged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No transition message when enabled state doesn't change."""
        import logging

        limiter = RateLimiter(RateLimitConfig(enabled=True))
        with caplog.at_level(logging.INFO):
            limiter.reconfigure(RateLimitConfig(enabled=True))
        assert "disabled via config reload" not in caplog.text
        assert "enabled via config reload" not in caplog.text


class TestRateLimitMiddleware:
    """Tests for rate_limit_middleware."""

    @pytest.mark.asyncio
    async def test_allows_non_api_paths(self) -> None:
        """Non-API paths should bypass rate limiting."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=1))
        handler = AsyncMock(return_value=web.Response(text="ok"))
        request = _make_api_request("GET", "/files", rate_limiter=limiter)

        response = await rate_limit_middleware(request, handler)
        handler.assert_called_once()
        assert response.text == "ok"

    @pytest.mark.asyncio
    async def test_allows_within_limit(self) -> None:
        """API requests within limit should pass through."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=10))
        handler = AsyncMock(return_value=web.Response(text="ok"))
        request = _make_api_request("GET", "/api/files", rate_limiter=limiter)

        response = await rate_limit_middleware(request, handler)
        handler.assert_called_once()
        assert response.text == "ok"

    @pytest.mark.asyncio
    async def test_returns_429_when_blocked(self) -> None:
        """Should return 429 with Retry-After when rate limited."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=1, window_seconds=60))
        handler = AsyncMock(return_value=web.Response(text="ok"))

        # First request allowed
        req1 = _make_api_request("GET", "/api/files", rate_limiter=limiter)
        await rate_limit_middleware(req1, handler)

        # Second request should be blocked
        req2 = _make_api_request("GET", "/api/files", rate_limiter=limiter)
        response = await rate_limit_middleware(req2, handler)

        assert response.status == 429
        assert "Retry-After" in response.headers
        assert int(response.headers["Retry-After"]) >= 1

    @pytest.mark.asyncio
    async def test_429_response_body_format(self) -> None:
        """429 response should have JSON error body."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=1, window_seconds=60))
        handler = AsyncMock(return_value=web.Response(text="ok"))

        # Exhaust limit
        req1 = _make_api_request("GET", "/api/files", rate_limiter=limiter)
        await rate_limit_middleware(req1, handler)

        # Get blocked response
        req2 = _make_api_request("GET", "/api/files", rate_limiter=limiter)
        response = await rate_limit_middleware(req2, handler)

        assert response.content_type == "application/json"

    @pytest.mark.asyncio
    async def test_exempt_paths_pass_through(self) -> None:
        """Exempt API paths should bypass rate limiting."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=1))
        handler = AsyncMock(return_value=web.Response(text="ok"))

        # Exhaust limit on regular API path
        req1 = _make_api_request("GET", "/api/files", rate_limiter=limiter)
        await rate_limit_middleware(req1, handler)

        # /api/about should still work (exempt)
        req2 = _make_api_request("GET", "/api/about", rate_limiter=limiter)
        response = await rate_limit_middleware(req2, handler)
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_disabled_passes_all(self) -> None:
        """When disabled, all API requests should pass through."""
        limiter = RateLimiter(RateLimitConfig(enabled=False, get_max_requests=1))
        handler = AsyncMock(return_value=web.Response(text="ok"))

        for _ in range(10):
            request = _make_api_request("GET", "/api/files", rate_limiter=limiter)
            response = await rate_limit_middleware(request, handler)
            assert response.status == 200

    @pytest.mark.asyncio
    async def test_fails_open_on_exception(self) -> None:
        """Middleware should allow request if rate limiter throws."""
        limiter = RateLimiter(RateLimitConfig(get_max_requests=10))

        # Break the limiter's check method
        def broken_check(*args, **kwargs):
            raise RuntimeError("simulated failure")

        limiter.check = broken_check  # type: ignore[assignment]

        handler = AsyncMock(return_value=web.Response(text="ok"))
        request = _make_api_request("GET", "/api/files", rate_limiter=limiter)

        response = await rate_limit_middleware(request, handler)
        handler.assert_called_once()
        assert response.status == 200

    @pytest.mark.asyncio
    async def test_no_rate_limiter_in_app_passes_through(self) -> None:
        """When no rate limiter is in the app dict, requests pass through."""
        app = web.Application()
        handler = AsyncMock(return_value=web.Response(text="ok"))
        request = make_mocked_request("GET", "/api/files", app=app)

        response = await rate_limit_middleware(request, handler)
        handler.assert_called_once()
        assert response.status == 200
