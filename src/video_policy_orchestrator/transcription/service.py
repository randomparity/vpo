"""Transcription service layer.

This module provides a service layer for transcription CLI commands,
extracting common logic for setup, validation, and result storage.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from video_policy_orchestrator.db.models import (
    FileRecord,
    TrackRecord,
    TranscriptionResultRecord,
    get_file_by_path,
    get_tracks_for_file,
    get_transcription_result,
)
from video_policy_orchestrator.transcription.audio_extractor import is_ffmpeg_available
from video_policy_orchestrator.transcription.registry import (
    PluginNotFoundError,
    get_registry,
)

if TYPE_CHECKING:
    from video_policy_orchestrator.transcription.interface import TranscriptionPlugin

logger = logging.getLogger(__name__)


class TranscriptionSetupError(Exception):
    """Error during transcription setup/validation."""

    pass


@dataclass
class TranscriptionContext:
    """Shared context for transcription operations.

    Contains all validated prerequisites needed to perform transcription
    on audio tracks within a media file.

    Attributes:
        conn: Database connection for storing results.
        transcriber: Plugin to use for transcription.
        file_record: Database record for the target file.
        audio_tracks: List of audio tracks to process.
    """

    conn: sqlite3.Connection
    transcriber: TranscriptionPlugin
    file_record: FileRecord
    audio_tracks: list[TrackRecord]


def prepare_transcription_context(
    conn: sqlite3.Connection | None,
    path: Path,
    plugin_name: str | None = None,
) -> TranscriptionContext:
    """Validate prerequisites and prepare context for transcription.

    This function consolidates the common setup logic shared between
    the 'detect' and 'quick' CLI commands:
    - Database connection validation
    - ffmpeg availability check
    - Plugin acquisition
    - File lookup in database
    - Audio track filtering

    Args:
        conn: Database connection (may be None).
        path: Path to the video file to process.
        plugin_name: Optional specific plugin name to use.

    Returns:
        TranscriptionContext with all validated prerequisites.

    Raises:
        TranscriptionSetupError: If any prerequisite check fails.
    """
    # Check database connection
    if conn is None:
        raise TranscriptionSetupError("Database connection not available")

    # Check ffmpeg availability
    if not is_ffmpeg_available():
        raise TranscriptionSetupError(
            "ffmpeg not found. Please install ffmpeg and ensure it's in PATH."
        )

    # Get transcription plugin
    registry = get_registry()
    try:
        if plugin_name:
            transcriber = registry.get(plugin_name)
        else:
            transcriber = registry.get_default()
            if transcriber is None:
                raise TranscriptionSetupError(
                    "No transcription plugins available. "
                    "Install openai-whisper for local transcription."
                )
    except PluginNotFoundError as e:
        raise TranscriptionSetupError(str(e)) from e

    # Get file from database
    file_record = get_file_by_path(conn, str(path.resolve()))
    if file_record is None:
        raise TranscriptionSetupError(
            f"File not found in database. Run 'vpo scan' first: {path}"
        )

    # Get audio tracks
    tracks = get_tracks_for_file(conn, file_record.id)
    audio_tracks = [t for t in tracks if t.track_type == "audio"]

    if not audio_tracks:
        raise TranscriptionSetupError(f"No audio tracks found in: {path}")

    return TranscriptionContext(
        conn=conn,
        transcriber=transcriber,
        file_record=file_record,
        audio_tracks=audio_tracks,
    )


def get_existing_transcription(
    conn: sqlite3.Connection,
    track_id: int,
) -> TranscriptionResultRecord | None:
    """Get existing transcription result for a track.

    Args:
        conn: Database connection.
        track_id: Track ID to look up.

    Returns:
        Existing transcription result, or None if not found.
    """
    return get_transcription_result(conn, track_id)


def should_skip_track(
    conn: sqlite3.Connection,
    track: TrackRecord,
    force: bool,
) -> tuple[bool, TranscriptionResultRecord | None]:
    """Check if transcription should be skipped for a track.

    Args:
        conn: Database connection.
        track: Track to check.
        force: Whether to force re-detection.

    Returns:
        Tuple of (should_skip, existing_result).
        If should_skip is True, existing_result contains the cached result.
    """
    existing = get_existing_transcription(conn, track.id)
    if existing and not force:
        return True, existing
    return False, None
