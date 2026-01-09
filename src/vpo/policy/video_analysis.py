"""Video stream analysis utilities for policy evaluation.

This module provides pure functions for analyzing video properties and
detecting edge cases that affect transcoding decisions. All functions
are pure and can be tested without FFmpeg dependencies.

Functions in this module:
- parse_frame_rate: Parse FFprobe frame rate strings to floats
- detect_vfr_content: Detect variable frame rate content
- detect_missing_bitrate: Estimate bitrate when metadata is missing
- select_primary_video_stream: Select primary from multiple video streams
- detect_hdr_type: Detect HDR type from color metadata
- build_hdr_preservation_args: Build FFmpeg args for HDR preservation
- analyze_video_tracks: Orchestrate all video analysis
"""

import logging
from dataclasses import dataclass
from enum import Enum

from vpo.db.models import TrackInfo

logger = logging.getLogger(__name__)


class HDRType(Enum):
    """Type of HDR content detected in video."""

    NONE = "none"
    """No HDR detected - standard dynamic range."""

    HDR10 = "hdr10"
    """HDR10 - PQ transfer function (smpte2084)."""

    HLG = "hlg"
    """Hybrid Log-Gamma - broadcast HDR (arib-std-b67)."""

    DOLBY_VISION = "dolby_vision"
    """Dolby Vision - detected from title metadata."""


@dataclass(frozen=True)
class VideoAnalysisResult:
    """Complete result of video stream analysis.

    This dataclass consolidates all video analysis into a single result
    for cleaner API boundaries between policy and executor layers.
    """

    primary_video_track: TrackInfo | None
    """The selected primary video track, or None if no video tracks."""

    primary_video_index: int | None
    """Index of the primary video track."""

    is_vfr: bool
    """True if variable frame rate was detected."""

    vfr_warning: str | None
    """Warning message about VFR, or None."""

    is_hdr: bool
    """True if HDR content was detected."""

    hdr_type: HDRType
    """Specific HDR type detected."""

    hdr_description: str | None
    """Human-readable HDR description, or None."""

    bitrate_estimated: bool
    """True if bitrate was estimated from file size."""

    estimated_bitrate: int | None
    """Estimated or actual video bitrate in bits/second."""

    warnings: tuple[str, ...]
    """All warnings accumulated during analysis."""


def parse_frame_rate(frame_rate_str: str | None) -> float | None:
    """Parse FFprobe frame rate string (e.g., '24000/1001') to float.

    Args:
        frame_rate_str: Frame rate string from ffprobe.

    Returns:
        Frame rate as float, or None if unparseable.
    """
    if not frame_rate_str or frame_rate_str == "0/0":
        return None

    if "/" in frame_rate_str:
        try:
            num, denom = frame_rate_str.split("/")
            denom_val = float(denom)
            if denom_val == 0:
                return None
            return float(num) / denom_val
        except ValueError:
            return None

    try:
        return float(frame_rate_str)
    except ValueError:
        return None


def detect_vfr_content(
    r_frame_rate: str | None,
    avg_frame_rate: str | None,
    tolerance: float = 0.01,
) -> tuple[bool, str | None]:
    """Detect if content is variable frame rate (VFR).

    VFR content is detected when r_frame_rate and avg_frame_rate differ
    significantly. This can cause issues with transcoding as some encoders
    may not handle VFR well.

    Args:
        r_frame_rate: Real frame rate from ffprobe (r_frame_rate).
        avg_frame_rate: Average frame rate from ffprobe (avg_frame_rate).
        tolerance: Maximum relative difference to consider as CFR.

    Returns:
        Tuple of (is_vfr, warning_message).
    """
    r_fps = parse_frame_rate(r_frame_rate)
    avg_fps = parse_frame_rate(avg_frame_rate)

    if r_fps is None or avg_fps is None:
        return False, None

    if avg_fps == 0:
        return False, None

    # Calculate relative difference
    relative_diff = abs(r_fps - avg_fps) / avg_fps

    if relative_diff > tolerance:
        return True, (
            f"Variable frame rate detected (r_frame_rate={r_frame_rate}, "
            f"avg_frame_rate={avg_frame_rate}). Transcoding may produce "
            "inconsistent playback. Consider using -vsync cfr to force CFR output."
        )

    return False, None


