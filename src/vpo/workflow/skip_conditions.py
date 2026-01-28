"""Skip condition evaluation for conditional phase execution.

This module provides functions to evaluate skip_when conditions against
file information and track data to determine if a phase should be skipped.
"""

import logging
from pathlib import Path

from vpo.core.codecs import video_codec_matches
from vpo.db.types import FileInfo, TrackInfo
from vpo.policy.evaluator import normalize_container_format
from vpo.policy.parsing import parse_duration, parse_file_size
from vpo.policy.types import (
    PhaseSkipCondition,
    SkipReason,
    SkipReasonType,
)

logger = logging.getLogger(__name__)


# Resolution to height mapping (standard definitions)
# Note: Kept separate from RESOLUTION_MAP in models.py which includes
# width/height tuples for scaling. This map is for height-only comparisons.
RESOLUTION_HEIGHT_MAP: dict[str, int] = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "2160p": 2160,
    "4k": 2160,
    "8k": 4320,
}


def get_video_track(file_info: FileInfo) -> TrackInfo | None:
    """Get the primary video track from file info."""
    for track in file_info.tracks:
        if track.track_type == "video":
            return track
    return None


def get_video_resolution_label(height: int) -> str:
    """Convert video height to resolution label (e.g., 1080 -> '1080p')."""
    if height >= 2160:
        return "2160p"
    elif height >= 1440:
        return "1440p"
    elif height >= 1080:
        return "1080p"
    elif height >= 720:
        return "720p"
    else:
        return "480p"


