"""File timestamp operation handler.

This module contains the handler for file_timestamp operations that
control file modification timestamps after processing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlite3 import Connection
from typing import Any

from vpo.core.file_utils import get_file_mtime, set_file_mtime
from vpo.db.queries import get_file_by_path
from vpo.db.types import FileInfo

from .helpers import parse_plugin_metadata
from .types import PhaseExecutionState

logger = logging.getLogger(__name__)


def execute_file_timestamp(
    state: PhaseExecutionState,
    file_info: FileInfo | None,
    conn: Connection,
    dry_run: bool,
) -> int:
    """Execute file timestamp operation.

    Handles file modification timestamp based on policy configuration:
    - preserve: Restore original mtime from state.original_mtime
    - release_date: Set to release/air date from plugin metadata
    - now: No-op (OS already sets current time on modification)

    Args:
        state: Current execution state (contains original_mtime).
        file_info: FileInfo from database.
        conn: Database connection.
        dry_run: If True, preview without making changes.

    Returns:
        Number of changes made (0 or 1).
    """
    phase = state.phase
    config = phase.file_timestamp

    if config is None:
        return 0

    mode = config.mode

    # Mode "now" is a no-op - the OS has already set current time
    if mode == "now":
        logger.debug("file_timestamp mode=now: no operation needed")
        return 0

    if mode == "preserve":
        return _handle_preserve_mode(state, dry_run)

    if mode == "release_date":
        return _handle_release_date_mode(state, file_info, conn, config, dry_run)

    logger.warning("Unknown file_timestamp mode: %s", mode)
    return 0


def _handle_preserve_mode(state: PhaseExecutionState, dry_run: bool) -> int:
    """Handle preserve mode - restore original mtime.

    Args:
        state: Execution state with original_mtime.
        dry_run: If True, preview without making changes.

    Returns:
        Number of changes made.
    """
    original_mtime = state.original_mtime

    if original_mtime is None:
        logger.warning(
            "file_timestamp mode=preserve but original_mtime not captured. "
            "Cannot restore timestamp."
        )
        return 0

    if dry_run:
        dt = datetime.fromtimestamp(original_mtime, tz=timezone.utc)
        logger.info(
            "[DRY-RUN] Would restore file mtime to %s",
            dt.isoformat(),
        )
        return 1

    # Get current mtime to check if change is needed
    current_mtime = get_file_mtime(state.file_path)
    if abs(current_mtime - original_mtime) < 1.0:
        # Less than 1 second difference - no change needed
        logger.debug("File mtime unchanged, skipping restore")
        return 0

    set_file_mtime(state.file_path, original_mtime)
    dt = datetime.fromtimestamp(original_mtime, tz=timezone.utc)
    logger.info("Restored file mtime to %s", dt.isoformat())
    return 1


def _handle_release_date_mode(
    state: PhaseExecutionState,
    file_info: FileInfo | None,
    conn: Connection,
    config: Any,  # FileTimestampConfig
    dry_run: bool,
) -> int:
    """Handle release_date mode - set mtime from plugin metadata.

    Args:
        state: Execution state.
        file_info: FileInfo from database.
        conn: Database connection.
        config: FileTimestampConfig with fallback and date_source.
        dry_run: If True, preview without making changes.

    Returns:
        Number of changes made.
    """
    file_path = state.file_path

    # Get plugin metadata
    file_record = get_file_by_path(conn, str(file_path))
    if file_record is None:
        logger.warning(
            "file_timestamp: File not in database, cannot get metadata: %s",
            file_path,
        )
        return _apply_fallback(state, config.fallback, dry_run)

    file_id = str(file_record.id)
    plugin_metadata = parse_plugin_metadata(
        file_record, file_path, file_id, "file_timestamp"
    )

    # Find release date from plugin metadata
    release_date = _get_release_date(plugin_metadata, config.date_source)

    if release_date is None:
        logger.debug(
            "No release date found in plugin metadata, using fallback: %s",
            config.fallback,
        )
        return _apply_fallback(state, config.fallback, dry_run)

    # Parse date string to timestamp (midnight UTC on that date)
    try:
        mtime = _parse_date_to_timestamp(release_date)
    except ValueError as e:
        logger.warning("Invalid release date format '%s': %s", release_date, e)
        return _apply_fallback(state, config.fallback, dry_run)

    if dry_run:
        logger.info(
            "[DRY-RUN] Would set file mtime to release date: %s",
            release_date,
        )
        return 1

    set_file_mtime(state.file_path, mtime)
    logger.info("Set file mtime to release date: %s", release_date)
    return 1


def _get_release_date(
    plugin_metadata: dict[str, Any],
    date_source: str,
) -> str | None:
    """Extract release date from plugin metadata.

    Args:
        plugin_metadata: Dict of plugin-provided metadata.
        date_source: Source preference ("auto", "radarr", "sonarr").

    Returns:
        Release date string (YYYY-MM-DD format) or None if not found.
    """
    # Determine which source to check
    if date_source == "radarr":
        sources = ["radarr"]
    elif date_source == "sonarr":
        sources = ["sonarr"]
    else:  # auto
        # Check external_source field to determine which one to use
        external_source = plugin_metadata.get("external_source")
        if external_source == "radarr":
            sources = ["radarr"]
        elif external_source == "sonarr":
            sources = ["sonarr"]
        else:
            # Try both (radarr first)
            sources = ["radarr", "sonarr"]

    # Check for release_date first (the consolidated primary date)
    if release_date := plugin_metadata.get("release_date"):
        return release_date

    # Check source-specific dates
    for source in sources:
        if source == "radarr":
            # Prefer digital, then physical, then cinema
            if date := plugin_metadata.get("digital_release"):
                return date
            if date := plugin_metadata.get("physical_release"):
                return date
            if date := plugin_metadata.get("cinema_release"):
                return date
        elif source == "sonarr":
            # Prefer episode air_date, then premiere_date
            if date := plugin_metadata.get("air_date"):
                return date
            if date := plugin_metadata.get("premiere_date"):
                return date

    return None


def _parse_date_to_timestamp(date_str: str) -> float:
    """Parse a date string to Unix timestamp at midnight UTC.

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        Unix timestamp (seconds since epoch).

    Raises:
        ValueError: If date format is invalid.
    """
    # Parse date (expecting YYYY-MM-DD format)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    # Set to midnight UTC
    dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _apply_fallback(
    state: PhaseExecutionState,
    fallback: str,
    dry_run: bool,
) -> int:
    """Apply fallback behavior when release date is not available.

    Args:
        state: Execution state with original_mtime.
        fallback: Fallback mode ("preserve", "now", "skip").
        dry_run: If True, preview without making changes.

    Returns:
        Number of changes made.
    """
    if fallback == "skip":
        logger.debug("file_timestamp fallback=skip: leaving timestamp as-is")
        return 0

    if fallback == "now":
        logger.debug("file_timestamp fallback=now: leaving timestamp as-is (current)")
        return 0

    if fallback == "preserve":
        return _handle_preserve_mode(state, dry_run)

    logger.warning("Unknown file_timestamp fallback: %s", fallback)
    return 0
