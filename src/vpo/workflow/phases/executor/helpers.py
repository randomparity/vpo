"""Helper functions for phase execution.

This module contains utility functions for tool caching, track retrieval,
metadata parsing, and executor selection.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vpo.language_analysis.models import LanguageAnalysisResult

from vpo.db.queries import (
    get_language_analysis_for_tracks,
    get_language_segments_for_analyses,
    get_tracks_for_file,
)
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


def get_tools(cache: dict[str, bool] | None) -> dict[str, bool]:
    """Get tool availability, using cache if available.

    Args:
        cache: Existing cache dict or None.

    Returns:
        Tools dict (returns cache if provided, else checks availability).
    """
    if cache is not None:
        return cache
    return check_tool_availability()


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
        parsed = json.loads(file_record.plugin_metadata)
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

    if not isinstance(parsed, dict):
        logger.error(
            "plugin_metadata for file %s (file_id=%s) is not a JSON object "
            "(got %s). Plugin metadata conditions in %s will not be evaluated.",
            file_path,
            file_id,
            type(parsed).__name__,
            context,
        )
        return None

    return parsed


def parse_container_tags(
    file_record: FileRecord | None,
    file_path: Path,
    file_id: str,
) -> dict[str, str] | None:
    """Parse container tags JSON from FileRecord.

    Args:
        file_record: File record from database (may be None).
        file_path: Path to file (for error logging).
        file_id: File ID string (for error logging).

    Returns:
        Parsed container tags dict, or None if unavailable or corrupted.
    """
    from vpo.db.queries.helpers import deserialize_container_tags

    if not file_record or not file_record.container_tags:
        return None

    result = deserialize_container_tags(file_record.container_tags)
    if result is None:
        logger.error(
            "Invalid container_tags for file %s (file_id=%s). "
            "Container metadata conditions will not be evaluated.",
            file_path,
            file_id,
        )
    return result


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
        logger.warning(
            "No executor available for container conversion to '%s' "
            "(ffmpeg=%s, mkvmerge=%s)",
            target,
            tools.get("ffmpeg", False),
            tools.get("mkvmerge", False),
        )
        return None

    # Track filtering or reordering requires remux
    if plan.tracks_removed > 0 or plan.requires_remux:
        if container in ("mkv", "matroska") and tools.get("mkvmerge"):
            return MkvmergeExecutor()
        elif tools.get("ffmpeg"):
            return FFmpegRemuxExecutor()
        logger.warning(
            "No executor available for remux (container=%s, mkvmerge=%s, ffmpeg=%s)",
            container,
            tools.get("mkvmerge", False),
            tools.get("ffmpeg", False),
        )
        return None

    # Metadata-only changes
    if container in ("mkv", "matroska") and tools.get("mkvpropedit"):
        return MkvpropeditExecutor()
    elif tools.get("ffmpeg"):
        return FfmpegMetadataExecutor()

    logger.warning(
        "No executor available for metadata changes (container=%s, "
        "mkvpropedit=%s, ffmpeg=%s)",
        container,
        tools.get("mkvpropedit", False),
        tools.get("ffmpeg", False),
    )
    return None


def get_language_results_for_tracks(
    conn: Connection, tracks: list[TrackInfo]
) -> dict[int, LanguageAnalysisResult] | None:
    """Get language analysis results for audio tracks.

    Fetches language analysis results from the database for audio tracks
    that have database IDs. Used to pass language results to the policy
    evaluator for audio_is_multi_language conditions.

    Args:
        conn: Database connection.
        tracks: List of TrackInfo for the file.

    Returns:
        Dictionary mapping track_id to LanguageAnalysisResult, or None if
        no results found.
    """
    from vpo.language_analysis.models import LanguageAnalysisResult

    # Filter to audio tracks with database IDs
    audio_track_ids = [
        t.id for t in tracks if t.track_type.casefold() == "audio" and t.id is not None
    ]

    if not audio_track_ids:
        logger.debug("No audio tracks with database IDs for language results lookup")
        return None

    # Batch fetch language analysis records
    records = get_language_analysis_for_tracks(conn, audio_track_ids)
    if not records:
        logger.debug(
            "No language analysis results found for %d audio track(s)",
            len(audio_track_ids),
        )
        return None

    # Batch fetch all segments (fixes N+1 query)
    analysis_ids = [r.id for r in records.values() if r.id is not None]
    all_segments = get_language_segments_for_analyses(conn, analysis_ids)

    # Convert records to domain models with segments
    results: dict[int, LanguageAnalysisResult] = {}
    for track_id, record in records.items():
        if record.id is None:
            continue
        segments = all_segments.get(record.id, [])
        results[track_id] = LanguageAnalysisResult.from_record(record, segments)

    return results if results else None
