"""Transcode operation handlers.

This module contains handlers for video and audio transcoding operations.
"""

import logging
import subprocess  # nosec B404 - subprocess required for FFmpeg execution
import tempfile
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from vpo.config.loader import get_temp_directory
from vpo.db.queries import get_file_by_path
from vpo.db.types import TrackInfo
from vpo.executor.backup import (
    check_disk_space,
    restore_from_backup,
)
from vpo.executor.backup import (
    create_backup as executor_create_backup,
)
from vpo.executor.interface import require_tool
from vpo.policy.transcode import (
    AudioAction,
    AudioPlan,
    create_audio_plan_v6,
)

from .helpers import get_tracks
from .types import PhaseExecutionState

if TYPE_CHECKING:
    from vpo.db.types import FileInfo

logger = logging.getLogger(__name__)


def execute_transcode(
    state: PhaseExecutionState,
    file_info: "FileInfo | None",
    conn: Connection,
    dry_run: bool,
) -> int:
    """Execute video/audio transcode operation.

    Args:
        state: Current execution state.
        file_info: FileInfo from database.
        conn: Database connection.
        dry_run: If True, preview without making changes.

    Returns:
        Number of changes made.
    """
    from vpo.executor.transcode import TranscodeExecutor
    from vpo.policy.types import TranscodePolicyConfig

    phase = state.phase
    if not phase.transcode and not phase.audio_transcode:
        return 0

    file_path = state.file_path

    # Get tracks
    if file_info is not None:
        tracks: list[TrackInfo] = list(file_info.tracks)
    else:
        file_record = get_file_by_path(conn, str(file_path))
        if file_record is None:
            raise ValueError(f"File not in database: {file_path}")
        tracks = get_tracks(conn, file_record.id)

    changes = 0

    # Video transcode
    if phase.transcode:
        vt = phase.transcode

        # Build TranscodePolicyConfig from VideoTranscodeConfig
        transcode_policy = TranscodePolicyConfig(
            target_video_codec=vt.target_codec,
            target_crf=vt.quality.crf if vt.quality else None,
            max_resolution=vt.scaling.max_resolution if vt.scaling else None,
        )

        # Get video track info
        video_tracks = [t for t in tracks if t.track_type == "video"]
        if not video_tracks:
            logger.info(
                "No video track found in %s, skipping transcode", file_path.name
            )
            return 0
        video_track = video_tracks[0]
        audio_tracks = [t for t in tracks if t.track_type == "audio"]

        # Get file record for size info
        file_record = get_file_by_path(conn, str(file_path))
        file_size_bytes = file_record.size_bytes if file_record else None

        executor = TranscodeExecutor(
            policy=transcode_policy,
            skip_if=vt.skip_if,
            audio_config=phase.audio_transcode,
            backup_original=True,
            temp_directory=get_temp_directory(),
        )

        # Create plan
        plan = executor.create_plan(
            input_path=file_path,
            output_path=file_path,
            video_codec=video_track.codec,
            video_width=video_track.width,
            video_height=video_track.height,
            duration_seconds=video_track.duration_seconds,
            audio_tracks=audio_tracks,
            all_tracks=tracks,
            file_size_bytes=file_size_bytes,
        )

        # Check if transcoding should be skipped
        if plan.skip_reason:
            logger.info(
                "Skipping transcode for %s: %s",
                file_path,
                plan.skip_reason,
            )
            # Record skip reason for stats tracking
            state.transcode_skip_reason = plan.skip_reason
            return 0

        if dry_run:
            logger.info(
                "[DRY-RUN] Would transcode video to %s",
                vt.target_codec,
            )
            changes += 1
        else:
            # Capture file size before transcode for logging
            state.size_before = file_path.stat().st_size

            result = executor.execute(plan)
            if not result.success:
                msg = f"Video transcode failed: {result.error_message}"
                raise RuntimeError(msg)
            changes += 1

            # Capture file size after transcode for logging
            state.size_after = file_path.stat().st_size

            # Capture encoding metrics for stats (Issue #264)
            state.encoding_fps = result.encoding_fps
            state.encoding_bitrate_kbps = result.encoding_bitrate_kbps
            state.total_frames = result.total_frames
            state.encoder_type = result.encoder_type

    # Audio transcode (without video transcode)
    elif phase.audio_transcode:
        audio_tracks = [t for t in tracks if t.track_type == "audio"]
        if not audio_tracks:
            logger.info(
                "No audio tracks found in %s, skipping audio transcode",
                file_path.name,
            )
            return 0

        # Create audio plan
        audio_plan = create_audio_plan_v6(audio_tracks, phase.audio_transcode)

        # Check if any tracks need transcoding
        transcode_count = sum(
            1 for t in audio_plan.tracks if t.action == AudioAction.TRANSCODE
        )
        if transcode_count == 0:
            logger.info(
                "All audio tracks already in acceptable codecs, no transcode needed"
            )
            return 0

        if dry_run:
            logger.info(
                "[DRY-RUN] Would transcode %d audio track(s) to %s",
                transcode_count,
                phase.audio_transcode.transcode_to,
            )
            changes += transcode_count
        else:
            # Execute audio-only transcode
            result = execute_audio_only_transcode(
                file_path, tracks, audio_plan, phase.audio_transcode.transcode_to
            )
            if not result:
                raise RuntimeError("Audio transcode failed")
            changes += transcode_count

    return changes


