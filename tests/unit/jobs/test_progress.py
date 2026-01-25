"""Tests for job progress reporting utilities."""

import io
import logging
import sqlite3
import sys
import threading
from unittest.mock import MagicMock, patch

from vpo.jobs.progress import (
    CompositeProgressReporter,
    DatabaseProgressReporter,
    NullProgressReporter,
    StderrProgressReporter,
)


class TestStderrProgressReporter:
    """Tests for StderrProgressReporter."""

    def test_on_start_initializes_counts(self):
        """on_start sets total and resets counters."""
        reporter = StderrProgressReporter(enabled=False)
        reporter.on_start(10)

        assert reporter.total == 10
        assert reporter.completed == 0
        assert reporter.active == 0
        assert reporter.failed == 0

    def test_on_item_start_increments_active(self):
        """on_item_start increments active counter."""
        reporter = StderrProgressReporter(enabled=False)
        reporter.on_start(5)
        reporter.on_item_start(0)
        reporter.on_item_start(1)

        assert reporter.active == 2

    def test_on_item_complete_updates_counters(self):
        """on_item_complete decrements active, increments completed."""
        reporter = StderrProgressReporter(enabled=False)
        reporter.on_start(5)
        reporter.on_item_start(0)
        reporter.on_item_complete(0, success=True)

        assert reporter.active == 0
        assert reporter.completed == 1
        assert reporter.failed == 0

    def test_on_item_complete_tracks_failures(self):
        """on_item_complete tracks failed items."""
        reporter = StderrProgressReporter(enabled=False)
        reporter.on_start(5)
        reporter.on_item_start(0)
        reporter.on_item_complete(0, success=False)

        assert reporter.completed == 1
        assert reporter.failed == 1

    def test_writes_to_stderr_when_enabled(self):
        """Progress updates write to stderr when enabled."""
        reporter = StderrProgressReporter(enabled=True)

        # Capture stderr
        captured = io.StringIO()
        with patch.object(sys, "stderr", captured):
            reporter.on_start(3)
            reporter.on_item_start(0)

        output = captured.getvalue()
        assert "Processing:" in output
        assert "0/3" in output
        assert "1 active" in output

    def test_no_output_when_disabled(self):
        """No output when reporter is disabled."""
        reporter = StderrProgressReporter(enabled=False)

        captured = io.StringIO()
        with patch.object(sys, "stderr", captured):
            reporter.on_start(3)
            reporter.on_item_start(0)
            reporter.on_item_complete(0, True)
            reporter.on_complete()

        assert captured.getvalue() == ""

    def test_on_complete_writes_newline(self):
        """on_complete writes newline to finish progress line."""
        reporter = StderrProgressReporter(enabled=True)

        captured = io.StringIO()
        with patch.object(sys, "stderr", captured):
            reporter.on_complete()

        assert captured.getvalue() == "\n"


class TestNullProgressReporter:
    """Tests for NullProgressReporter."""

    def test_all_methods_are_noop(self):
        """All methods complete without error."""
        reporter = NullProgressReporter()

        # These should all be no-ops
        reporter.on_start(10)
        reporter.on_item_start(0)
        reporter.on_item_complete(0, True)
        reporter.on_progress(50.0)
        reporter.on_complete()

        # Just verify no exceptions were raised


class TestCompositeProgressReporter:
    """Tests for CompositeProgressReporter."""

    def test_delegates_to_all_reporters(self):
        """All methods delegate to all contained reporters."""
        mock1 = MagicMock()
        mock2 = MagicMock()
        composite = CompositeProgressReporter([mock1, mock2])

        composite.on_start(10)
        mock1.on_start.assert_called_once_with(10)
        mock2.on_start.assert_called_once_with(10)

        composite.on_item_start(5, "test")
        mock1.on_item_start.assert_called_once_with(5, "test")
        mock2.on_item_start.assert_called_once_with(5, "test")

        composite.on_item_complete(5, True, "done")
        mock1.on_item_complete.assert_called_once_with(5, True, "done")
        mock2.on_item_complete.assert_called_once_with(5, True, "done")

        composite.on_progress(75.0, "msg")
        mock1.on_progress.assert_called_once_with(75.0, "msg")
        mock2.on_progress.assert_called_once_with(75.0, "msg")

        composite.on_complete(True)
        mock1.on_complete.assert_called_once_with(True)
        mock2.on_complete.assert_called_once_with(True)

    def test_works_with_empty_list(self):
        """Works correctly with no reporters."""
        composite = CompositeProgressReporter([])

        # Should not raise
        composite.on_start(10)
        composite.on_item_start(0)
        composite.on_item_complete(0, True)
        composite.on_progress(50.0)
        composite.on_complete()


