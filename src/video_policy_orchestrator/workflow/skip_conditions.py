"""Skip condition evaluation for conditional phase execution.

This module provides functions to evaluate skip_when conditions against
file information and track data to determine if a phase should be skipped.
"""

import logging
import re
from pathlib import Path

from video_policy_orchestrator.db.types import FileInfo, TrackInfo
from video_policy_orchestrator.policy.models import (
    PhaseSkipCondition,
    SkipReason,
    SkipReasonType,
)

logger = logging.getLogger(__name__)


# Resolution to height mapping (standard definitions)
RESOLUTION_HEIGHT_MAP: dict[str, int] = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "2160p": 2160,
    "4k": 2160,
}


def parse_file_size(value: str) -> int | None:
    """Parse file size string (e.g., '5GB', '500MB') to bytes.

    Returns None if the format is invalid.
    """
    match = re.match(
        r"^(\d+(?:\.\d+)?)\s*(B|KB|MB|GB|TB)$", value.strip(), re.IGNORECASE
    )
    if not match:
        return None
    num = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(num * multipliers[unit])


def parse_duration(value: str) -> float | None:
    """Parse duration string (e.g., '30m', '2h', '1h30m') to seconds.

    Returns None if the format is invalid.
    """
    # Try simple formats first: '30m', '2h', '90s'
    simple_match = re.match(
        r"^(\d+(?:\.\d+)?)\s*(s|m|h)$", value.strip(), re.IGNORECASE
    )
    if simple_match:
        num = float(simple_match.group(1))
        unit = simple_match.group(2).lower()
        multipliers = {"s": 1, "m": 60, "h": 3600}
        return num * multipliers[unit]

    # Try compound format: '1h30m'
    compound_match = re.match(r"^(\d+)h(?:(\d+)m)?$", value.strip(), re.IGNORECASE)
    if compound_match:
        hours = int(compound_match.group(1))
        minutes = int(compound_match.group(2)) if compound_match.group(2) else 0
        return hours * 3600 + minutes * 60

    return None


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
    # Check video_codec condition
    if condition.video_codec:
        video_track = get_video_track(file_info)
        if video_track and video_track.codec:
            video_codec_lower = video_track.codec.lower()
            # Check against common codec aliases
            codec_aliases = {
                video_codec_lower,
                video_codec_lower.replace("-", ""),
            }
            # Add specific aliases
            if video_codec_lower in ("hevc", "h265", "h.265"):
                codec_aliases.update({"hevc", "h265", "h.265"})
            if video_codec_lower in ("h264", "h.264", "avc"):
                codec_aliases.update({"h264", "h.264", "avc"})

            for target_codec in condition.video_codec:
                if target_codec.lower() in codec_aliases:
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
        target_codec = condition.audio_codec_exists.lower()
        for track in file_info.tracks:
            if track.track_type == "audio" and track.codec:
                if track.codec.lower() == target_codec:
                    return SkipReason(
                        reason_type=SkipReasonType.CONDITION,
                        message=f"audio_codec_exists: {target_codec}",
                        condition_name="audio_codec_exists",
                        condition_value=track.codec,
                    )

    # Check subtitle_language_exists condition
    if condition.subtitle_language_exists:
        target_lang = condition.subtitle_language_exists.lower()
        for track in file_info.tracks:
            if track.track_type == "subtitle" and track.language:
                if track.language.lower() == target_lang:
                    return SkipReason(
                        reason_type=SkipReasonType.CONDITION,
                        message=f"subtitle_language_exists: {target_lang}",
                        condition_name="subtitle_language_exists",
                        condition_value=track.language,
                    )

    # Check container condition
    if condition.container and file_info.container_format:
        container_lower = file_info.container_format.lower()
        for target in condition.container:
            if target.lower() == container_lower:
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=f"container matches [{', '.join(condition.container)}]",
                    condition_name="container",
                    condition_value=file_info.container_format,
                )

    # Check resolution condition (exact match)
    if condition.resolution:
        video_track = get_video_track(file_info)
        if video_track and video_track.height:
            actual_label = get_video_resolution_label(video_track.height)
            # Normalize '4k' to '2160p' for comparison
            target = condition.resolution.lower()
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
        if video_track and video_track.height:
            target = condition.resolution_under.lower()
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
            if duration is not None and duration < threshold_seconds:
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
            if duration is not None and duration > threshold_seconds:
                msg = f"duration ({duration:.1f}s) over {condition.duration_over}"
                return SkipReason(
                    reason_type=SkipReasonType.CONDITION,
                    message=msg,
                    condition_name="duration_over",
                    condition_value=f"{duration:.1f}s",
                )

    # No conditions matched
    return None