def detect_missing_bitrate(
    bitrate: int | None,
    file_size_bytes: int | None,
    duration_seconds: float | None,
) -> tuple[bool, int | None, str | None]:
    """Handle missing bitrate metadata with estimation.

    When bitrate metadata is missing, we can estimate it from file size
    and duration to allow skip conditions to still work.

    Args:
        bitrate: Bitrate from metadata (may be None).
        file_size_bytes: Total file size in bytes.
        duration_seconds: Video duration in seconds.

    Returns:
        Tuple of (was_estimated, estimated_bitrate, warning_message).
    """
    if bitrate is not None and bitrate > 0:
        return False, bitrate, None

    if file_size_bytes is None or duration_seconds is None:
        return (
            True,
            None,
            (
                "Video bitrate metadata is missing and cannot be estimated "
                "(file size or duration unknown). Bitrate-based skip conditions "
                "will be ignored."
            ),
        )

    if duration_seconds <= 0:
        return (
            True,
            None,
            (
                "Video bitrate metadata is missing and cannot be estimated "
                "(duration is zero or negative). Bitrate-based skip conditions "
                "will be ignored."
            ),
        )

    # Estimate total bitrate from file size and duration
    # This includes all streams, so it's an upper bound for video bitrate
    estimated_bps = int((file_size_bytes * 8) / duration_seconds)

    return (
        True,
        estimated_bps,
        (
            f"Video bitrate metadata is missing. Estimated total bitrate: "
            f"{estimated_bps / 1_000_000:.1f} Mbps (based on file size/duration). "
            "This estimate includes all streams and may be higher than actual "
            "video bitrate."
        ),
    )


def select_primary_video_stream(
    tracks: list[TrackInfo],
) -> tuple[TrackInfo | None, list[str]]:
    """Select primary video stream when multiple video streams exist.

    Selects the first video stream marked as default, or the first video
    stream if none are marked default. Generates warnings about additional
    video streams.

    Args:
        tracks: List of all tracks from the file.

    Returns:
        Tuple of (primary_video_track, list_of_warnings).
    """
    video_tracks = [t for t in tracks if t.track_type == "video"]
    warnings: list[str] = []

    if not video_tracks:
        return None, ["No video streams found in file"]

    if len(video_tracks) == 1:
        return video_tracks[0], []

    # Multiple video streams - select primary
    # First check for default flagged stream
    default_tracks = [t for t in video_tracks if t.is_default]

    if default_tracks:
        primary = default_tracks[0]
    else:
        primary = video_tracks[0]

    # Generate warnings about other video streams
    other_indices = [t.index for t in video_tracks if t.index != primary.index]
    warnings.append(
        f"Multiple video streams detected ({len(video_tracks)} total). "
        f"Using stream {primary.index} as primary. "
        f"Streams {other_indices} will be dropped during transcoding."
    )

    return primary, warnings


def detect_hdr_type(tracks: list[TrackInfo]) -> tuple[HDRType, str | None]:
    """Detect HDR type from video color metadata.

    Detection priority:
    1. color_transfer field (most reliable):
       - smpte2084 → HDR10 (PQ)
       - arib-std-b67 → HLG
    2. Title metadata fallback for Dolby Vision (not in color_transfer)

    Args:
        tracks: List of all tracks from the file.

    Returns:
        Tuple of (HDRType, description string or None).
    """
    video_tracks = [t for t in tracks if t.track_type == "video"]

    if not video_tracks:
        return HDRType.NONE, None

    for track in video_tracks:
        # Primary detection: color_transfer field
        if track.color_transfer:
            transfer = track.color_transfer.casefold()
            if transfer == "smpte2084":
                return HDRType.HDR10, "HDR10 (PQ transfer function)"
            if transfer == "arib-std-b67":
                return HDRType.HLG, "HLG (Hybrid Log-Gamma)"

        # Secondary detection: title metadata (for Dolby Vision and other formats)
        if track.title:
            title_lower = track.title.casefold()
            if "dolby vision" in title_lower or "dovi" in title_lower:
                return HDRType.DOLBY_VISION, "Dolby Vision (from title)"
            # Generic HDR indicators in title
            hdr_indicators = ("hdr10+", "hdr10", "hdr", "hlg", "bt2020")
            for indicator in hdr_indicators:
                if indicator in title_lower:
                    # Try to be specific about type
                    if "hlg" in title_lower:
                        return HDRType.HLG, f"HLG (title contains '{indicator}')"
                    return HDRType.HDR10, f"HDR content (title contains '{indicator}')"

    return HDRType.NONE, None


