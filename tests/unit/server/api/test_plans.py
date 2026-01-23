"""Unit tests for plan API endpoints."""

from __future__ import annotations

import time

from vpo.server.api.plans import (
    BulkActionResponse,
    RateLimitState,
    _check_rate_limit,
    _rate_limit_state,
)


class TestBulkActionResponse:
    """Tests for BulkActionResponse dataclass."""

    def test_to_dict_success_only(self) -> None:
        """Response with only success field."""
        response = BulkActionResponse(success=True)
        result = response.to_dict()
        assert result == {"success": True}

    def test_to_dict_with_approved(self) -> None:
        """Response with approved count."""
        response = BulkActionResponse(success=True, approved=5)
        result = response.to_dict()
        assert result == {"success": True, "approved": 5}

    def test_to_dict_with_rejected(self) -> None:
        """Response with rejected count."""
        response = BulkActionResponse(success=True, rejected=3)
        result = response.to_dict()
        assert result == {"success": True, "rejected": 3}

    def test_to_dict_with_failures(self) -> None:
        """Response with failed count and errors."""
        errors = [
            {"plan_id": "uuid1", "error": "Not found"},
            {"plan_id": "uuid2", "error": "Already approved"},
        ]
        response = BulkActionResponse(success=True, approved=3, failed=2, errors=errors)
        result = response.to_dict()
        assert result == {
            "success": True,
            "approved": 3,
            "failed": 2,
            "errors": errors,
        }

    def test_to_dict_excludes_zero_counts(self) -> None:
        """Zero counts should not be included in output."""
        response = BulkActionResponse(success=True, approved=0, rejected=5, failed=0)
        result = response.to_dict()
        assert "approved" not in result
        assert "rejected" in result
        assert "failed" not in result


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def setup_method(self) -> None:
        """Clear rate limit state before each test."""
        _rate_limit_state.clear()

    def test_allows_first_request(self) -> None:
        """First request from a client should be allowed."""
        assert _check_rate_limit("192.168.1.1") is True

    def test_allows_requests_within_limit(self) -> None:
        """Requests within the limit should all be allowed."""
        client_ip = "192.168.1.2"
        for _ in range(10):  # Default limit is 10
            assert _check_rate_limit(client_ip) is True

    def test_blocks_requests_over_limit(self) -> None:
        """Requests over the limit should be blocked."""
        client_ip = "192.168.1.3"
        # Fill up the limit
        for _ in range(10):
            _check_rate_limit(client_ip)

        # 11th request should be blocked
        assert _check_rate_limit(client_ip) is False

    def test_different_clients_independent(self) -> None:
        """Different clients have independent rate limits."""
        client1 = "192.168.1.4"
        client2 = "192.168.1.5"

        # Fill up client1's limit
        for _ in range(10):
            _check_rate_limit(client1)
        assert _check_rate_limit(client1) is False

        # Client2 should still be allowed
        assert _check_rate_limit(client2) is True

    def test_window_expiration(self) -> None:
        """Old requests should expire and allow new ones."""
        client_ip = "192.168.1.6"

        # Fill up the limit
        for _ in range(10):
            _check_rate_limit(client_ip)
        assert _check_rate_limit(client_ip) is False

        # Manually expire the requests by manipulating timestamps
        state = _rate_limit_state[client_ip]
        # All older than 60s
        state.requests = [time.time() - 61 for _ in state.requests]

        # Now should be allowed
        assert _check_rate_limit(client_ip) is True


class TestRateLimitState:
    """Tests for RateLimitState dataclass."""

    def test_default_values(self) -> None:
        """Default values should be sensible."""
        state = RateLimitState(requests=[])
        assert state.window_seconds == 60
        assert state.max_requests == 10


# Note: Full integration tests for the bulk API endpoints would require
# setting up aiohttp test client and mocking the database. Those tests
# should be added to the integration test suite.
