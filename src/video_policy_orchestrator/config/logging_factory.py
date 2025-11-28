"""Logging configuration factory.

This module provides a factory function for building LoggingConfig
instances with CLI overrides applied to a base configuration.
"""

from __future__ import annotations

from pathlib import Path

from video_policy_orchestrator.config.models import LoggingConfig


def build_logging_config(
    base: LoggingConfig,
    *,
    level: str | None = None,
    file: Path | None = None,
    format: str | None = None,
    include_stderr: bool | None = None,
) -> LoggingConfig:
    """Build LoggingConfig by merging base config with CLI overrides.

    Creates a new LoggingConfig instance with values from the base
    configuration, overridden by any non-None CLI arguments.

    This function centralizes the pattern of merging CLI logging options
    with configuration file settings, eliminating duplicate code across
    CLI commands.

    Args:
        base: Base logging configuration (typically from config file).
        level: Override log level (debug, info, warning, error).
               If None, uses base.level.
        file: Override log file path. If None, uses base.file.
        format: Override log format (text, json). If None, uses base.format.
        include_stderr: Override stderr inclusion. If None, uses base.include_stderr.

    Returns:
        New LoggingConfig with overrides applied. Validation runs via
        LoggingConfig.__post_init__, so invalid values will raise ValueError.

    Example:
        # In CLI command:
        config = get_config()
        logging_config = build_logging_config(
            config.logging,
            level=log_level,  # From CLI option
            format="json" if json_flag else None,
        )
        configure_logging(logging_config)
    """
    return LoggingConfig(
        level=level if level is not None else base.level,
        file=file if file is not None else base.file,
        format=format if format is not None else base.format,
        include_stderr=(
            include_stderr if include_stderr is not None else base.include_stderr
        ),
        max_bytes=base.max_bytes,
        backup_count=base.backup_count,
    )


def configure_logging_from_cli(
    *,
    config_path: Path | None = None,
    level: str | None = None,
    file: Path | None = None,
    format: str | None = None,
    include_stderr: bool | None = None,
) -> None:
    """Configure logging with CLI overrides.

    Convenience function that loads config, applies overrides, and configures
    logging. Centralizes the pattern used by CLI commands.

    Args:
        config_path: Path to config file (None uses default).
        level: Override log level.
        file: Override log file path.
        format: Override log format ("text" or "json").
        include_stderr: Override stderr inclusion.
    """
    from video_policy_orchestrator.config import get_config
    from video_policy_orchestrator.logging import configure_logging

    config = get_config(config_path=config_path)
    final_config = build_logging_config(
        config.logging,
        level=level,
        file=file,
        format=format,
        include_stderr=include_stderr,
    )
    configure_logging(final_config)
