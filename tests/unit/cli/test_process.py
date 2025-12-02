"""Tests for cli/process.py module."""

from unittest.mock import patch

import pytest

from video_policy_orchestrator.cli.process import (
    ProgressTracker,
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


class TestProgressTracker:
    """Tests for ProgressTracker class."""

    def test_initial_state(self) -> None:
        """Initial state should be zeros."""
        tracker = ProgressTracker(total=10, enabled=False)
        assert tracker.total == 10
        assert tracker.completed == 0
        assert tracker.active == 0

    def test_start_file_increments_active(self) -> None:
        """start_file should increment active count."""
        tracker = ProgressTracker(total=10, enabled=False)
        tracker.start_file()
        assert tracker.active == 1
        assert tracker.completed == 0

    def test_complete_file_updates_counts(self) -> None:
        """complete_file should update both active and completed."""
        tracker = ProgressTracker(total=10, enabled=False)
        tracker.start_file()
        tracker.complete_file()
        assert tracker.active == 0
        assert tracker.completed == 1

    def test_multiple_active_files(self) -> None:
        """Should track multiple active files."""
        tracker = ProgressTracker(total=10, enabled=False)
        tracker.start_file()
        tracker.start_file()
        tracker.start_file()
        assert tracker.active == 3
        tracker.complete_file()
        assert tracker.active == 2
        assert tracker.completed == 1

    def test_thread_safety(self) -> None:
        """Progress tracker should be thread-safe."""
        import threading

        tracker = ProgressTracker(total=100, enabled=False)
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(10):
                    tracker.start_file()
                    tracker.complete_file()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert tracker.completed == 100
        assert tracker.active == 0

    def test_enabled_false_suppresses_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """enabled=False should suppress stderr output."""
        tracker = ProgressTracker(total=10, enabled=False)
        tracker.start_file()
        tracker.complete_file()
        tracker.finish()
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_enabled_true_writes_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        """enabled=True should write to stderr."""
        tracker = ProgressTracker(total=10, enabled=True)
        tracker.start_file()
        captured = capsys.readouterr()
        assert "Processing:" in captured.err
        assert "[1 active]" in captured.err
