"""Unit tests for SSE events API handlers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vpo.server.api.events import (
    MAX_SSE_CONNECTIONS,
    SSE_DB_TIMEOUT,
    SSE_WRITE_TIMEOUT,
    _compute_jobs_hash,
    _get_client_info,
)


class TestComputeJobsHash:
    """Tests for _compute_jobs_hash function."""

    def test_empty_jobs_list(self) -> None:
        """Empty jobs list returns consistent hash."""
        result = _compute_jobs_hash({"jobs": []})
        assert isinstance(result, str)
        assert len(result) == 16  # SHA256 prefix

    def test_same_jobs_same_hash(self) -> None:
        """Same job data produces same hash."""
        jobs_data = {
            "jobs": [
                {"id": "abc123", "status": "running", "progress_percent": 50},
                {"id": "def456", "status": "completed", "progress_percent": 100},
            ]
        }
        hash1 = _compute_jobs_hash(jobs_data)
        hash2 = _compute_jobs_hash(jobs_data)
        assert hash1 == hash2

    def test_different_jobs_different_hash(self) -> None:
        """Different job data produces different hash."""
        data1 = {"jobs": [{"id": "abc", "status": "running", "progress_percent": 50}]}
        data2 = {
            "jobs": [{"id": "abc", "status": "completed", "progress_percent": 100}]
        }
        assert _compute_jobs_hash(data1) != _compute_jobs_hash(data2)

    def test_order_independent(self) -> None:
        """Hash is stable regardless of job order (sorted internally)."""
        data1 = {
            "jobs": [
                {"id": "aaa", "status": "running", "progress_percent": 50},
                {"id": "bbb", "status": "completed", "progress_percent": 100},
            ]
        }
        data2 = {
            "jobs": [
                {"id": "bbb", "status": "completed", "progress_percent": 100},
                {"id": "aaa", "status": "running", "progress_percent": 50},
            ]
        }
        assert _compute_jobs_hash(data1) == _compute_jobs_hash(data2)

    def test_handles_missing_keys(self) -> None:
        """Hash handles jobs with missing keys gracefully."""
        data = {"jobs": [{"id": "abc", "status": "running"}]}  # No progress_percent
        result = _compute_jobs_hash(data)
        assert isinstance(result, str)

    def test_handles_missing_jobs_key(self) -> None:
        """Hash handles missing jobs key gracefully."""
        result = _compute_jobs_hash({})
        assert isinstance(result, str)


class TestGetClientInfo:
    """Tests for _get_client_info function."""

    def test_extracts_remote_ip(self) -> None:
        """Extracts remote IP from request."""
        request = MagicMock()
        request.remote = "192.168.1.100"
        request.headers = {}

        client_ip, request_id = _get_client_info(request)

        assert client_ip == "192.168.1.100"
        assert request_id == "unknown"

    def test_extracts_request_id_header(self) -> None:
        """Extracts X-Request-ID header."""
        request = MagicMock()
        request.remote = "127.0.0.1"
        request.headers = {"X-Request-ID": "req-12345"}

        client_ip, request_id = _get_client_info(request)

        assert client_ip == "127.0.0.1"
        assert request_id == "req-12345"

    def test_handles_missing_remote(self) -> None:
        """Handles missing remote address."""
        request = MagicMock()
        request.remote = None
        request.headers = {}

        client_ip, request_id = _get_client_info(request)

        assert client_ip == "unknown"
        assert request_id == "unknown"


class TestSSEConfiguration:
    """Tests for SSE configuration constants."""

    def test_connection_limit_reasonable(self) -> None:
        """Connection limit is set to a reasonable value."""
        assert MAX_SSE_CONNECTIONS > 0
        assert MAX_SSE_CONNECTIONS <= 1000

    def test_timeout_values_reasonable(self) -> None:
        """Timeout values are reasonable."""
        assert SSE_WRITE_TIMEOUT > 0
        assert SSE_WRITE_TIMEOUT <= 30
        assert SSE_DB_TIMEOUT > 0
        assert SSE_DB_TIMEOUT <= 30


class TestJobFilterParamsValidation:
    """Tests for query parameter validation in _get_jobs_for_sse."""

    @pytest.mark.asyncio
    async def test_invalid_params_use_defaults(self) -> None:
        """Invalid query parameters fall back to defaults."""
        from vpo.server.api.events import _get_jobs_for_sse

        # Create mock request with invalid params
        request = MagicMock()
        request.query = {"limit": "invalid", "offset": "bad"}
        request.app = {}

        # Should not raise, should return empty result (no db configured)
        result = await _get_jobs_for_sse(request)

        assert result == {"jobs": [], "total": 0, "has_filters": False}

    @pytest.mark.asyncio
    async def test_no_database_returns_empty(self) -> None:
        """Returns empty result when no database configured."""
        from vpo.server.api.events import _get_jobs_for_sse

        request = MagicMock()
        request.query = {}
        request.app = {}  # No connection_pool

        result = await _get_jobs_for_sse(request)

        assert result["jobs"] == []
        assert result["total"] == 0


class TestTemplateXSSEscaping:
    """Tests for template XSS protection in policies.html."""

    def test_category_attribute_escaped(self) -> None:
        """Verify data-category uses |e filter in template."""
        import re
        from pathlib import Path

        template_path = Path("src/vpo/server/ui/templates/sections/policies.html")
        content = template_path.read_text()

        # Check that data-category attribute uses escaping
        match = re.search(r'data-category="[^"]*\|e[^"]*"', content)
        assert match is not None, "data-category should use |e filter"

    def test_description_title_escaped(self) -> None:
        """Verify description title uses |e filter in template."""
        import re
        from pathlib import Path

        template_path = Path("src/vpo/server/ui/templates/sections/policies.html")
        content = template_path.read_text()

        # Check that policy-description title uses escaping
        # Look for title attribute with |e filter
        match = re.search(
            r'class="policy-description"[^>]*title="[^"]*\|e[^"]*"', content
        )
        assert match is not None, "policy-description title should use |e filter"
