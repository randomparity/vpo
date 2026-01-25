"""Tests for job progress reporting utilities."""

import io
import sys
from unittest.mock import MagicMock, patch

from vpo.jobs.progress import (
    CompositeProgressReporter,
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
