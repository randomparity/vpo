"""Helper functions for phase execution.

This module contains utility functions for tool caching, track retrieval,
metadata parsing, and executor selection.
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from sqlite3 import Connection

from vpo.db.queries import get_tracks_for_file
from vpo.db.types import FileRecord, TrackInfo, tracks_to_track_info
from vpo.executor import (
    FfmpegMetadataExecutor,
    FFmpegRemuxExecutor,
    MkvmergeExecutor,
    MkvpropeditExecutor,
    check_tool_availability,
)
from vpo.policy.evaluator import Plan
from vpo.tools.ffmpeg_progress import FFmpegProgress

logger = logging.getLogger(__name__)


def get_tools(cache: dict[str, bool] | None) -> tuple[dict[str, bool], dict[str, bool]]:
    """Get tool availability, using cache if available.

    Args:
        cache: Existing cache dict or None.

    Returns:
        Tuple of (tools dict, updated cache).
    """
    if cache is not None:
        return cache, cache
    tools = check_tool_availability()
    return tools, tools


def get_tracks(conn: Connection, file_id: int) -> list[TrackInfo]:
    """Get tracks from database for a file.

    Args:
        conn: Database connection.
        file_id: Database ID of the file.

    Returns:
        List of TrackInfo for the file.
    """
    track_records = get_tracks_for_file(conn, file_id)
    return tracks_to_track_info(track_records)


def parse_plugin_metadata(
    file_record: FileRecord | None,
    file_path: Path,
    file_id: str,
    context: str = "operations",
) -> dict | None:
    """Parse plugin metadata JSON from FileRecord.

    Args:
        file_record: File record from database (may be None).
        file_path: Path to file (for error logging).
        file_id: File ID string (for error logging).
        context: Context description for error message.

    Returns:
        Parsed metadata dict, or None if unavailable or corrupted.
    """
    if not file_record or not file_record.plugin_metadata:
        return None

    try:
        return json.loads(file_record.plugin_metadata)
    except json.JSONDecodeError as e:
        logger.error(
            "Corrupted plugin_metadata JSON for file %s (file_id=%s): %s. "
            "Plugin metadata conditions in %s will not be evaluated.",
            file_path,
            file_id,
            e,
            context,
        )
        return None


def select_executor(
    plan: Plan,
    container: str,
    tools: dict[str, bool],
    ffmpeg_progress_callback: Callable[[FFmpegProgress], None] | None = None,
) -> (
    MkvpropeditExecutor
    | MkvmergeExecutor
    | FFmpegRemuxExecutor
    | FfmpegMetadataExecutor
    | None
):
    """Select appropriate executor based on plan and container.

    Args:
        plan: The execution plan.
        container: The file container format.
        tools: Dict of tool availability.
        ffmpeg_progress_callback: Optional callback for FFmpeg progress updates.
            Only used when FFmpegRemuxExecutor is selected for container conversion.

    Returns:
        Appropriate executor instance, or None if no tool available.
    """
    # Container conversion takes priority
    if plan.container_change:
        target = plan.container_change.target_format
        if target == "mp4":
            if tools.get("ffmpeg"):
                return FFmpegRemuxExecutor(progress_callback=ffmpeg_progress_callback)
        elif target in ("mkv", "matroska"):
            if tools.get("mkvmerge"):
                return MkvmergeExecutor()
        return None

    # Track filtering or reordering requires remux
    if plan.tracks_removed > 0 or plan.requires_remux:
        if container in ("mkv", "matroska") and tools.get("mkvmerge"):
            return MkvmergeExecutor()
        elif tools.get("ffmpeg"):
            return FFmpegRemuxExecutor()
        return None

    # Metadata-only changes
    if container in ("mkv", "matroska") and tools.get("mkvpropedit"):
        return MkvpropeditExecutor()
    elif tools.get("ffmpeg"):
        return FfmpegMetadataExecutor()

    return None
