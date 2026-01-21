"""Advanced operation handlers.

This module contains handlers for audio synthesis and transcription operations.
"""

import logging
from sqlite3 import Connection
from typing import TYPE_CHECKING

from vpo.db.queries import get_file_by_path
from vpo.db.types import TrackInfo
from vpo.policy.types import OperationType, PhaseExecutionError, PolicySchema

from .helpers import get_tracks, parse_plugin_metadata
from .types import PhaseExecutionState

if TYPE_CHECKING:
    from vpo.db.types import FileInfo
    from vpo.plugin import PluginRegistry

logger = logging.getLogger(__name__)


def execute_audio_synthesis(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    policy: PolicySchema,
    dry_run: bool,
) -> int:
    """Execute audio synthesis operation.

    Args:
        state: Current execution state.
        file_info: FileInfo from database.
        conn: Database connection.
        policy: PolicySchema configuration.
        dry_run: If True, preview without making changes.

    Returns:
        Number of changes made.
    """
    from vpo.policy.synthesis import (
        execute_synthesis_plan,
        plan_synthesis,
    )

    phase = state.phase
    if not phase.audio_synthesis:
        return 0

    file_path = state.file_path

    # Get tracks
    # Note: FileInfo has no file_id attribute, we must look it up
    if file_info is not None:
        tracks: list[TrackInfo] = list(file_info.tracks)
    else:
        file_record = get_file_by_path(conn, str(file_path))
        if file_record is None:
            raise ValueError(f"File not in database: {file_path}")
        tracks = get_tracks(conn, file_record.id)

    # Get file_id from database for audit trail
    file_record = get_file_by_path(conn, str(file_path))
    file_id = str(file_record.id) if file_record else "unknown"

    # Parse plugin metadata from FileRecord
    plugin_metadata = parse_plugin_metadata(
        file_record, file_path, file_id, "synthesis"
    )

    # Plan synthesis
    synthesis_plan = plan_synthesis(
        file_id=file_id,
        file_path=file_path,
        tracks=tracks,
        synthesis_config=phase.audio_synthesis,
        commentary_patterns=policy.config.commentary_patterns,
        plugin_metadata=plugin_metadata,
    )

    if not synthesis_plan.operations:
        logger.debug("No synthesis operations needed")
        return 0

    changes = len(synthesis_plan.operations)

    if dry_run:
        logger.info(
            "[DRY-RUN] Would synthesize %d audio track(s)",
            changes,
        )
        return changes

    # Execute synthesis
    logger.info("Executing audio synthesis: %d track(s)", changes)
    result = execute_synthesis_plan(
        synthesis_plan,
        keep_backup=False,  # Phase manages backup
        dry_run=False,
    )
    if not result.success:
        raise RuntimeError(f"Audio synthesis failed: {result.message}")

    return result.tracks_created


def execute_transcription(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    dry_run: bool,
    plugin_registry: "PluginRegistry | None",
) -> int:
    """Execute transcription analysis operation.

    Uses TranscriptionCoordinator to coordinate:
    1. Multi-sample language detection via smart_detect
    2. Track type classification
    3. Database persistence with proper TranscriptionResultRecord

    Args:
        state: Current execution state.
        file_info: FileInfo from database.
        conn: Database connection.
        dry_run: If True, preview without making changes.
        plugin_registry: Plugin registry for transcription plugins.

    Returns:
        Number of changes made.
    """
    from vpo.transcription.coordinator import (
        DEFAULT_CONFIDENCE_THRESHOLD,
        NoTranscriptionPluginError,
        TranscriptionCoordinator,
        TranscriptionOptions,
    )
    from vpo.workflow.phases.context import (
        FileOperationContext,
    )

    phase = state.phase
    if not phase.transcription or not phase.transcription.enabled:
        return 0

    # Transcription requires plugin registry
    if plugin_registry is None:
        logger.info(
            "Transcription requested but no plugin registry available. "
            "Skipping transcription operation."
        )
        return 0

    file_path = state.file_path

    # Build operation context (handles FileInfo → DB ID mapping)
    # This ensures tracks have their database IDs populated
    try:
        if file_info is not None:
            context = FileOperationContext.from_file_info(file_info, conn)
        else:
            context = FileOperationContext.from_file_path(file_path, conn)
    except ValueError as e:
        raise PhaseExecutionError(
            phase_name=state.phase.name,
            operation=OperationType.TRANSCRIPTION.value,
            message=f"File context creation failed: {e}",
        ) from e

    # Filter to audio tracks with duration
    audio_tracks = [
        t
        for t in context.tracks
        if t.track_type == "audio" and t.duration_seconds is not None
    ]

    if not audio_tracks:
        logger.debug("No audio tracks with duration to transcribe")
        return 0

    if dry_run:
        logger.info(
            "[DRY-RUN] Would analyze %d audio track(s)",
            len(audio_tracks),
        )
        return len(audio_tracks)

    # Create coordinator from plugin registry
    coordinator = TranscriptionCoordinator(plugin_registry)

    if not coordinator.is_available():
        logger.warning(
            "No transcription plugins available. "
            "Install a transcription plugin (e.g., whisper-local)."
        )
        return 0

    # Build options from policy config
    confidence_threshold = (
        phase.transcription.confidence_threshold
        if phase.transcription.confidence_threshold is not None
        else DEFAULT_CONFIDENCE_THRESHOLD
    )
    options = TranscriptionOptions(confidence_threshold=confidence_threshold)

    # Analyze each track
    changes = 0
    for track in audio_tracks:
        try:
            logger.debug("Analyzing track %d", track.index)

            # Coordinator handles extraction → detection → persistence
            coordinator.analyze_and_persist(
                file_path=context.file_path,
                track=track,
                track_duration=track.duration_seconds,
                conn=conn,
                options=options,
            )
            changes += 1

        except NoTranscriptionPluginError as e:
            logger.warning("Transcription plugin not available: %s", e)
            break  # Stop trying other tracks if no plugin
        except Exception as e:
            logger.warning(
                "Transcription failed for track %d: %s",
                track.index,
                e,
            )
            # Continue with other tracks

    return changes
