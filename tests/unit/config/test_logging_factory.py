"""Tests for logging_factory module."""

from __future__ import annotations

from pathlib import Path

import pytest

from video_policy_orchestrator.config.logging_factory import build_logging_config
from video_policy_orchestrator.config.models import LoggingConfig


class TestBuildLoggingConfig:
    """Tests for build_logging_config function."""

    @pytest.fixture
    def base_config(self) -> LoggingConfig:
        """Create a base LoggingConfig for testing."""
        return LoggingConfig(
            level="info",
            file=Path("/var/log/vpo.log"),
            format="text",
            include_stderr=True,
            max_bytes=10_000_000,
            backup_count=5,
        )

    def test_returns_base_values_when_no_overrides(
        self, base_config: LoggingConfig
    ) -> None:
        """Should return base values when no overrides provided."""
        result = build_logging_config(base_config)

        assert result.level == "info"
        assert result.file == Path("/var/log/vpo.log")
        assert result.format == "text"
        assert result.include_stderr is True
        assert result.max_bytes == 10_000_000
        assert result.backup_count == 5

    def test_overrides_level(self, base_config: LoggingConfig) -> None:
        """Should override log level when provided."""
        result = build_logging_config(base_config, level="debug")
        assert result.level == "debug"
        # Other values preserved
        assert result.file == base_config.file
        assert result.format == base_config.format

    def test_overrides_file(self, base_config: LoggingConfig) -> None:
        """Should override file path when provided."""
        new_file = Path("/tmp/test.log")
        result = build_logging_config(base_config, file=new_file)
        assert result.file == new_file
        # Other values preserved
        assert result.level == base_config.level

    def test_overrides_format(self, base_config: LoggingConfig) -> None:
        """Should override format when provided."""
        result = build_logging_config(base_config, format="json")
        assert result.format == "json"
        # Other values preserved
        assert result.level == base_config.level

    def test_overrides_include_stderr(self, base_config: LoggingConfig) -> None:
        """Should override include_stderr when provided."""
        result = build_logging_config(base_config, include_stderr=False)
        assert result.include_stderr is False
        # Other values preserved
        assert result.level == base_config.level

    def test_preserves_max_bytes_and_backup_count(
        self, base_config: LoggingConfig
    ) -> None:
        """Should always preserve max_bytes and backup_count from base."""
        result = build_logging_config(
            base_config,
            level="debug",
            file=Path("/tmp/test.log"),
            format="json",
            include_stderr=False,
        )
        # These are not overridable via CLI
        assert result.max_bytes == base_config.max_bytes
        assert result.backup_count == base_config.backup_count

    def test_returns_new_instance(self, base_config: LoggingConfig) -> None:
        """Should return a new LoggingConfig instance."""
        result = build_logging_config(base_config)
        assert result is not base_config

    def test_multiple_overrides(self, base_config: LoggingConfig) -> None:
        """Should handle multiple overrides at once."""
        result = build_logging_config(
            base_config,
            level="warning",
            format="json",
            include_stderr=False,
        )
        assert result.level == "warning"
        assert result.format == "json"
        assert result.include_stderr is False
        # File not overridden
        assert result.file == base_config.file

    def test_validates_new_values(self) -> None:
        """Should validate new values via LoggingConfig.__post_init__."""
        base = LoggingConfig(level="info", format="text")

        with pytest.raises(ValueError, match="level must be one of"):
            build_logging_config(base, level="invalid")

        with pytest.raises(ValueError, match="format must be one of"):
            build_logging_config(base, format="xml")

    def test_none_values_preserve_base(self, base_config: LoggingConfig) -> None:
        """Explicit None values should preserve base values."""
        result = build_logging_config(
            base_config,
            level=None,
            file=None,
            format=None,
            include_stderr=None,
        )
        assert result.level == base_config.level
        assert result.file == base_config.file
        assert result.format == base_config.format
        assert result.include_stderr == base_config.include_stderr

    def test_with_default_base_config(self) -> None:
        """Should work with default LoggingConfig values."""
        base = LoggingConfig()  # All defaults

        result = build_logging_config(base, level="debug")

        assert result.level == "debug"
        assert result.file is None  # Default
        assert result.format == "text"  # Default
        assert result.include_stderr is True  # Default

    def test_cli_override_use_case(self) -> None:
        """Simulate typical CLI override pattern."""
        # Base config from file
        base = LoggingConfig(
            level="info",
            file=Path("/var/log/vpo.log"),
            format="text",
            include_stderr=True,
        )

        # CLI provides --log-level=debug and --log-json flag
        log_level = "debug"
        log_json = True

        result = build_logging_config(
            base,
            level=log_level,
            format="json" if log_json else None,
        )

        assert result.level == "debug"
        assert result.format == "json"
        # File preserved from base
        assert result.file == Path("/var/log/vpo.log")

    def test_daemon_use_case(self) -> None:
        """Simulate daemon mode override pattern."""
        base = LoggingConfig(
            level="info",
            file=None,
            format="text",
            include_stderr=False,
        )

        # Daemon mode: always include stderr (for journald)
        result = build_logging_config(
            base,
            include_stderr=True,
        )

        assert result.include_stderr is True
        # Other values preserved
        assert result.level == "info"
        assert result.format == "text"
