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


def _resolve_file_size(file_info: FileInfo, file_path: Path) -> int | None:
    """Get file size from file_info or filesystem."""
    size = file_info.size_bytes
    if size is None and file_path.exists():
        size = file_path.stat().st_size
    return size


def _normalize_resolution_target(target: str) -> str:
    """Normalize resolution target (e.g., '4k' -> '2160p')."""
    t = target.casefold()
    return "2160p" if t == "4k" else t


# ---------------------------------------------------------------------------
# Individual condition checkers
#
# Each returns a SkipReason if the condition matches, None otherwise.
# They are called from both ANY and ALL evaluation modes.
# ---------------------------------------------------------------------------


def _check_video_codec(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.video_codec:
        return None
    if video_track is None:
        logger.debug("Cannot evaluate video_codec condition: no video track found")
        return None
    if not video_track.codec:
        logger.debug("Cannot evaluate video_codec condition: video codec unknown")
        return None
    for target_codec in condition.video_codec:
        if video_codec_matches(video_track.codec, target_codec):
            return SkipReason(
                reason_type=SkipReasonType.CONDITION,
                message=f"video_codec matches [{', '.join(condition.video_codec)}]",
                condition_name="video_codec",
                condition_value=video_track.codec,
            )
    return None


def _check_audio_codec_exists(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.audio_codec_exists:
        return None
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
    return None


def _check_subtitle_language_exists(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.subtitle_language_exists:
        return None
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
    return None


def _check_container(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.container or not file_info.container_format:
        return None
    normalized_container = normalize_container_format(file_info.container_format)
    for target in condition.container:
        if normalize_container_format(target) == normalized_container:
            return SkipReason(
                reason_type=SkipReasonType.CONDITION,
                message=f"container matches [{', '.join(condition.container)}]",
                condition_name="container",
                condition_value=file_info.container_format,
            )
    return None


def _check_resolution(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.resolution:
        return None
    if video_track is None:
        logger.debug("Cannot evaluate resolution condition: no video track found")
        return None
    if not video_track.height:
        logger.debug("Cannot evaluate resolution condition: video height unknown")
        return None
    actual_label = get_video_resolution_label(video_track.height)
    target = _normalize_resolution_target(condition.resolution)
    if actual_label == target:
        return SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message=f"resolution matches {condition.resolution}",
            condition_name="resolution",
            condition_value=actual_label,
        )
    return None


def _check_resolution_under(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.resolution_under:
        return None
    if video_track is None:
        logger.debug("Cannot evaluate resolution_under condition: no video track found")
        return None
    if not video_track.height:
        logger.debug("Cannot evaluate resolution_under condition: video height unknown")
        return None
    target = _normalize_resolution_target(condition.resolution_under)
    threshold_height = RESOLUTION_HEIGHT_MAP.get(target)
    if threshold_height and video_track.height < threshold_height:
        actual_label = get_video_resolution_label(video_track.height)
        return SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message=f"resolution ({actual_label}) under {condition.resolution_under}",
            condition_name="resolution_under",
            condition_value=actual_label,
        )
    return None


def _check_file_size_under(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.file_size_under:
        return None
    threshold_bytes = parse_file_size(condition.file_size_under)
    if threshold_bytes is None:
        logger.warning(
            "Cannot parse file_size_under value: %r", condition.file_size_under
        )
        return None
    if file_size is not None and file_size < threshold_bytes:
        return SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message=f"file_size ({file_size} bytes) under {condition.file_size_under}",
            condition_name="file_size_under",
            condition_value=str(file_size),
        )
    return None


def _check_file_size_over(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.file_size_over:
        return None
    threshold_bytes = parse_file_size(condition.file_size_over)
    if threshold_bytes is None:
        logger.warning(
            "Cannot parse file_size_over value: %r", condition.file_size_over
        )
        return None
    if file_size is not None and file_size > threshold_bytes:
        return SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message=f"file_size ({file_size} bytes) over {condition.file_size_over}",
            condition_name="file_size_over",
            condition_value=str(file_size),
        )
    return None


def _check_duration_under(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.duration_under:
        return None
    threshold_seconds = parse_duration(condition.duration_under)
    if threshold_seconds is None:
        logger.warning(
            "Cannot parse duration_under value: %r", condition.duration_under
        )
        return None
    duration = video_track.duration_seconds if video_track else None
    if duration is None:
        logger.debug("Cannot evaluate duration_under condition: duration unknown")
        return None
    if duration < threshold_seconds:
        return SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message=f"duration ({duration:.1f}s) under {condition.duration_under}",
            condition_name="duration_under",
            condition_value=f"{duration:.1f}s",
        )
    return None


def _check_duration_over(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    video_track: TrackInfo | None,
    file_size: int | None,
) -> SkipReason | None:
    if not condition.duration_over:
        return None
    threshold_seconds = parse_duration(condition.duration_over)
    if threshold_seconds is None:
        logger.warning("Cannot parse duration_over value: %r", condition.duration_over)
        return None
    duration = video_track.duration_seconds if video_track else None
    if duration is None:
        logger.debug("Cannot evaluate duration_over condition: duration unknown")
        return None
    if duration > threshold_seconds:
        return SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message=f"duration ({duration:.1f}s) over {condition.duration_over}",
            condition_name="duration_over",
            condition_value=f"{duration:.1f}s",
        )
    return None


# Ordered list of (condition_field_name, checker_fn) tuples.
# All checkers share a uniform signature:
#   (condition, file_info, video_track, file_size) -> SkipReason | None
# video_track and file_size are pre-resolved once by the caller to avoid
# redundant O(n) track scans and filesystem stat() calls per condition.
_CONDITION_CHECKERS = [
    ("video_codec", _check_video_codec),
    ("audio_codec_exists", _check_audio_codec_exists),
    ("subtitle_language_exists", _check_subtitle_language_exists),
    ("container", _check_container),
    ("resolution", _check_resolution),
    ("resolution_under", _check_resolution_under),
    ("file_size_under", _check_file_size_under),
    ("file_size_over", _check_file_size_over),
    ("duration_under", _check_duration_under),
    ("duration_over", _check_duration_over),
]


def evaluate_skip_when(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    file_path: Path,
) -> SkipReason | None:
    """Evaluate skip_when conditions against file info.

    The `mode` field controls evaluation logic:
    - 'any' (default): skip if ANY condition matches (OR logic)
    - 'all': skip only if ALL conditions match (AND logic)

    Args:
        condition: The skip condition to evaluate
        file_info: File information including tracks
        file_path: Path to the file (for size/duration checks if not in file_info)

    Returns:
        SkipReason if phase should be skipped, None if it should run
    """
    if condition.mode == "all":
        return _evaluate_skip_when_all(condition, file_info, file_path)
    return _evaluate_skip_when_any(condition, file_info, file_path)


def _evaluate_skip_when_any(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    file_path: Path,
) -> SkipReason | None:
    """Evaluate with 'any' mode: skip if ANY condition matches (OR logic)."""
    # Pre-resolve once to avoid redundant O(n) track scans and stat() calls
    video_track = get_video_track(file_info)
    file_size = _resolve_file_size(file_info, file_path)

    for field_name, checker in _CONDITION_CHECKERS:
        if getattr(condition, field_name, None) is None:
            continue
        result = checker(condition, file_info, video_track, file_size)
        if result is not None:
            return result
    return None


def _evaluate_skip_when_all(
    condition: PhaseSkipCondition,
    file_info: FileInfo,
    file_path: Path,
) -> SkipReason | None:
    """Evaluate with 'all' mode: skip only if ALL conditions match (AND logic).

    Evaluates each active condition. If any active condition does NOT match,
    returns None (don't skip). Only returns a SkipReason if every active
    condition matches.
    """
    # Pre-resolve once to avoid redundant O(n) track scans and stat() calls
    video_track = get_video_track(file_info)
    file_size = _resolve_file_size(file_info, file_path)

    matched_reasons: list[str] = []
    active_conditions = 0

    for field_name, checker in _CONDITION_CHECKERS:
        if getattr(condition, field_name, None) is None:
            continue
        active_conditions += 1
        result = checker(condition, file_info, video_track, file_size)
        if result is not None:
            matched_reasons.append(field_name)
        else:
            return None  # At least one active condition didn't match

    # All active conditions matched
    if active_conditions > 0 and len(matched_reasons) == active_conditions:
        return SkipReason(
            reason_type=SkipReasonType.CONDITION,
            message=f"all conditions matched: {', '.join(matched_reasons)}",
            condition_name="skip_when(all)",
            condition_value=", ".join(matched_reasons),
        )

    return None
