"""Tests for process command worker utilities.

Renamed as part of CLI reorganization. The `policy run` command
was promoted to top-level `process` command.
"""

from unittest.mock import patch

import pytest

from vpo.cli.process import (
    get_max_workers,
    resolve_worker_count,
)


class TestGetMaxWorkers:
    """Tests for get_max_workers function."""

    def test_returns_half_cpu_cores(self) -> None:
        """Should return half of CPU cores."""
        with patch("os.cpu_count", return_value=8):
            assert get_max_workers() == 4

    def test_minimum_is_one(self) -> None:
        """Minimum return value is 1."""
        with patch("os.cpu_count", return_value=1):
            assert get_max_workers() == 1

    def test_handles_cpu_count_none(self) -> None:
        """Should handle cpu_count returning None."""
        with patch("os.cpu_count", return_value=None):
            # Defaults to 2 CPUs, returns 1
            assert get_max_workers() == 1

    def test_odd_cpu_count_floors(self) -> None:
        """Odd CPU count should floor divide."""
        with patch("os.cpu_count", return_value=7):
            assert get_max_workers() == 3


class TestResolveWorkerCount:
    """Tests for resolve_worker_count function."""

    def test_uses_requested_when_provided(self) -> None:
        """Should use requested value when provided."""
        with patch("os.cpu_count", return_value=16):
            result = resolve_worker_count(requested=4, config_default=2)
            assert result == 4

    def test_uses_config_default_when_not_requested(self) -> None:
        """Should use config default when requested is None."""
        with patch("os.cpu_count", return_value=16):
            result = resolve_worker_count(requested=None, config_default=3)
            assert result == 3

    def test_caps_at_max_workers(self) -> None:
        """Should cap at half CPU cores."""
        with patch("os.cpu_count", return_value=4):  # max = 2
            result = resolve_worker_count(requested=10, config_default=2)
            assert result == 2

    def test_logs_warning_when_capped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should log warning when capping worker count."""
        with patch("os.cpu_count", return_value=4):  # max = 2
            result = resolve_worker_count(requested=10, config_default=2)
            assert result == 2
            assert "exceeds cap of 2" in caplog.text

    def test_minimum_is_one(self) -> None:
        """Result is at least 1."""
        with patch("os.cpu_count", return_value=16):
            result = resolve_worker_count(requested=0, config_default=2)
            assert result == 1

    def test_negative_becomes_one(self) -> None:
        """Negative values become 1."""
        with patch("os.cpu_count", return_value=16):
            result = resolve_worker_count(requested=-5, config_default=2)
            assert result == 1


# Note: Progress tracking is now handled by StderrProgressReporter in vpo.jobs.progress
# Tests for progress reporters are in tests/unit/jobs/test_progress.py
