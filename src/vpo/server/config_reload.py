"""Configuration reload support for hot-reloading config on SIGHUP.

This module provides infrastructure for reloading configuration without
restarting the daemon. Some configuration options are hot-reloadable while
others require a full restart.

Hot-Reloadable:
- jobs.* - retention_days, log_compression_days, log_deletion_days, auto_purge
- worker.* - max_files, max_duration, end_by, cpu_cores
- processing.workers - worker count for batch operations
- logging.level - can update dynamically
- transcription.* - read per request
- language.*, behavior.* - read per operation

Requires Restart:
- server.bind, server.port - socket already bound
- server.auth_token - middleware already created
- database_path - connection pool already created
- tools.* - cached in tool registry at startup
- plugins.* - plugins loaded at startup
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.config.models import VPOConfig

logger = logging.getLogger(__name__)


# Configuration fields that require a restart to take effect
REQUIRES_RESTART_FIELDS = frozenset(
    {
        "server.bind",
        "server.port",
        "server.auth_token",
        "database_path",
        "tools.ffmpeg",
        "tools.ffprobe",
        "tools.mkvmerge",
        "tools.mkvpropedit",
        "plugins.plugin_dirs",
        "plugins.entry_point_group",
        "plugins.auto_load",
        "detection.auto_detect_on_startup",
    }
)


@dataclass
class ReloadState:
    """Tracks configuration reload state for daemon lifecycle."""

    last_reload: datetime | None = None
    """UTC timestamp of last successful reload, None if never reloaded."""

    reload_count: int = 0
    """Number of successful reloads since daemon start."""

    last_error: str | None = None
    """Error message from last failed reload, None if last succeeded."""

    changes_detected: list[str] = field(default_factory=list)
    """List of config fields that changed in last reload."""


@dataclass
class ReloadResult:
    """Result of a configuration reload attempt."""

    success: bool
    """Whether the reload succeeded."""

    changes: list[str]
    """List of changed configuration fields."""

    error: str | None = None
    """Error message if reload failed."""

    requires_restart: list[str] = field(default_factory=list)
    """List of changed fields that require a restart to take effect."""


def _get_nested_attr(obj: object, path: str) -> object:
    """Get a nested attribute from an object using dot notation.

    Args:
        obj: Object to get attribute from.
        path: Dot-separated attribute path (e.g., "server.port").

    Returns:
        The attribute value, or None if not found.
    """
    parts = path.split(".")
    current = obj
    for part in parts:
        try:
            current = getattr(current, part)
        except AttributeError:
            return None
    return current


def _detect_changes(
    old_config: VPOConfig, new_config: VPOConfig
) -> tuple[list[str], list[str]]:
    """Detect which configuration fields changed between old and new config.

    Args:
        old_config: Previous configuration.
        new_config: New configuration.

    Returns:
        Tuple of (changed_fields, requires_restart_fields).
    """
    changed: list[str] = []
    requires_restart: list[str] = []

    # Fields to check (dot-separated paths)
    fields_to_check = [
        # Server config
        "server.bind",
        "server.port",
        "server.shutdown_timeout",
        "server.auth_token",
        # Jobs config
        "jobs.retention_days",
        "jobs.auto_purge",
        "jobs.temp_directory",
        "jobs.backup_original",
        "jobs.disk_space_ratio_hevc",
        "jobs.disk_space_ratio_other",
        "jobs.disk_space_buffer",
        "jobs.log_compression_days",
        "jobs.log_deletion_days",
        # Worker config
        "worker.max_files",
        "worker.max_duration",
        "worker.end_by",
        "worker.cpu_cores",
        # Processing config
        "processing.workers",
        # Logging config
        "logging.level",
        "logging.file",
        "logging.format",
        "logging.include_stderr",
        "logging.max_bytes",
        "logging.backup_count",
        # Tools config
        "tools.ffmpeg",
        "tools.ffprobe",
        "tools.mkvmerge",
        "tools.mkvpropedit",
        # Detection config
        "detection.cache_ttl_hours",
        "detection.auto_detect_on_startup",
        # Behavior config
        "behavior.warn_on_missing_features",
        "behavior.show_upgrade_suggestions",
        # Language config
        "language.standard",
        "language.warn_on_conversion",
        # Transcription config
        "transcription.plugin",
        "transcription.model_size",
        "transcription.sample_duration",
        "transcription.gpu_enabled",
        "transcription.max_samples",
        "transcription.confidence_threshold",
        "transcription.incumbent_bonus",
        # Plugins config (some subset)
        "plugins.plugin_dirs",
        "plugins.entry_point_group",
        "plugins.auto_load",
        "plugins.warn_unacknowledged",
        # Database path
        "database_path",
    ]

    for field_path in fields_to_check:
        old_val = _get_nested_attr(old_config, field_path)
        new_val = _get_nested_attr(new_config, field_path)

        # Handle Path comparisons
        if isinstance(old_val, Path) or isinstance(new_val, Path):
            old_val = str(old_val) if old_val else None
            new_val = str(new_val) if new_val else None

        # Handle list comparisons (e.g., plugin_dirs)
        if isinstance(old_val, list) and isinstance(new_val, list):
            old_val = [str(p) if isinstance(p, Path) else p for p in old_val]
            new_val = [str(p) if isinstance(p, Path) else p for p in new_val]

        if old_val != new_val:
            changed.append(field_path)
            if field_path in REQUIRES_RESTART_FIELDS:
                requires_restart.append(field_path)

    return changed, requires_restart


def _format_change_log(field: str, old_config: VPOConfig, new_config: VPOConfig) -> str:
    """Format a change log message for a single field.

    Args:
        field: The field path that changed.
        old_config: Previous configuration.
        new_config: New configuration.

    Returns:
        Formatted log message.
    """
    old_val = _get_nested_attr(old_config, field)
    new_val = _get_nested_attr(new_config, field)

    # Sanitize auth_token values
    if "auth_token" in field:
        old_val = "****" if old_val else None
        new_val = "****" if new_val else None

    return f"{field}: {old_val!r} -> {new_val!r}"


class ConfigReloader:
    """Handles configuration reloading for the daemon.

    This class manages the reload process, detecting changes and
    applying dynamic updates where possible.
    """

    def __init__(
        self,
        state: ReloadState,
        config_path: Path | None = None,
    ) -> None:
        """Initialize the config reloader.

        Args:
            state: ReloadState to track reload history.
            config_path: Path to config file (uses default if None).
        """
        self._state = state
        self._config_path = config_path
        self._current_config: VPOConfig | None = None

    def set_current_config(self, config: VPOConfig) -> None:
        """Set the current configuration snapshot.

        Args:
            config: Current configuration to compare against on reload.
        """
        self._current_config = config

    async def reload(self) -> ReloadResult:
        """Reload configuration from file.

        Compares new configuration with current snapshot, detects changes,
        logs what changed, and updates state. On validation failure,
        keeps old config and returns error.

        Returns:
            ReloadResult with success status and details.
        """
        from vpo.config.loader import clear_config_cache, get_config

        logger.info("Received SIGHUP, reloading configuration")

        if self._current_config is None:
            error = "No current configuration snapshot to compare against"
            logger.error("Configuration reload failed: %s", error)
            self._state.last_error = error
            return ReloadResult(success=False, changes=[], error=error)

        try:
            # Clear cache to force re-read from file
            clear_config_cache()

            # Load new configuration
            new_config = get_config(config_path=self._config_path)

            # Detect changes
            changes, requires_restart = _detect_changes(
                self._current_config, new_config
            )

            if not changes:
                logger.info("Configuration unchanged, no reload needed")
                return ReloadResult(success=True, changes=[])

            # Log each change
            for field in changes:
                msg = _format_change_log(field, self._current_config, new_config)
                if field in requires_restart:
                    logger.warning("Configuration change requires restart: %s", msg)
                else:
                    logger.info("Configuration changed: %s", msg)

            # Apply dynamic updates that can be changed at runtime
            self._apply_dynamic_updates(changes, new_config)

            # Update state
            self._current_config = new_config
            self._state.last_reload = datetime.now(timezone.utc)
            self._state.reload_count += 1
            self._state.last_error = None
            self._state.changes_detected = changes

            logger.info(
                "Configuration reload complete: %d change(s), %d require restart",
                len(changes),
                len(requires_restart),
            )

            return ReloadResult(
                success=True,
                changes=changes,
                requires_restart=requires_restart,
            )

        except Exception as e:
            error = str(e)
            logger.error("Configuration reload failed: %s", error)
            self._state.last_error = error
            return ReloadResult(success=False, changes=[], error=error)

    def _apply_dynamic_updates(self, changes: list[str], new_config: VPOConfig) -> None:
        """Apply dynamic configuration updates that don't require restart.

        Args:
            changes: List of changed field paths.
            new_config: New configuration to apply.
        """
        # Update log level if changed
        if "logging.level" in changes:
            new_level = new_config.logging.level.upper()
            root_logger = logging.getLogger()
            root_logger.setLevel(new_level)
            logger.info("Updated log level to %s", new_level)