def detect_hdr_content(tracks: list[TrackInfo]) -> tuple[bool, str | None]:
    """Detect if video content contains HDR metadata.

    This is a compatibility wrapper around detect_hdr_type() that returns
    a boolean instead of HDRType enum.

    Args:
        tracks: List of all tracks from the file.

    Returns:
        Tuple of (is_hdr, hdr_type_description).
    """
    hdr_type, description = detect_hdr_type(tracks)
    return hdr_type != HDRType.NONE, description


def build_hdr_preservation_args(hdr_type: HDRType, scaling: bool = False) -> list[str]:
    """Build FFmpeg arguments to preserve HDR metadata during transcoding.

    When scaling HDR content, we need to preserve HDR metadata to avoid
    converting to SDR. This function provides the necessary FFmpeg flags
    based on the specific HDR format.

    Args:
        hdr_type: Type of HDR content (HDR10, HLG, Dolby Vision, or NONE).
        scaling: Whether scaling is being applied.

    Returns:
        List of FFmpeg arguments for HDR preservation.
    """
    if hdr_type == HDRType.NONE:
        return []

    args: list[str] = []

    # Map HDR type to transfer characteristics
    color_trc_map = {
        HDRType.HDR10: "smpte2084",  # PQ (Perceptual Quantizer)
        HDRType.DOLBY_VISION: "smpte2084",  # Dolby Vision uses PQ
        HDRType.HLG: "arib-std-b67",  # HLG transfer function
    }
    color_trc = color_trc_map.get(hdr_type, "smpte2084")

    # Preserve color metadata
    args.extend(
        [
            "-colorspace",
            "bt2020nc",
            "-color_primaries",
            "bt2020",
            "-color_trc",
            color_trc,
        ]
    )

    if scaling:
        # When scaling, we need to ensure HDR metadata is copied
        # Note: Complex HDR tone mapping would require additional filters
        logger.warning(
            "Scaling HDR content may affect quality. HDR metadata will be "
            "preserved, but tone mapping is not applied. Consider keeping "
            "original resolution for HDR."
        )

    return args


def analyze_video_tracks(
    tracks: list[TrackInfo],
    video_bitrate: int | None,
    file_size_bytes: int | None,
    duration_seconds: float | None,
    r_frame_rate: str | None,
    avg_frame_rate: str | None,
) -> VideoAnalysisResult:
    """Orchestrate all video analysis into a single result.

    This is the main entry point for video analysis, combining:
    - Primary video stream selection
    - VFR detection
    - HDR detection
    - Bitrate estimation

    Args:
        tracks: List of all tracks from the file.
        video_bitrate: Video bitrate from metadata (may be None).
        file_size_bytes: Total file size in bytes.
        duration_seconds: Video duration in seconds.
        r_frame_rate: Real frame rate from ffprobe.
        avg_frame_rate: Average frame rate from ffprobe.

    Returns:
        VideoAnalysisResult with all analysis consolidated.
    """
    warnings: list[str] = []

    # Select primary video stream
    primary_track, stream_warnings = select_primary_video_stream(tracks)
    warnings.extend(stream_warnings)

    primary_index = primary_track.index if primary_track else None

    # Detect VFR
    is_vfr, vfr_warning = detect_vfr_content(r_frame_rate, avg_frame_rate)
    if vfr_warning:
        warnings.append(vfr_warning)

    # Detect HDR
    hdr_type, hdr_description = detect_hdr_type(tracks)
    is_hdr = hdr_type != HDRType.NONE

    # Handle bitrate estimation
    bitrate_estimated, estimated_bitrate, bitrate_warning = detect_missing_bitrate(
        video_bitrate, file_size_bytes, duration_seconds
    )
    if bitrate_warning:
        warnings.append(bitrate_warning)

    return VideoAnalysisResult(
        primary_video_track=primary_track,
        primary_video_index=primary_index,
        is_vfr=is_vfr,
        vfr_warning=vfr_warning,
        is_hdr=is_hdr,
        hdr_type=hdr_type,
        hdr_description=hdr_description,
        bitrate_estimated=bitrate_estimated,
        estimated_bitrate=estimated_bitrate,
        warnings=tuple(warnings),
    )
