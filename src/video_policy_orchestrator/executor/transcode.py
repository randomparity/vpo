"""Transcode executor for video/audio transcoding via FFmpeg."""

import logging
import platform
import queue
import shutil
import subprocess  # nosec B404 - subprocess is required for FFmpeg invocation
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from video_policy_orchestrator.db.models import TrackInfo
from video_policy_orchestrator.executor.interface import require_tool
from video_policy_orchestrator.jobs.progress import (
    FFmpegProgress,
    parse_stderr_progress,
)
from video_policy_orchestrator.policy.models import (
    RESOLUTION_MAP,
    AudioTranscodeConfig,
    QualityMode,
    QualitySettings,
    SkipCondition,
    TranscodePolicyConfig,
    get_default_crf,
    parse_bitrate,
)
from video_policy_orchestrator.policy.transcode import (
    AudioAction,
    AudioPlan,
    AudioTrackPlan,
    create_audio_plan,
    create_audio_plan_v6,
    describe_audio_plan,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Two-Pass Encoding Support
# =============================================================================


@dataclass
class TwoPassContext:
    """Context for two-pass encoding.

    Two-pass encoding requires running FFmpeg twice:
    - Pass 1: Analyze video, output to /dev/null, create log file
    - Pass 2: Encode video using the log file for accurate bitrate targeting
    """

    passlogfile: Path
    """Path prefix for pass log files (FFmpeg adds suffixes)."""

    current_pass: int = 1
    """Current pass number (1 or 2)."""

    def cleanup(self) -> None:
        """Remove pass log files after encoding.

        x265 creates: passlogfile.log, passlogfile.log.cutree
        x264 creates: passlogfile-0.log, passlogfile-0.log.mbtree
        """
        suffixes = [".log", ".log.cutree", "-0.log", "-0.log.mbtree"]
        for suffix in suffixes:
            log_file = Path(str(self.passlogfile) + suffix)
            if log_file.exists():
                try:
                    log_file.unlink()
                    logger.debug("Cleaned up pass log file: %s", log_file)
                except OSError as e:
                    logger.warning(
                        "Could not clean up pass log file %s: %s", log_file, e
                    )


# =============================================================================
# Edge Case Detection Utilities
# =============================================================================


def _parse_frame_rate(frame_rate_str: str | None) -> float | None:
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
    r_fps = _parse_frame_rate(r_frame_rate)
    avg_fps = _parse_frame_rate(avg_frame_rate)

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
            transfer = track.color_transfer.lower()
            if transfer == "smpte2084":
                return HDRType.HDR10, "HDR10 (PQ transfer function)"
            if transfer == "arib-std-b67":
                return HDRType.HLG, "HLG (Hybrid Log-Gamma)"

        # Secondary detection: title metadata (for Dolby Vision and other formats)
        if track.title:
            title_lower = track.title.lower()
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


@dataclass
class TranscodeResult:
    """Result of a transcode operation."""

    success: bool
    output_path: Path | None = None
    error_message: str | None = None
    backup_path: Path | None = None


@dataclass(frozen=True)
class SkipEvaluationResult:
    """Result of skip condition evaluation."""

    skip: bool
    """True if transcoding should be skipped."""

    reason: str | None = None
    """Human-readable reason for the skip decision."""


# Codec aliases for matching
CODEC_ALIASES: dict[str, tuple[str, ...]] = {
    "hevc": ("hevc", "h265", "x265"),
    "h265": ("hevc", "h265", "x265"),
    "h264": ("h264", "avc", "x264"),
    "avc": ("h264", "avc", "x264"),
    "vp9": ("vp9", "vp09"),
    "av1": ("av1", "av01", "libaom-av1"),
}


def _codec_matches_any(
    current_codec: str | None, codec_patterns: tuple[str, ...] | None
) -> bool:
    """Check if current codec matches any pattern.

    Args:
        current_codec: Current video codec (from ffprobe).
        codec_patterns: Tuple of codec patterns to match.

    Returns:
        True if codec matches any pattern.
    """
    if codec_patterns is None:
        return True  # No patterns = always passes
    if current_codec is None:
        return False

    current_lower = current_codec.lower()

    for pattern in codec_patterns:
        pattern_lower = pattern.lower()

        # Direct match
        if current_lower == pattern_lower:
            return True

        # Check if pattern has aliases - use exact matching
        aliases = CODEC_ALIASES.get(pattern_lower, ())
        if current_lower in aliases:
            return True

        # Check if current codec has aliases that match pattern exactly
        current_aliases = CODEC_ALIASES.get(current_lower, ())
        if pattern_lower in current_aliases:
            return True

    return False


def _resolution_within_threshold(
    width: int | None,
    height: int | None,
    resolution_within: str | None,
) -> bool:
    """Check if resolution is within the specified threshold.

    Args:
        width: Current video width.
        height: Current video height.
        resolution_within: Resolution preset (e.g., '1080p', '4k').

    Returns:
        True if resolution is at or below threshold.
    """
    if resolution_within is None:
        return True  # No threshold = always passes
    if width is None or height is None:
        return True  # Unknown resolution = can't evaluate, pass

    max_dims = RESOLUTION_MAP.get(resolution_within.lower())
    if max_dims is None:
        return True  # Invalid preset = pass (validation should catch this earlier)

    max_width, max_height = max_dims
    return width <= max_width and height <= max_height


def _bitrate_under_threshold(
    current_bitrate: int | None,
    bitrate_under: str | None,
) -> bool:
    """Check if bitrate is under the specified threshold.

    Args:
        current_bitrate: Current video bitrate in bits per second.
        bitrate_under: Threshold bitrate string (e.g., '10M', '5000k').

    Returns:
        True if bitrate is under threshold.
    """
    if bitrate_under is None:
        return True  # No threshold = always passes
    if current_bitrate is None:
        return True  # Unknown bitrate = can't evaluate, pass

    threshold = parse_bitrate(bitrate_under)
    if threshold is None:
        return True  # Invalid threshold = pass

    return current_bitrate < threshold


def should_skip_transcode(
    skip_if: SkipCondition | None,
    video_codec: str | None,
    video_width: int | None,
    video_height: int | None,
    video_bitrate: int | None,
) -> SkipEvaluationResult:
    """Evaluate skip conditions for video transcoding.

    All specified conditions must pass for skip (AND logic).
    Unspecified conditions (None) are not evaluated and pass by default.

    Args:
        skip_if: Skip condition configuration.
        video_codec: Current video codec.
        video_width: Current video width.
        video_height: Current video height.
        video_bitrate: Current video bitrate in bits per second.

    Returns:
        SkipEvaluationResult with skip decision and reason.
    """
    if skip_if is None:
        return SkipEvaluationResult(skip=False, reason=None)

    # Check codec condition
    codec_matches = _codec_matches_any(video_codec, skip_if.codec_matches)
    if not codec_matches:
        return SkipEvaluationResult(
            skip=False,
            reason=f"Codec '{video_codec}' not in skip list {skip_if.codec_matches}",
        )

    # Check resolution condition
    resolution_ok = _resolution_within_threshold(
        video_width, video_height, skip_if.resolution_within
    )
    if not resolution_ok:
        return SkipEvaluationResult(
            skip=False,
            reason=(
                f"Resolution {video_width}x{video_height} exceeds "
                f"{skip_if.resolution_within} threshold"
            ),
        )

    # Check bitrate condition
    bitrate_ok = _bitrate_under_threshold(video_bitrate, skip_if.bitrate_under)
    if not bitrate_ok:
        threshold = parse_bitrate(skip_if.bitrate_under) or 0
        return SkipEvaluationResult(
            skip=False,
            reason=(
                f"Bitrate {video_bitrate} exceeds "
                f"{skip_if.bitrate_under} ({threshold}) threshold"
            ),
        )

    # All conditions passed - build skip reason
    reasons = []
    if skip_if.codec_matches:
        reasons.append(f"codec is {video_codec}")
    if skip_if.resolution_within:
        res_str = f"{video_width}x{video_height}"
        reasons.append(f"resolution {res_str} within {skip_if.resolution_within}")
    if skip_if.bitrate_under:
        reasons.append(f"bitrate under {skip_if.bitrate_under}")

    reason = (
        "Already compliant: " + ", ".join(reasons) if reasons else "All conditions met"
    )
    return SkipEvaluationResult(skip=True, reason=reason)


@dataclass
class TranscodePlan:
    """Plan for transcoding a file."""

    input_path: Path
    output_path: Path
    policy: TranscodePolicyConfig

    # Video track info (from introspection)
    video_codec: str | None = None
    video_width: int | None = None
    video_height: int | None = None
    video_bitrate: int | None = None
    duration_seconds: float | None = None

    # Audio tracks info
    audio_tracks: list[TrackInfo] | None = None

    # V6 skip condition evaluation result
    skip_result: SkipEvaluationResult | None = None

    # Computed video actions
    needs_video_transcode: bool = False
    needs_video_scale: bool = False
    target_width: int | None = None
    target_height: int | None = None

    # Computed audio plan
    audio_plan: AudioPlan | None = None

    # Edge case detection results
    warnings: list[str] | None = None
    is_vfr: bool = False
    is_hdr: bool = False
    hdr_type: HDRType = HDRType.NONE
    bitrate_estimated: bool = False
    primary_video_index: int | None = None

    @property
    def needs_any_transcode(self) -> bool:
        """True if any transcoding work is needed."""
        # If skip evaluation says skip, no transcode needed
        if self.skip_result and self.skip_result.skip:
            return False
        if self.needs_video_transcode:
            return True
        if self.audio_plan and self.audio_plan.has_changes:
            return True
        return False

    @property
    def should_skip(self) -> bool:
        """True if transcoding should be skipped due to skip conditions."""
        return self.skip_result is not None and self.skip_result.skip

    @property
    def skip_reason(self) -> str | None:
        """Human-readable skip reason if should_skip is True."""
        if self.skip_result and self.skip_result.skip:
            return self.skip_result.reason
        return None


def should_transcode_video(
    policy: TranscodePolicyConfig,
    current_codec: str | None,
    current_width: int | None,
    current_height: int | None,
) -> tuple[bool, bool, int | None, int | None]:
    """Determine if video transcoding is needed.

    Args:
        policy: Transcode policy configuration.
        current_codec: Current video codec (from ffprobe).
        current_width: Current video width.
        current_height: Current video height.

    Returns:
        Tuple of (needs_transcode, needs_scale, target_width, target_height).
    """
    needs_transcode = False
    needs_scale = False
    target_width = None
    target_height = None

    # Check codec compliance
    if policy.target_video_codec:
        target_codec = policy.target_video_codec.lower()
        # Normalize codec names for comparison
        codec_aliases = {
            "hevc": ("hevc", "h265", "x265"),
            "h264": ("h264", "avc", "x264"),
            "vp9": ("vp9", "vp09"),
            "av1": ("av1", "av01"),
        }
        target_variants = codec_aliases.get(target_codec, (target_codec,))

        if current_codec:
            current_normalized = current_codec.lower()
            if not any(variant in current_normalized for variant in target_variants):
                needs_transcode = True
                logger.debug(
                    "Video transcode needed: %s -> %s", current_codec, target_codec
                )

    # Check resolution limits
    max_dims = policy.get_max_dimensions()
    if max_dims and current_width and current_height:
        max_width, max_height = max_dims
        if current_width > max_width or current_height > max_height:
            needs_scale = True
            # Calculate target dimensions maintaining aspect ratio
            width_ratio = max_width / current_width
            height_ratio = max_height / current_height
            scale_ratio = min(width_ratio, height_ratio)

            target_width = int(current_width * scale_ratio)
            target_height = int(current_height * scale_ratio)

            # Ensure even dimensions (required by most codecs)
            target_width = target_width - (target_width % 2)
            target_height = target_height - (target_height % 2)

            logger.debug(
                "Video scale needed: %dx%d -> %dx%d",
                current_width,
                current_height,
                target_width,
                target_height,
            )

    # If we need to scale, we also need to transcode
    if needs_scale:
        needs_transcode = True

    return needs_transcode, needs_scale, target_width, target_height


def _build_quality_args(
    quality: QualitySettings | None,
    policy: TranscodePolicyConfig,
    codec: str,
    encoder: str,
    two_pass_ctx: TwoPassContext | None = None,
) -> list[str]:
    """Build FFmpeg quality-related arguments.

    Supports V6 QualitySettings (takes precedence) and falls back to
    TranscodePolicyConfig for backward compatibility.

    Args:
        quality: V6 quality settings (optional).
        policy: V1-5 transcode policy config.
        codec: Target video codec name.
        encoder: FFmpeg encoder name.
        two_pass_ctx: Context for two-pass encoding (if active).

    Returns:
        List of FFmpeg arguments for quality settings.
    """
    args: list[str] = []

    if quality is not None:
        # V6 quality settings
        if quality.mode == QualityMode.CRF:
            # CRF mode
            crf = quality.crf if quality.crf is not None else get_default_crf(codec)
            args.extend(["-crf", str(crf)])

        elif quality.mode == QualityMode.BITRATE:
            # Bitrate mode
            if quality.bitrate:
                args.extend(["-b:v", quality.bitrate])

            # Two-pass encoding for bitrate mode
            if quality.two_pass and two_pass_ctx:
                if encoder == "libx264":
                    # x264 uses -pass 1/2 and -passlogfile
                    args.extend(["-pass", str(two_pass_ctx.current_pass)])
                    args.extend(["-passlogfile", str(two_pass_ctx.passlogfile)])
                elif encoder == "libx265":
                    # x265 uses x265-params pass=1/2:stats=file
                    x265_params = (
                        f"pass={two_pass_ctx.current_pass}:"
                        f"stats={two_pass_ctx.passlogfile}"
                    )
                    args.extend(["-x265-params", x265_params])
                else:
                    # Other encoders: warn about limited two-pass support
                    logger.warning(
                        "Two-pass encoding requested for %s but may not be "
                        "fully supported. Using single-pass.",
                        encoder,
                    )

        elif quality.mode == QualityMode.CONSTRAINED_QUALITY:
            # Constrained quality: CRF with min/max bitrate bounds
            crf = quality.crf if quality.crf is not None else get_default_crf(codec)
            args.extend(["-crf", str(crf)])
            # Add minimum bitrate if specified
            if quality.min_bitrate:
                args.extend(["-minrate", quality.min_bitrate])
            # Add maximum bitrate if specified
            if quality.max_bitrate:
                args.extend(["-maxrate", quality.max_bitrate])
                # Buffer size typically 2x max bitrate for VBV compliance
                bitrate_val = parse_bitrate(quality.max_bitrate)
                if bitrate_val:
                    bufsize = f"{int(bitrate_val * 2 / 1000)}k"
                    args.extend(["-bufsize", bufsize])

        # Preset (for x264/x265 encoders)
        if encoder in ("libx264", "libx265"):
            args.extend(["-preset", quality.preset])

        # Tune option
        if quality.tune:
            args.extend(["-tune", quality.tune])

    else:
        # Fall back to V1-5 policy settings
        if policy.target_crf is not None:
            args.extend(["-crf", str(policy.target_crf)])
        elif policy.target_bitrate:
            args.extend(["-b:v", policy.target_bitrate])
        else:
            # Default CRF for good quality
            default_crf = get_default_crf(codec)
            args.extend(["-crf", str(default_crf)])

        # Default preset for x264/x265
        if encoder in ("libx264", "libx265"):
            args.extend(["-preset", "medium"])

    return args


def build_ffmpeg_command(
    plan: TranscodePlan,
    cpu_cores: int | None = None,
    quality: QualitySettings | None = None,
    target_codec: str | None = None,
    two_pass_ctx: TwoPassContext | None = None,
) -> list[str]:
    """Build FFmpeg command for transcoding.

    Args:
        plan: Transcode plan with input/output paths and settings.
        cpu_cores: Number of CPU cores to use (None = auto).
        quality: V6 quality settings (overrides policy settings if provided).
        target_codec: V6 target codec (overrides policy codec if provided).
        two_pass_ctx: Context for two-pass encoding (if active).

    Returns:
        List of command arguments.
    """
    ffmpeg_path = require_tool("ffmpeg")
    cmd = [str(ffmpeg_path), "-y", "-hide_banner"]

    # Input file
    cmd.extend(["-i", str(plan.input_path)])

    # Explicit stream mapping (required when AudioAction.REMOVE is present)
    if _needs_explicit_mapping(plan.audio_plan):
        cmd.extend(_build_stream_maps(plan, plan.audio_plan))

    # Video settings
    if plan.needs_video_transcode:
        policy = plan.policy

        # Determine codec (V6 target_codec takes precedence)
        codec = target_codec or policy.target_video_codec or "hevc"
        encoder = _get_encoder(codec)
        cmd.extend(["-c:v", encoder])

        # Build quality arguments (V6 quality takes precedence over policy)
        cmd.extend(_build_quality_args(quality, policy, codec, encoder, two_pass_ctx))

        # Scaling
        if plan.needs_video_scale and plan.target_width and plan.target_height:
            cmd.extend(
                [
                    "-vf",
                    f"scale={plan.target_width}:{plan.target_height}",
                ]
            )

        # HDR preservation (must come after video encoder settings)
        hdr_args = build_hdr_preservation_args(
            plan.hdr_type, scaling=plan.needs_video_scale
        )
        cmd.extend(hdr_args)
    else:
        # Copy video stream
        cmd.extend(["-c:v", "copy"])

    # Audio settings - per-track handling
    if plan.audio_plan and plan.audio_plan.has_changes:
        cmd.extend(_build_audio_args(plan.audio_plan, plan.policy))
    else:
        # No audio plan or no changes - copy all audio
        cmd.extend(["-c:a", "copy"])

    # Subtitle - copy all subtitles
    cmd.extend(["-c:s", "copy"])

    # Thread control
    if cpu_cores:
        cmd.extend(["-threads", str(cpu_cores)])

    # Progress output to stderr
    cmd.extend(["-stats_period", "1"])

    # Output file
    cmd.append(str(plan.output_path))

    return cmd


def build_ffmpeg_command_pass1(
    plan: "TranscodePlan",
    two_pass_ctx: TwoPassContext,
    cpu_cores: int | None = None,
    quality: QualitySettings | None = None,
    target_codec: str | None = None,
) -> list[str]:
    """Build FFmpeg command for first pass of two-pass encoding.

    First pass analyzes the video and writes stats to a log file.
    Output goes to /dev/null (Linux/macOS) or NUL (Windows).

    Args:
        plan: Transcode plan with input/output paths and settings.
        two_pass_ctx: Two-pass context with passlogfile path.
        cpu_cores: Number of CPU cores to use (None = auto).
        quality: V6 quality settings.
        target_codec: V6 target codec.

    Returns:
        List of command arguments.
    """
    ffmpeg_path = require_tool("ffmpeg")
    cmd = [str(ffmpeg_path), "-y", "-hide_banner"]

    # Input file
    cmd.extend(["-i", str(plan.input_path)])

    # Video encoder settings
    policy = plan.policy
    codec = target_codec or policy.target_video_codec or "hevc"
    encoder = _get_encoder(codec)
    cmd.extend(["-c:v", encoder])

    # Quality args with two-pass context (pass 1)
    # Note: _build_quality_args() already adds preset for x264/x265 encoders
    two_pass_ctx.current_pass = 1
    cmd.extend(_build_quality_args(quality, policy, codec, encoder, two_pass_ctx))

    # Scaling (same as pass 2)
    if plan.needs_video_scale and plan.target_width and plan.target_height:
        cmd.extend(["-vf", f"scale={plan.target_width}:{plan.target_height}"])

    # HDR preservation (same as pass 2)
    hdr_args = build_hdr_preservation_args(
        plan.hdr_type, scaling=plan.needs_video_scale
    )
    cmd.extend(hdr_args)

    # No audio on first pass
    cmd.extend(["-an"])

    # Thread control
    if cpu_cores:
        cmd.extend(["-threads", str(cpu_cores)])

    # Progress output to stderr
    cmd.extend(["-stats_period", "1"])

    # Output to null device
    null_device = "NUL" if platform.system() == "Windows" else "/dev/null"
    cmd.extend(["-f", "null", null_device])

    return cmd


def _needs_explicit_mapping(audio_plan: AudioPlan | None) -> bool:
    """Check if explicit stream mapping is needed.

    Explicit mapping is required when any audio track is marked for removal,
    as FFmpeg's default behavior copies all streams.

    Args:
        audio_plan: Audio plan with track actions.

    Returns:
        True if explicit -map arguments are needed.
    """
    if audio_plan is None:
        return False
    return any(t.action == AudioAction.REMOVE for t in audio_plan.tracks)


def _build_stream_maps(
    plan: "TranscodePlan",
    audio_plan: AudioPlan | None,
) -> list[str]:
    """Build explicit stream mapping arguments.

    When explicit mapping is used, we must specify every stream to include.
    Streams not mapped are excluded from the output.

    Args:
        plan: Transcode plan with video info.
        audio_plan: Audio plan with track actions.

    Returns:
        List of -map arguments for FFmpeg.
    """
    args: list[str] = []

    # Map video stream (always include)
    args.extend(["-map", "0:v:0"])

    # Map audio streams (only those not marked for removal)
    if audio_plan:
        for track in audio_plan.tracks:
            if track.action != AudioAction.REMOVE:
                # Map this audio stream by its track index
                args.extend(["-map", f"0:{track.track_index}"])
    else:
        # No audio plan = keep all audio
        args.extend(["-map", "0:a?"])  # ? makes it optional if no audio

    # Map all subtitle streams
    args.extend(["-map", "0:s?"])  # ? makes it optional

    # Map attachments (fonts, etc.)
    args.extend(["-map", "0:t?"])  # ? makes it optional

    return args


def _build_audio_args(
    audio_plan: AudioPlan, policy: TranscodePolicyConfig
) -> list[str]:
    """Build FFmpeg arguments for audio track handling.

    Note: When AudioAction.REMOVE is present, explicit -map is used
    in build_ffmpeg_command() to exclude those tracks. This function
    only needs to specify codecs for remaining tracks, using output
    stream indices (which may differ from input indices if tracks were removed).

    Args:
        audio_plan: The audio handling plan.
        policy: Transcode policy configuration.

    Returns:
        List of FFmpeg arguments for audio.
    """
    args = []

    # Track output stream index (may differ from input if tracks removed)
    output_stream_idx = 0

    # Process each audio track
    for track in audio_plan.tracks:
        if track.action == AudioAction.COPY:
            # Stream copy this track
            args.extend([f"-c:a:{output_stream_idx}", "copy"])
            output_stream_idx += 1
        elif track.action == AudioAction.TRANSCODE:
            # Transcode this track
            target = track.target_codec or policy.audio_transcode_to
            encoder = _get_audio_encoder(target)
            args.extend([f"-c:a:{output_stream_idx}", encoder])

            # Set bitrate for the track
            bitrate = track.target_bitrate or policy.audio_transcode_bitrate
            if bitrate:
                args.extend([f"-b:a:{output_stream_idx}", bitrate])
            output_stream_idx += 1
        elif track.action == AudioAction.REMOVE:
            # Track excluded by -map, no codec args needed
            # Do NOT increment output_stream_idx
            pass

    # Handle downmix as an additional output stream
    if audio_plan.downmix_track:
        downmix = audio_plan.downmix_track
        # Add filter for downmix
        # This creates a new stereo track from the first audio stream
        downmix_filter = _build_downmix_filter(downmix)
        if downmix_filter:
            args.extend(["-filter_complex", downmix_filter])
            # The downmixed stream will be added by the filter

    return args


def _get_audio_encoder(codec: str) -> str:
    """Get FFmpeg audio encoder name for a codec."""
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
    return encoders.get(codec.lower(), "aac")


def _build_downmix_filter(downmix_track: AudioTrackPlan) -> str | None:
    """Build FFmpeg filter for audio downmix.

    Args:
        downmix_track: The downmix track plan.

    Returns:
        Filter string or None if no filter needed.
    """
    # Use the track's actual stream index, not hardcoded 0
    source_index = downmix_track.stream_index

    if downmix_track.channel_layout == "stereo":
        # Downmix to stereo using Dolby Pro Logic II encoding
        return (
            f"[0:a:{source_index}]aresample=matrix_encoding=dplii,"
            f"pan=stereo|FL=FC+0.30*FL+0.30*BL|FR=FC+0.30*FR+0.30*BR[downmix]"
        )
    elif downmix_track.channel_layout == "5.1":
        # Downmix to 5.1 (usually from 7.1)
        return (
            f"[0:a:{source_index}]pan=5.1|FL=FL|FR=FR|FC=FC|LFE=LFE|"
            f"BL=0.5*BL+0.5*SL|BR=0.5*BR+0.5*SR[downmix]"
        )
    return None


def _get_encoder(codec: str) -> str:
    """Get FFmpeg encoder name for a codec (software encoders only)."""
    encoders = {
        "hevc": "libx265",
        "h265": "libx265",
        "h264": "libx264",
        "vp9": "libvpx-vp9",
        "av1": "libaom-av1",
    }
    return encoders.get(codec.lower(), "libx265")


# Hardware encoder mappings by codec and hardware type
HARDWARE_ENCODERS: dict[str, dict[str, str]] = {
    "hevc": {
        "nvenc": "hevc_nvenc",
        "qsv": "hevc_qsv",
        "vaapi": "hevc_vaapi",
    },
    "h265": {
        "nvenc": "hevc_nvenc",
        "qsv": "hevc_qsv",
        "vaapi": "hevc_vaapi",
    },
    "h264": {
        "nvenc": "h264_nvenc",
        "qsv": "h264_qsv",
        "vaapi": "h264_vaapi",
    },
    "av1": {
        "nvenc": "av1_nvenc",  # RTX 40 series only
        "qsv": "av1_qsv",  # Intel Arc / newer iGPU
    },
}

# Patterns in FFmpeg output that indicate hardware encoder memory/resource errors
HW_ENCODER_ERROR_PATTERNS = (
    "cannot load",
    "not found",
    "not supported",
    "nvenc",
    "cuda",
    "device",
    "memory",
    "resource",
    "initialization failed",
    "encoder not found",
    "could not open",
)


def _check_hw_encoder_available(encoder: str) -> bool:
    """Check if a hardware encoder is available on this system.

    Uses FFmpeg to test if the encoder can be loaded.

    Args:
        encoder: FFmpeg encoder name (e.g., 'hevc_nvenc').

    Returns:
        True if encoder appears to be available.
    """
    try:
        ffmpeg_path = require_tool("ffmpeg")
        # Use ffmpeg -encoders to check if encoder is listed
        result = subprocess.run(  # nosec B603
            [str(ffmpeg_path), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return encoder in result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return False


def select_encoder_with_fallback(
    codec: str,
    hw_mode: str = "auto",
    fallback_to_cpu: bool = True,
) -> tuple[str, str]:
    """Select the best available encoder with fallback support.

    Args:
        codec: Target video codec (hevc, h264, etc.).
        hw_mode: Hardware acceleration mode (auto, nvenc, qsv, vaapi, none).
        fallback_to_cpu: Whether to fall back to CPU if HW unavailable.

    Returns:
        Tuple of (encoder_name, encoder_type) where encoder_type is
        'hardware' or 'software'.
    """
    codec_lower = codec.lower()

    # If explicitly set to none, use software encoder
    if hw_mode == "none":
        return _get_encoder(codec_lower), "software"

    # Get hardware encoders for this codec
    hw_encoders = HARDWARE_ENCODERS.get(codec_lower, {})

    if hw_mode == "auto":
        # Try each hardware encoder in preferred order
        hw_priority = ["nvenc", "qsv", "vaapi"]
        for hw_type in hw_priority:
            if hw_type in hw_encoders:
                encoder = hw_encoders[hw_type]
                if _check_hw_encoder_available(encoder):
                    logger.info("Selected hardware encoder: %s", encoder)
                    return encoder, "hardware"
    else:
        # Specific hardware type requested
        if hw_mode in hw_encoders:
            encoder = hw_encoders[hw_mode]
            if _check_hw_encoder_available(encoder):
                logger.info("Selected requested hardware encoder: %s", encoder)
                return encoder, "hardware"
            elif not fallback_to_cpu:
                logger.error(
                    "Requested hardware encoder %s not available and "
                    "fallback_to_cpu is disabled",
                    encoder,
                )
                raise RuntimeError(
                    f"Hardware encoder {encoder} not available. "
                    "Enable fallback_to_cpu or use a different hardware mode."
                )

    # Fall back to software encoder
    logger.info("Hardware encoder not available for %s, using software encoder", codec)
    return _get_encoder(codec_lower), "software"


def detect_hw_encoder_error(stderr_output: str) -> bool:
    """Check if FFmpeg stderr output indicates a hardware encoder error.

    Args:
        stderr_output: FFmpeg stderr output to analyze.

    Returns:
        True if output suggests a hardware encoder failure.
    """
    stderr_lower = stderr_output.lower()
    return any(pattern in stderr_lower for pattern in HW_ENCODER_ERROR_PATTERNS)


class TranscodeExecutor:
    """Executor for video transcoding operations."""

    def __init__(
        self,
        policy: TranscodePolicyConfig,
        skip_if: SkipCondition | None = None,
        audio_config: AudioTranscodeConfig | None = None,
        cpu_cores: int | None = None,
        progress_callback: Callable[[FFmpegProgress], None] | None = None,
        temp_directory: Path | None = None,
        backup_original: bool = True,
        transcode_timeout: float | None = None,
    ) -> None:
        """Initialize the transcode executor.

        Args:
            policy: Transcode policy configuration.
            skip_if: V6 skip condition for conditional transcoding.
            audio_config: V6 audio transcode config for preserve_codecs handling.
            cpu_cores: Number of CPU cores to use.
            progress_callback: Optional callback for progress updates.
            temp_directory: Directory for temp files (None = same as output).
            backup_original: Whether to backup original after success.
            transcode_timeout: Maximum time in seconds for transcode (None = no limit).
        """
        self.policy = policy
        self.skip_if = skip_if
        self.audio_config = audio_config
        self.cpu_cores = cpu_cores
        self.progress_callback = progress_callback
        self.temp_directory = temp_directory
        self.backup_original = backup_original
        self.transcode_timeout = transcode_timeout

    def create_plan(
        self,
        input_path: Path,
        output_path: Path,
        video_codec: str | None = None,
        video_width: int | None = None,
        video_height: int | None = None,
        video_bitrate: int | None = None,
        duration_seconds: float | None = None,
        audio_tracks: list[TrackInfo] | None = None,
        all_tracks: list[TrackInfo] | None = None,
        file_size_bytes: int | None = None,
        r_frame_rate: str | None = None,
        avg_frame_rate: str | None = None,
    ) -> TranscodePlan:
        """Create a transcode plan for a file.

        Args:
            input_path: Path to input file.
            output_path: Path for output file.
            video_codec: Current video codec.
            video_width: Current video width.
            video_height: Current video height.
            video_bitrate: Current video bitrate in bits per second.
            duration_seconds: File duration in seconds.
            audio_tracks: List of audio track info.
            all_tracks: List of all tracks (for edge case detection).
            file_size_bytes: Total file size (for bitrate estimation).
            r_frame_rate: Real frame rate from ffprobe.
            avg_frame_rate: Average frame rate from ffprobe.

        Returns:
            TranscodePlan with computed actions.
        """
        warnings: list[str] = []
        is_vfr = False
        is_hdr = False
        hdr_type = HDRType.NONE
        bitrate_estimated = False
        primary_video_index: int | None = None
        effective_bitrate = video_bitrate

        # Edge case: Detect VFR content (T095)
        if r_frame_rate or avg_frame_rate:
            vfr_detected, vfr_warning = detect_vfr_content(r_frame_rate, avg_frame_rate)
            is_vfr = vfr_detected
            if vfr_warning:
                warnings.append(vfr_warning)
                logger.warning("VFR content: %s - %s", input_path, vfr_warning)

        # Edge case: Handle missing bitrate metadata (T096)
        was_estimated, estimated_bitrate, bitrate_warning = detect_missing_bitrate(
            video_bitrate, file_size_bytes, duration_seconds
        )
        bitrate_estimated = was_estimated
        if estimated_bitrate is not None:
            effective_bitrate = estimated_bitrate
        if bitrate_warning:
            warnings.append(bitrate_warning)
            logger.warning("Bitrate estimation: %s - %s", input_path, bitrate_warning)

        # Edge case: Handle multiple video streams (T099)
        if all_tracks:
            primary_track, multi_video_warnings = select_primary_video_stream(
                all_tracks
            )
            warnings.extend(multi_video_warnings)
            if primary_track:
                primary_video_index = primary_track.index
                for w in multi_video_warnings:
                    logger.warning("Multiple video streams: %s - %s", input_path, w)

            # Edge case: Detect HDR content (T101)
            hdr_type, hdr_desc = detect_hdr_type(all_tracks)
            is_hdr = hdr_type != HDRType.NONE
            if hdr_desc:
                logger.info("HDR detection: %s - %s", input_path, hdr_desc)

        # Evaluate V6 skip conditions using effective (possibly estimated) bitrate
        skip_result = should_skip_transcode(
            skip_if=self.skip_if,
            video_codec=video_codec,
            video_width=video_width,
            video_height=video_height,
            video_bitrate=effective_bitrate,
        )

        # If skip conditions are met, create plan with skip result
        if skip_result.skip:
            logger.info(
                "Skipping video transcode - %s: %s",
                skip_result.reason,
                input_path,
            )
            return TranscodePlan(
                input_path=input_path,
                output_path=output_path,
                policy=self.policy,
                video_codec=video_codec,
                video_width=video_width,
                video_height=video_height,
                video_bitrate=effective_bitrate,
                duration_seconds=duration_seconds,
                audio_tracks=audio_tracks,
                skip_result=skip_result,
                needs_video_transcode=False,
                needs_video_scale=False,
                warnings=warnings if warnings else None,
                is_vfr=is_vfr,
                is_hdr=is_hdr,
                hdr_type=hdr_type,
                bitrate_estimated=bitrate_estimated,
                primary_video_index=primary_video_index,
            )

        # Normal transcode evaluation
        needs_transcode, needs_scale, target_width, target_height = (
            should_transcode_video(
                self.policy,
                video_codec,
                video_width,
                video_height,
            )
        )

        # Edge case: HDR preservation warning (T101)
        if is_hdr and needs_scale:
            warnings.append(
                "HDR content will be scaled. HDR metadata will be preserved, but "
                "visual quality may be affected. Consider keeping original resolution "
                "for HDR content."
            )
            logger.warning(
                "HDR content scaling: %s - consider keeping original resolution",
                input_path,
            )

        # Create audio plan if audio tracks are provided
        # Use V6 audio config if available, otherwise fall back to V1-5 policy
        audio_plan = None
        if audio_tracks:
            if self.audio_config is not None:
                audio_plan = create_audio_plan_v6(audio_tracks, self.audio_config)
            else:
                audio_plan = create_audio_plan(audio_tracks, self.policy)

        return TranscodePlan(
            input_path=input_path,
            output_path=output_path,
            policy=self.policy,
            video_codec=video_codec,
            video_width=video_width,
            video_height=video_height,
            video_bitrate=effective_bitrate,
            duration_seconds=duration_seconds,
            audio_tracks=audio_tracks,
            skip_result=skip_result,
            needs_video_transcode=needs_transcode,
            needs_video_scale=needs_scale,
            target_width=target_width,
            target_height=target_height,
            audio_plan=audio_plan,
            warnings=warnings if warnings else None,
            is_vfr=is_vfr,
            is_hdr=is_hdr,
            hdr_type=hdr_type,
            bitrate_estimated=bitrate_estimated,
            primary_video_index=primary_video_index,
        )

    def is_compliant(
        self,
        video_codec: str | None = None,
        video_width: int | None = None,
        video_height: int | None = None,
    ) -> bool:
        """Check if a file already meets policy requirements.

        Args:
            video_codec: Current video codec.
            video_width: Current video width.
            video_height: Current video height.

        Returns:
            True if file is already compliant.
        """
        needs_transcode, _, _, _ = should_transcode_video(
            self.policy,
            video_codec,
            video_width,
            video_height,
        )
        return not needs_transcode

    def _check_disk_space(
        self,
        plan: TranscodePlan,
        ratio_hevc: float = 0.5,
        ratio_other: float = 0.8,
        buffer: float = 1.2,
    ) -> str | None:
        """Check if there's enough disk space for transcoding.

        Args:
            plan: The transcode plan.
            ratio_hevc: Estimated output/input size ratio for HEVC/AV1 codecs.
            ratio_other: Estimated output/input size ratio for other codecs.
            buffer: Buffer multiplier for safety margin.

        Returns:
            Error message if insufficient space, None if OK.
        """
        # Estimate output size based on target codec
        input_size = plan.input_path.stat().st_size
        codec = self.policy.target_video_codec or "hevc"
        ratio = ratio_hevc if codec in ("hevc", "h265", "av1") else ratio_other
        estimated_size = int(input_size * ratio * buffer)

        # Check temp directory space if using temp
        if self.temp_directory:
            temp_path = self.temp_directory
        else:
            temp_path = plan.output_path.parent

        try:
            disk_usage = shutil.disk_usage(temp_path)
            if disk_usage.free < estimated_size:
                free_gb = disk_usage.free / (1024**3)
                need_gb = estimated_size / (1024**3)
                return (
                    f"Insufficient disk space: "
                    f"{free_gb:.1f}GB free, need ~{need_gb:.1f}GB"
                )
        except OSError as e:
            logger.warning("Could not check disk space: %s", e)

        return None

    def _backup_original(
        self, original_path: Path, output_path: Path
    ) -> tuple[bool, Path | None, str | None]:
        """Backup the original file after successful transcode.

        Args:
            original_path: Path to original file.
            output_path: Path to transcoded file.

        Returns:
            Tuple of (success, backup_path, error_message).
        """
        backup_path = original_path.with_suffix(f"{original_path.suffix}.original")

        # If backup already exists, add number
        counter = 1
        while backup_path.exists():
            backup_path = original_path.with_suffix(
                f"{original_path.suffix}.original.{counter}"
            )
            counter += 1

        try:
            original_path.rename(backup_path)
            logger.info("Backed up original: %s", backup_path)
            return True, backup_path, None
        except OSError as e:
            return False, None, str(e)

    def _cleanup_partial(self, path: Path) -> None:
        """Remove partial output file on failure.

        Args:
            path: Path to potentially incomplete output file.
        """
        if path.exists():
            try:
                path.unlink()
                logger.info("Cleaned up partial output: %s", path)
            except OSError as e:
                logger.warning("Could not clean up partial output: %s", e)

    def _get_temp_output_path(self, output_path: Path) -> Path:
        """Generate temp output path for safe transcoding.

        Args:
            output_path: Final output path.

        Returns:
            Path for temporary output file.
        """
        if self.temp_directory:
            return self.temp_directory / f".vpo_temp_{output_path.name}"
        return output_path.with_name(f".vpo_temp_{output_path.name}")

    def _atomic_replace(self, temp_path: Path, output_path: Path) -> None:
        """Atomically replace output file with temp file.

        Args:
            temp_path: Source temp file path.
            output_path: Target output file path.
        """
        temp_path.rename(output_path)
        logger.info("Moved temp file to final: %s", output_path)

    def _verify_output_integrity(self, output_path: Path) -> bool:
        """Verify output file integrity after transcode.

        Args:
            output_path: Path to output file.

        Returns:
            True if file passes integrity checks.
        """
        if not output_path.exists():
            logger.error("Output file does not exist: %s", output_path)
            return False

        if output_path.stat().st_size == 0:
            logger.error("Output file is empty: %s", output_path)
            return False

        # Could add ffprobe validation here in future
        return True

    def _run_ffmpeg_with_timeout(
        self,
        cmd: list[str],
        description: str,
        progress_callback: Callable[[FFmpegProgress], None] | None = None,
    ) -> tuple[bool, int, list[str]]:
        """Run FFmpeg command with timeout and threaded stderr reading.

        Args:
            cmd: FFmpeg command arguments.
            description: Description for logging (e.g., "pass 1", "transcode").
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (success, return_code, stderr_lines).
            success is False if timeout expired or process failed.
        """
        process = subprocess.Popen(  # nosec B603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Read stderr in a separate thread to support timeout
        stderr_output: list[str] = []
        stderr_queue: queue.Queue[str | None] = queue.Queue()

        def read_stderr() -> None:
            """Read stderr lines and put them in the queue."""
            try:
                assert process.stderr is not None
                for line in process.stderr:
                    stderr_queue.put(line)
            finally:
                stderr_queue.put(None)  # Signal end of output

        reader_thread = threading.Thread(target=read_stderr, daemon=True)
        reader_thread.start()

        # Process stderr output while waiting for completion
        timeout_expired = False
        start_time = time.monotonic()

        while True:
            # Check timeout
            if self.transcode_timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed >= self.transcode_timeout:
                    timeout_expired = True
                    break

            # Check if process finished
            if process.poll() is not None:
                break

            # Read from queue with timeout to allow checking process status
            try:
                line = stderr_queue.get(timeout=1.0)
                if line is None:
                    break  # End of stderr
                stderr_output.append(line)
                progress = parse_stderr_progress(line)
                if progress and progress_callback:
                    progress_callback(progress)
            except queue.Empty:
                continue

        # Handle timeout
        if timeout_expired:
            logger.warning(
                "%s timed out after %s seconds", description, self.transcode_timeout
            )
            process.kill()
            process.wait()  # Clean up zombie process
            return (False, -1, stderr_output)

        # Drain any remaining stderr output
        reader_thread.join(timeout=5.0)
        while True:
            try:
                line = stderr_queue.get_nowait()
                if line is None:
                    break
                stderr_output.append(line)
            except queue.Empty:
                break

        # Wait for process to finish (should already be done)
        process.wait()

        return (process.returncode == 0, process.returncode, stderr_output)

    def _execute_two_pass(
        self,
        plan: TranscodePlan,
        quality: QualitySettings,
        target_codec: str | None,
        temp_output: Path,
    ) -> TranscodeResult:
        """Execute two-pass encoding.

        Two-pass encoding runs FFmpeg twice:
        - Pass 1: Analyze video, write stats to log file
        - Pass 2: Encode video using log for accurate bitrate targeting

        Args:
            plan: The transcode plan.
            quality: Quality settings with two_pass=True.
            target_codec: Target codec override.
            temp_output: Temp output path.

        Returns:
            TranscodeResult with success status.
        """
        two_pass_ctx: TwoPassContext | None = None

        try:
            # Create passlogfile in temp directory
            passlog_dir = self.temp_directory or plan.output_path.parent
            with tempfile.NamedTemporaryFile(
                prefix="vpo_passlog_",
                suffix="",
                delete=False,
                dir=passlog_dir,
            ) as f:
                passlogfile = Path(f.name)

            two_pass_ctx = TwoPassContext(passlogfile=passlogfile)
            # === PASS 1 ===
            two_pass_ctx.current_pass = 1
            cmd1 = build_ffmpeg_command_pass1(
                plan, two_pass_ctx, self.cpu_cores, quality, target_codec
            )
            logger.info("Starting two-pass encoding pass 1: %s", plan.input_path)
            logger.debug("FFmpeg pass 1 command: %s", " ".join(cmd1))

            success1, rc1, stderr1 = self._run_ffmpeg_with_timeout(
                cmd1, "Pass 1", self.progress_callback
            )

            if not success1:
                error_msg = "".join(stderr1[-10:])
                if rc1 == -1:  # Timeout
                    logger.error("FFmpeg pass 1 timed out")
                    return TranscodeResult(
                        success=False,
                        error_message=(
                            f"Two-pass encoding pass 1 timed out "
                            f"after {self.transcode_timeout} seconds"
                        ),
                    )
                logger.error("FFmpeg pass 1 failed: %s", error_msg)
                return TranscodeResult(
                    success=False,
                    error_message=f"Two-pass encoding failed on pass 1: {error_msg}",
                )

            logger.info("Pass 1 complete, starting pass 2")

            # === PASS 2 ===
            two_pass_ctx.current_pass = 2

            # Create modified plan with temp output
            temp_plan = TranscodePlan(
                input_path=plan.input_path,
                output_path=temp_output,
                policy=plan.policy,
                video_codec=plan.video_codec,
                video_width=plan.video_width,
                video_height=plan.video_height,
                video_bitrate=plan.video_bitrate,
                duration_seconds=plan.duration_seconds,
                audio_tracks=plan.audio_tracks,
                skip_result=plan.skip_result,
                needs_video_transcode=plan.needs_video_transcode,
                needs_video_scale=plan.needs_video_scale,
                target_width=plan.target_width,
                target_height=plan.target_height,
                audio_plan=plan.audio_plan,
                is_hdr=plan.is_hdr,
                hdr_type=plan.hdr_type,
            )

            cmd2 = build_ffmpeg_command(
                temp_plan, self.cpu_cores, quality, target_codec, two_pass_ctx
            )
            logger.info("Starting two-pass encoding pass 2: %s", plan.input_path)
            logger.debug("FFmpeg pass 2 command: %s", " ".join(cmd2))

            success2, rc2, stderr2 = self._run_ffmpeg_with_timeout(
                cmd2, "Pass 2", self.progress_callback
            )

            if not success2:
                error_msg = "".join(stderr2[-10:])
                self._cleanup_partial(temp_output)
                if rc2 == -1:  # Timeout
                    logger.error("FFmpeg pass 2 timed out")
                    return TranscodeResult(
                        success=False,
                        error_message=(
                            f"Two-pass encoding pass 2 timed out "
                            f"after {self.transcode_timeout} seconds"
                        ),
                    )
                logger.error("FFmpeg pass 2 failed: %s", error_msg)
                return TranscodeResult(
                    success=False,
                    error_message=f"Two-pass encoding failed on pass 2: {error_msg}",
                )

            return TranscodeResult(success=True, output_path=temp_output)

        finally:
            # Clean up pass log files
            if two_pass_ctx is not None:
                two_pass_ctx.cleanup()

    def execute(
        self,
        plan: TranscodePlan,
        quality: QualitySettings | None = None,
        target_codec: str | None = None,
    ) -> TranscodeResult:
        """Execute a transcode plan with safety features.

        Uses write-to-temp-then-move pattern, backs up originals on success,
        and cleans up partial outputs on failure.

        Args:
            plan: The transcode plan to execute.
            quality: V6 quality settings (optional).
            target_codec: V6 target codec (optional).

        Returns:
            TranscodeResult with success status.
        """
        # V6 skip condition check
        if plan.should_skip:
            logger.info(
                "Skipping video transcode - already compliant: %s (%s)",
                plan.input_path,
                plan.skip_reason,
            )
            return TranscodeResult(success=True)

        if not plan.needs_video_transcode:
            logger.info(
                "File already compliant, no transcode needed: %s", plan.input_path
            )
            return TranscodeResult(success=True)

        # Check disk space before starting
        space_error = self._check_disk_space(plan)
        if space_error:
            logger.error("Disk space check failed: %s", space_error)
            return TranscodeResult(success=False, error_message=space_error)

        # Determine temp path (write to temp, then move to final)
        if self.temp_directory:
            temp_output = self.temp_directory / f".vpo_temp_{plan.output_path.name}"
        else:
            temp_output = plan.output_path.with_name(
                f".vpo_temp_{plan.output_path.name}"
            )

        # Check if two-pass encoding is requested
        if quality and quality.two_pass and quality.mode == QualityMode.BITRATE:
            result = self._execute_two_pass(plan, quality, target_codec, temp_output)
            if not result.success:
                return result
            # Two-pass succeeded, continue with verification and move
            try:
                temp_output.parent.mkdir(parents=True, exist_ok=True)
                plan.output_path.parent.mkdir(parents=True, exist_ok=True)

                # Verify output integrity
                if not self._verify_output_integrity(temp_output):
                    self._cleanup_partial(temp_output)
                    return TranscodeResult(
                        success=False,
                        error_message="Output file failed integrity verification",
                    )

                # Move temp to final destination
                try:
                    shutil.move(str(temp_output), str(plan.output_path))
                except OSError as e:
                    self._cleanup_partial(temp_output)
                    return TranscodeResult(
                        success=False,
                        error_message=f"Failed to move temp to final: {e}",
                    )

                # Backup original if requested
                backup_path = None
                if self.backup_original and plan.input_path != plan.output_path:
                    success, backup_path, backup_error = self._backup_original(
                        plan.input_path, plan.output_path
                    )
                    if not success:
                        logger.warning("Could not backup original: %s", backup_error)

                logger.info("Two-pass transcode completed: %s", plan.output_path)
                return TranscodeResult(
                    success=True,
                    output_path=plan.output_path,
                    backup_path=backup_path,
                )

            except Exception as e:
                logger.exception("Two-pass transcode failed: %s", e)
                self._cleanup_partial(temp_output)
                return TranscodeResult(
                    success=False,
                    error_message=str(e),
                )

        # Create a modified plan with temp output
        temp_plan = TranscodePlan(
            input_path=plan.input_path,
            output_path=temp_output,
            policy=plan.policy,
            video_codec=plan.video_codec,
            video_width=plan.video_width,
            video_height=plan.video_height,
            video_bitrate=plan.video_bitrate,
            duration_seconds=plan.duration_seconds,
            audio_tracks=plan.audio_tracks,
            skip_result=plan.skip_result,
            needs_video_transcode=plan.needs_video_transcode,
            needs_video_scale=plan.needs_video_scale,
            target_width=plan.target_width,
            target_height=plan.target_height,
            audio_plan=plan.audio_plan,
            is_hdr=plan.is_hdr,
            hdr_type=plan.hdr_type,
        )

        cmd = build_ffmpeg_command(temp_plan, self.cpu_cores)
        logger.info("Executing transcode: %s -> %s", plan.input_path, plan.output_path)
        logger.debug("FFmpeg command: %s", " ".join(cmd))

        try:
            # Ensure output directory exists
            temp_output.parent.mkdir(parents=True, exist_ok=True)
            plan.output_path.parent.mkdir(parents=True, exist_ok=True)

            # Run FFmpeg with progress monitoring and timeout
            success, rc, stderr_output = self._run_ffmpeg_with_timeout(
                cmd, "Transcode", self.progress_callback
            )

            if not success:
                self._cleanup_partial(temp_output)
                if rc == -1:  # Timeout
                    timeout_secs = self.transcode_timeout
                    msg = f"Transcode timed out after {timeout_secs} seconds"
                    return TranscodeResult(success=False, error_message=msg)
                error_msg = "".join(stderr_output[-10:])  # Last 10 lines
                logger.error("FFmpeg failed: %s", error_msg)
                return TranscodeResult(
                    success=False,
                    error_message=f"FFmpeg exited with code {rc}: {error_msg}",
                )

            # Verify temp output exists
            if not temp_output.exists():
                return TranscodeResult(
                    success=False,
                    error_message="Output file was not created",
                )

            # Move temp to final destination
            try:
                shutil.move(str(temp_output), str(plan.output_path))
            except OSError as e:
                self._cleanup_partial(temp_output)
                return TranscodeResult(
                    success=False,
                    error_message=f"Failed to move temp to final: {e}",
                )

            # Backup original if requested
            backup_path = None
            if self.backup_original and plan.input_path != plan.output_path:
                success, backup_path, backup_error = self._backup_original(
                    plan.input_path, plan.output_path
                )
                if not success:
                    logger.warning("Could not backup original: %s", backup_error)
                    # Not a fatal error - transcode succeeded

            logger.info("Transcode completed: %s", plan.output_path)
            return TranscodeResult(
                success=True,
                output_path=plan.output_path,
                backup_path=backup_path,
            )

        except Exception as e:
            logger.exception("Transcode failed: %s", e)
            self._cleanup_partial(temp_output)
            return TranscodeResult(
                success=False,
                error_message=str(e),
            )

    def dry_run(self, plan: TranscodePlan) -> dict:
        """Generate dry-run output showing what would be done.

        Args:
            plan: The transcode plan.

        Returns:
            Dictionary with planned operations.
        """
        # V6 skip condition check for dry-run
        if plan.should_skip:
            return {
                "input": str(plan.input_path),
                "output": str(plan.output_path),
                "needs_transcode": False,
                "skipped": True,
                "skip_reason": (
                    f"Skipping video transcode - already compliant: {plan.skip_reason}"
                ),
                "video_operations": [],
                "audio_operations": [],
                "audio_descriptions": [],
                "command": None,
            }

        operations = []

        if plan.needs_video_transcode:
            op = {
                "type": "video_transcode",
                "from_codec": plan.video_codec,
                "to_codec": self.policy.target_video_codec or "hevc",
            }
            if self.policy.target_crf is not None:
                op["crf"] = self.policy.target_crf
            if self.policy.target_bitrate:
                op["bitrate"] = self.policy.target_bitrate
            operations.append(op)

        if plan.needs_video_scale:
            operations.append(
                {
                    "type": "video_scale",
                    "from_resolution": f"{plan.video_width}x{plan.video_height}",
                    "to_resolution": f"{plan.target_width}x{plan.target_height}",
                }
            )

        # Add audio operations
        audio_operations = []
        if plan.audio_plan:
            for track in plan.audio_plan.tracks:
                audio_op = {
                    "stream_index": track.stream_index,
                    "codec": track.codec,
                    "language": track.language,
                    "channels": track.channels,
                    "action": track.action.value,
                }
                if track.action == AudioAction.TRANSCODE:
                    audio_op["target_codec"] = track.target_codec
                    audio_op["target_bitrate"] = track.target_bitrate
                audio_op["reason"] = track.reason
                audio_operations.append(audio_op)

            if plan.audio_plan.downmix_track:
                downmix = plan.audio_plan.downmix_track
                audio_operations.append(
                    {
                        "stream_index": "new",
                        "action": "downmix",
                        "channel_layout": downmix.channel_layout,
                        "target_codec": downmix.target_codec,
                        "target_bitrate": downmix.target_bitrate,
                        "reason": downmix.reason,
                    }
                )

        # Determine if any work is needed
        needs_work = plan.needs_any_transcode

        return {
            "input": str(plan.input_path),
            "output": str(plan.output_path),
            "needs_transcode": needs_work,
            "video_operations": operations,
            "audio_operations": audio_operations,
            "audio_descriptions": (
                describe_audio_plan(plan.audio_plan) if plan.audio_plan else []
            ),
            "command": (
                build_ffmpeg_command(plan, self.cpu_cores) if needs_work else None
            ),
        }