def execute_audio_only_transcode(
    file_path: Path,
    tracks: list[TrackInfo],
    audio_plan: AudioPlan,
    target_codec: str,
) -> bool:
    """Execute audio-only transcode using FFmpeg.

    Copies video and subtitle streams unchanged while transcoding
    audio streams according to the audio plan.

    Args:
        file_path: Path to the media file.
        tracks: All tracks in the file.
        audio_plan: Audio transcode plan from create_audio_plan_v6.
        target_codec: Target audio codec name (for logging).

    Returns:
        True if successful, False otherwise.
    """
    # Pre-flight disk space check
    try:
        check_disk_space(file_path)
    except Exception as e:
        logger.error("Insufficient disk space for audio transcode: %s", e)
        return False

    # Get FFmpeg path
    try:
        ffmpeg_path = require_tool("ffmpeg")
    except FileNotFoundError as e:
        logger.error("FFmpeg not available: %s", e)
        return False

    # Create backup
    try:
        backup_path = executor_create_backup(file_path)
    except (FileNotFoundError, PermissionError) as e:
        logger.error("Backup failed for audio transcode: %s", e)
        return False

    # Create temp output file
    temp_dir = get_temp_directory()
    with tempfile.NamedTemporaryFile(
        suffix=file_path.suffix, delete=False, dir=temp_dir or file_path.parent
    ) as tmp:
        temp_path = Path(tmp.name)

    try:
        # Build FFmpeg command
        cmd = build_audio_transcode_command(
            ffmpeg_path, file_path, temp_path, tracks, audio_plan
        )

        logger.info(
            "Executing audio transcode to %s for %s",
            target_codec,
            file_path.name,
        )
        logger.debug("FFmpeg command: %s", " ".join(str(c) for c in cmd))

        # Execute FFmpeg
        result = subprocess.run(  # nosec B603 - cmd built from validated inputs
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            logger.error("FFmpeg audio transcode failed: %s", result.stderr)
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return False

        # Verify output exists and has reasonable size
        if not temp_path.exists() or temp_path.stat().st_size == 0:
            logger.error("Audio transcode produced empty or missing output")
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return False

        # Atomic replace: move temp to original
        temp_path.replace(file_path)

        # Clean up backup on success
        backup_path.unlink(missing_ok=True)

        logger.info("Audio transcode completed successfully for %s", file_path.name)
        return True

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg audio transcode timed out after 30 minutes")
        temp_path.unlink(missing_ok=True)
        restore_from_backup(backup_path)
        return False
    except Exception as e:
        logger.exception("Unexpected error during audio transcode: %s", e)
        temp_path.unlink(missing_ok=True)
        restore_from_backup(backup_path)
        return False


def build_audio_transcode_command(
    ffmpeg_path: Path,
    input_path: Path,
    output_path: Path,
    tracks: list[TrackInfo],
    audio_plan: AudioPlan,
) -> list[str]:
    """Build FFmpeg command for audio-only transcode.

    Args:
        ffmpeg_path: Path to FFmpeg executable.
        input_path: Path to input file.
        output_path: Path for output file.
        tracks: All tracks in the file.
        audio_plan: Audio transcode plan.

    Returns:
        List of command arguments.
    """
    cmd = [
        str(ffmpeg_path),
        "-i",
        str(input_path),
        "-map",
        "0",  # Copy all streams
        "-c:v",
        "copy",  # Copy video unchanged
        "-c:s",
        "copy",  # Copy subtitles unchanged
    ]

    # Build audio codec args from plan
    output_stream_idx = 0
    for track_plan in audio_plan.tracks:
        if track_plan.action == AudioAction.COPY:
            cmd.extend([f"-c:a:{output_stream_idx}", "copy"])
            output_stream_idx += 1
        elif track_plan.action == AudioAction.TRANSCODE:
            # Map codec name to FFmpeg encoder
            encoder = get_audio_encoder(track_plan.target_codec or "aac")
            cmd.extend([f"-c:a:{output_stream_idx}", encoder])
            if track_plan.target_bitrate:
                cmd.extend([f"-b:a:{output_stream_idx}", track_plan.target_bitrate])
            output_stream_idx += 1
        # AudioAction.REMOVE would exclude the track, but we don't support
        # that in audio-only transcode currently

    # Output file (overwrite if exists)
    cmd.extend(["-y", str(output_path)])

    return cmd


def get_audio_encoder(codec: str) -> str:
    """Get FFmpeg encoder name for a codec.

    Args:
        codec: Target codec name (e.g., 'aac', 'opus', 'flac').

    Returns:
        FFmpeg encoder name.
    """
    encoders = {
        "aac": "aac",
        "ac3": "ac3",
        "eac3": "eac3",
        "flac": "flac",
        "opus": "libopus",
        "mp3": "libmp3lame",
        "vorbis": "libvorbis",
        "pcm_s16le": "pcm_s16le",
        "pcm_s24le": "pcm_s24le",
    }
    return encoders.get(codec.casefold(), "aac")
