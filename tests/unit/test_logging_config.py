"""Unit tests for logging configuration.

Tests for T052 (logging configuration) and T053 (JSON formatter output).
"""

import json
import logging
from pathlib import Path

import pytest

from video_policy_orchestrator.config.models import LoggingConfig
from video_policy_orchestrator.logging.config import configure_logging
from video_policy_orchestrator.logging.handlers import JSONFormatter


@pytest.fixture(autouse=True)
def reset_root_logger():
    """Save and restore root logger state between tests."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers[:] = original_handlers
    root.setLevel(original_level)


# =============================================================================
# T052: Unit tests for logging configuration
# =============================================================================


class TestConfigureLogging:
    """Tests for configure_logging()."""

    def test_configure_default_level(self) -> None:
        """Should configure info level by default."""
        config = LoggingConfig(level="info")
        configure_logging(config)

        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_configure_debug_level(self) -> None:
        """Should configure debug level when specified."""
        config = LoggingConfig(level="debug")
        configure_logging(config)

        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_warning_level(self) -> None:
        """Should configure warning level when specified."""
        config = LoggingConfig(level="warning")
        configure_logging(config)

        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_configure_error_level(self) -> None:
        """Should configure error level when specified."""
        config = LoggingConfig(level="error")
        configure_logging(config)

        root = logging.getLogger()
        assert root.level == logging.ERROR

    def test_configure_level_case_insensitive(self) -> None:
        """Should accept level regardless of case."""
        config = LoggingConfig(level="DEBUG")
        configure_logging(config)

        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_stderr_only(self) -> None:
        """Should add stderr handler when no file specified."""
        config = LoggingConfig(level="info", file=None, include_stderr=True)
        configure_logging(config)

        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_configure_file_handler(self, tmp_path: Path) -> None:
        """Should add file handler when file specified."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            level="info",
            file=log_file,
            include_stderr=False,
        )
        configure_logging(config)

        root = logging.getLogger()
        # Should have 1 file handler
        assert len(root.handlers) == 1

    def test_configure_file_and_stderr(self, tmp_path: Path) -> None:
        """Should add both handlers when file and include_stderr."""
        log_file = tmp_path / "test.log"
        config = LoggingConfig(
            level="info",
            file=log_file,
            include_stderr=True,
        )
        configure_logging(config)

        root = logging.getLogger()
        # Should have 2 handlers
        assert len(root.handlers) == 2

    def test_configure_creates_log_directory(self, tmp_path: Path) -> None:
        """Should create log directory if it doesn't exist."""
        log_dir = tmp_path / "logs" / "nested"
        log_file = log_dir / "app.log"
        config = LoggingConfig(
            level="info",
            file=log_file,
            include_stderr=False,
        )
        configure_logging(config)

        assert log_dir.exists()

    def test_configure_fallback_on_file_error(self, tmp_path: Path) -> None:
        """Should fall back to stderr when file is not writable."""
        # Create a directory where we can't write
        unwritable = tmp_path / "unwritable"
        unwritable.mkdir()
        unwritable.chmod(0o444)

        try:
            config = LoggingConfig(
                level="info",
                file=unwritable / "test.log",
                include_stderr=False,
            )
            configure_logging(config)

            root = logging.getLogger()
            # Should have fallen back to stderr
            assert len(root.handlers) >= 1
        finally:
            # Restore permissions for cleanup
            unwritable.chmod(0o755)

    def test_configure_text_formatter(self) -> None:
        """Should use text formatter when format is text."""
        config = LoggingConfig(level="info", format="text")
        configure_logging(config)

        root = logging.getLogger()
        assert not isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_configure_json_formatter(self) -> None:
        """Should use JSON formatter when format is json."""
        config = LoggingConfig(level="info", format="json")
        configure_logging(config)

        root = logging.getLogger()
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_configure_clears_existing_handlers(self) -> None:
        """Should clear existing handlers on reconfiguration."""
        # First configuration
        config1 = LoggingConfig(level="info")
        configure_logging(config1)

        root = logging.getLogger()
        initial_handlers = len(root.handlers)

        # Second configuration
        config2 = LoggingConfig(level="debug")
        configure_logging(config2)

        # Should have same number of handlers (not accumulated)
        assert len(root.handlers) == initial_handlers


# =============================================================================
# T053: Unit tests for JSON formatter output
# =============================================================================


class TestJSONFormatter:
    """Tests for JSONFormatter output."""

    def test_basic_log_entry(self) -> None:
        """Should produce valid JSON with required fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "timestamp" in data
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["logger"] == "test.logger"

    def test_timestamp_is_utc_iso8601(self) -> None:
        """Should produce ISO-8601 UTC timestamp."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # Should be valid ISO-8601 with timezone
        timestamp = data["timestamp"]
        assert "T" in timestamp
        assert timestamp.endswith("+00:00") or timestamp.endswith("Z")

    def test_timestamp_uses_record_created_time(self) -> None:
        """Should use record.created timestamp, not format time."""
        from datetime import datetime, timezone

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )
        # Override record.created to a known past time (2020-01-01 00:00:00 UTC)
        known_timestamp = 1577836800.0
        record.created = known_timestamp

        output = formatter.format(record)
        data = json.loads(output)

        # Parse the output timestamp and verify it matches record.created
        output_dt = datetime.fromisoformat(data["timestamp"])
        expected_dt = datetime.fromtimestamp(known_timestamp, tz=timezone.utc)
        assert output_dt == expected_dt

    def test_message_formatting_with_args(self) -> None:
        """Should format message with arguments."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Value is %s",
            args=("42",),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["message"] == "Value is 42"

    def test_root_logger_no_logger_field(self) -> None:
        """Should not include logger field for root logger."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="root",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "logger" not in data

    def test_empty_name_no_logger_field(self) -> None:
        """Should not include logger field for empty name."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert "logger" not in data

    def test_extra_context_included(self) -> None:
        """Should include extra context fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )
        # Add extra fields
        record.file_path = "/media/movies/file.mkv"
        record.count = 42

        output = formatter.format(record)
        data = json.loads(output)

        assert "context" in data
        assert data["context"]["file_path"] == "/media/movies/file.mkv"
        assert data["context"]["count"] == 42

    def test_exception_info_included(self) -> None:
        """Should include exception info when present."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=42,
                msg="An error occurred",
                args=(),
                exc_info=exc_info,
            )

            output = formatter.format(record)
            data = json.loads(output)

            assert "exception" in data
            assert "ValueError" in data["exception"]
            assert "Test error" in data["exception"]

    def test_all_log_levels(self) -> None:
        """Should work with all log levels."""
        formatter = JSONFormatter()
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level, level_name in levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=42,
                msg="Test",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            data = json.loads(output)

            assert data["level"] == level_name

    def test_special_characters_escaped(self) -> None:
        """Should properly escape special characters in JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg='Message with "quotes" and\nnewlines',
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        # Should be valid JSON
        data = json.loads(output)
        assert '"quotes"' in data["message"]
        assert "\n" in data["message"]