class TestDatabaseProgressReporter:
    """Tests for DatabaseProgressReporter."""

    def test_on_start_initializes_counters(self):
        """on_start sets total and resets counters."""
        mock_pool = MagicMock()
        reporter = DatabaseProgressReporter(mock_pool, "job-123")
        reporter.on_start(10)

        assert reporter.total == 10
        assert reporter.completed == 0

    def test_on_item_complete_calculates_percent(self):
        """on_item_complete calculates correct percentage."""
        mock_pool = MagicMock()
        reporter = DatabaseProgressReporter(mock_pool, "job-123")
        reporter.on_start(10)
        reporter.on_item_complete(0, True)

        # Should update database with 10% progress
        mock_pool.execute_write.assert_called_with(
            "UPDATE jobs SET progress_percent = ? WHERE id = ?",
            (10.0, "job-123"),
        )

    def test_handles_division_by_zero(self):
        """Handles zero total without crashing."""
        mock_pool = MagicMock()
        reporter = DatabaseProgressReporter(mock_pool, "job-123")
        reporter.on_start(0)  # Zero total
        reporter.on_item_complete(0, True)  # Should not crash

        # Should update with 0% (not crash)
        mock_pool.execute_write.assert_called_with(
            "UPDATE jobs SET progress_percent = ? WHERE id = ?",
            (0.0, "job-123"),
        )

    def test_handles_sqlite_errors_gracefully(self):
        """Handles database errors without raising."""
        mock_pool = MagicMock()
        mock_pool.execute_write.side_effect = sqlite3.Error("DB locked")
        reporter = DatabaseProgressReporter(mock_pool, "job-123")
        reporter.on_start(10)
        reporter.on_item_complete(0, True)  # Should not raise

    def test_handles_pool_closed_error(self):
        """Handles pool closed error without raising."""
        mock_pool = MagicMock()
        mock_pool.execute_write.side_effect = RuntimeError("Pool is closed")
        reporter = DatabaseProgressReporter(mock_pool, "job-123")
        reporter.on_start(10)
        reporter.on_item_complete(0, True)  # Should not raise

    def test_thread_safety(self):
        """Concurrent updates don't corrupt state."""
        mock_pool = MagicMock()
        reporter = DatabaseProgressReporter(mock_pool, "job-123")
        reporter.on_start(100)

        def complete_items():
            for i in range(50):
                reporter.on_item_complete(i, True)

        threads = [threading.Thread(target=complete_items) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert reporter.completed == 100

    def test_on_progress_updates_directly(self):
        """on_progress sends percentage directly to database."""
        mock_pool = MagicMock()
        reporter = DatabaseProgressReporter(mock_pool, "job-123")
        reporter.on_progress(75.0, "message")

        mock_pool.execute_write.assert_called_with(
            "UPDATE jobs SET progress_percent = ? WHERE id = ?",
            (75.0, "job-123"),
        )

    def test_on_complete_sets_100_percent(self):
        """on_complete sets progress to 100%."""
        mock_pool = MagicMock()
        reporter = DatabaseProgressReporter(mock_pool, "job-123")
        reporter.on_complete()

        mock_pool.execute_write.assert_called_with(
            "UPDATE jobs SET progress_percent = ? WHERE id = ?",
            (100.0, "job-123"),
        )


class TestStderrProgressReporterValidation:
    """Tests for StderrProgressReporter state validation."""

    def test_complete_without_start_logs_warning(self, caplog):
        """Complete without start logs warning."""
        reporter = StderrProgressReporter(enabled=False)
        reporter.on_start(5)

        # Complete without starting first
        with caplog.at_level(logging.WARNING):
            reporter.on_item_complete(0, success=True)

        assert "on_item_complete called without matching on_item_start" in caplog.text
        # active should not go negative
        assert reporter.active == 0

    def test_overcomplete_logs_warning(self, caplog):
        """Completing more than total logs warning."""
        reporter = StderrProgressReporter(enabled=False)
        reporter.on_start(2)

        # Complete more than total
        for i in range(3):
            reporter.on_item_start(i)
            reporter.on_item_complete(i, success=True)

        assert "completed (3) exceeds total (2)" in caplog.text

    def test_normal_flow_no_warnings(self, caplog):
        """Normal start/complete flow produces no warnings."""
        reporter = StderrProgressReporter(enabled=False)
        reporter.on_start(2)

        with caplog.at_level(logging.WARNING):
            reporter.on_item_start(0)
            reporter.on_item_complete(0, success=True)
            reporter.on_item_start(1)
            reporter.on_item_complete(1, success=True)

        # No warnings should be logged
        assert "on_item_complete called without" not in caplog.text
        assert "exceeds total" not in caplog.text