def evaluate_skip_when(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    file_path: Path,
) -> SkipReason | None:
    """Evaluate skip_when conditions against file info.

    Returns a SkipReason if any condition matches (OR logic), None otherwise.

    Args:
        condition: The skip condition to evaluate
        file_info: File information including tracks
        file_path: Path to the file (for size/duration checks if not in file_info)

    Returns:
        SkipReason if phase should be skipped, None if it should run
    """
    # Check video_codec condition using centralized alias matching
    if condition.video_codec:
        video_track = get_video_track(file_info)
        if video_track is None:
            logger.debug("Cannot evaluate video_codec condition: no video track found")
        elif not video_track.codec:
            logger.debug("Cannot evaluate video_codec condition: video codec unknown")
        else:
            for target_codec in condition.video_codec:
                if video_codec_matches(video_track.codec, target_codec):
                    return SkipReason(
                        reason_type=SkipReasonType.CONDITION,
                        message=(
                            f"video_codec matches [{', '.join(condition.video_codec)}]"
                        ),
                        condition_name="video_codec",
                        condition_value=video_track.codec,
                    )

    # Check audio_codec_exists condition
    if condition.audio_codec_exists:
        target_codec = condition.audio_codec_exists.casefold()
        for track in file_info.tracks:
            if track.track_type == "audio" and track.codec:
                if track.codec.casefold() == target_codec:
                    return SkipReason(
                        reason_type=SkipReasonType.CONDITION,
                        message=f"audio_codec_exists: {target_codec}",
                        condition_name="audio_codec_exists",
                        condition_value=track.codec,
                    )

    # Check subtitle_language_exists condition
    if condition.subtitle_language_exists:
        target_lang = condition.subtitle_language_exists.casefold()
        for track in file_info.tracks:
            if track.track_type == "subtitle" and track.language:
                if track.language.casefold() == target_lang:
                    return SkipReason(
                        reason_type=SkipReasonType.CONDITION,
                        message=f"subtitle_language_exists: {target_lang}",
                        condition_name="subtitle_language_exists",
                        condition_value=track.language,
                    )

    # Check container condition
    if condition.container and file_info.container_format:
        # Normalize container format to handle aliases (e.g., matroska -> mkv)
        normalized_container = normalize_container_format(file_info.container_format)
        for target in condition.container:
            # Normalize target as well to ensure consistent matching
            normalized_target = normalize_container_format(target)
            if normalized_target == normalized_container:
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=f"container matches [{', '.join(condition.container)}]",
                    condition_name="container",
                    condition_value=file_info.container_format,
                )

    # Check resolution condition (exact match)
    if condition.resolution:
        video_track = get_video_track(file_info)
        if video_track is None:
            logger.debug("Cannot evaluate resolution condition: no video track found")
        elif not video_track.height:
            logger.debug("Cannot evaluate resolution condition: video height unknown")
        else:
            actual_label = get_video_resolution_label(video_track.height)
            # Normalize '4k' to '2160p' for comparison
            target = condition.resolution.casefold()
            if target == "4k":
                target = "2160p"
            if actual_label == target:
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=f"resolution matches {condition.resolution}",
                    condition_name="resolution",
                    condition_value=actual_label,
                )

    # Check resolution_under condition
    if condition.resolution_under:
        video_track = get_video_track(file_info)
        if video_track is None:
            logger.debug(
                "Cannot evaluate resolution_under condition: no video track found"
            )
        elif not video_track.height:
            logger.debug(
                "Cannot evaluate resolution_under condition: video height unknown"
            )
        else:
            target = condition.resolution_under.casefold()
            if target == "4k":
                target = "2160p"
            threshold_height = RESOLUTION_HEIGHT_MAP.get(target)
            if threshold_height and video_track.height < threshold_height:
                actual_label = get_video_resolution_label(video_track.height)
                msg = f"resolution ({actual_label}) under {condition.resolution_under}"
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=msg,
                    condition_name="resolution_under",
                    condition_value=actual_label,
                )

    # Check file_size_under condition
    if condition.file_size_under:
        threshold_bytes = parse_file_size(condition.file_size_under)
        if threshold_bytes:
            # Use file_info.size_bytes if available, otherwise check file
            file_size = file_info.size_bytes
            if file_size is None and file_path.exists():
                file_size = file_path.stat().st_size
            if file_size is not None and file_size < threshold_bytes:
                msg = f"file_size ({file_size} bytes) under {condition.file_size_under}"
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=msg,
                    condition_name="file_size_under",
                    condition_value=str(file_size),
                )

    # Check file_size_over condition
    if condition.file_size_over:
        threshold_bytes = parse_file_size(condition.file_size_over)
        if threshold_bytes:
            file_size = file_info.size_bytes
            if file_size is None and file_path.exists():
                file_size = file_path.stat().st_size
            if file_size is not None and file_size > threshold_bytes:
                msg = f"file_size ({file_size} bytes) over {condition.file_size_over}"
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=msg,
                    condition_name="file_size_over",
                    condition_value=str(file_size),
                )

    # Check duration_under condition
    if condition.duration_under:
        threshold_seconds = parse_duration(condition.duration_under)
        if threshold_seconds:
            # Find video track duration
            video_track = get_video_track(file_info)
            duration = video_track.duration_seconds if video_track else None
            if duration is None:
                logger.debug(
                    "Cannot evaluate duration_under condition: duration unknown"
                )
            elif duration < threshold_seconds:
                msg = f"duration ({duration:.1f}s) under {condition.duration_under}"
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=msg,
                    condition_name="duration_under",
                    condition_value=f"{duration:.1f}s",
                )

    # Check duration_over condition
    if condition.duration_over:
        threshold_seconds = parse_duration(condition.duration_over)
        if threshold_seconds:
            video_track = get_video_track(file_info)
            duration = video_track.duration_seconds if video_track else None
            if duration is None:
                logger.debug(
                    "Cannot evaluate duration_over condition: duration unknown"
                )
            elif duration > threshold_seconds:
                msg = f"duration ({duration:.1f}s) over {condition.duration_over}"
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=msg,
                    condition_name="duration_over",
                    condition_value=f"{duration:.1f}s",
                )

    # No conditions matched
    return None
