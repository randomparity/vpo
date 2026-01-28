"""FFmpeg command building for transcoding.

This module provides functions for constructing FFmpeg command-line arguments
for video transcoding, including quality settings, scaling, and stream mapping.
"""

from __future__ import annotations

import logging
import platform

from vpo.executor.interface import require_tool
from vpo.policy.transcode import AudioAction, AudioPlan
from vpo.policy.types import (
    QualityMode,
    QualitySettings,
    TranscodePolicyConfig,
    get_default_crf,
    parse_bitrate,
)
from vpo.policy.video_analysis import build_hdr_preservation_args
from vpo.tools.encoders import get_software_encoder

from .audio import build_audio_args
from .types import TranscodePlan, TwoPassContext

logger = logging.getLogger(__name__)

# Local alias for internal use
_get_encoder = get_software_encoder


def build_quality_args(
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
    scale_algorithm: str | None = None,
    ffmpeg_args: tuple[str, ...] | None = None,
) -> list[str]:
    """Build FFmpeg command for transcoding.

    Args:
        plan: Transcode plan with input/output paths and settings.
        cpu_cores: Number of CPU cores to use (None = auto).
        quality: V6 quality settings (overrides policy settings if provided).
        target_codec: V6 target codec (overrides policy codec if provided).
        two_pass_ctx: Context for two-pass encoding (if active).
        scale_algorithm: Scaling algorithm (e.g., 'lanczos', 'bicubic').
        ffmpeg_args: Custom FFmpeg arguments to insert before output.

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
        cmd.extend(build_quality_args(quality, policy, codec, encoder, two_pass_ctx))

        # Scaling
        if plan.needs_video_scale and plan.target_width and plan.target_height:
            scale_filter = f"scale={plan.target_width}:{plan.target_height}"
            if scale_algorithm:
                scale_filter += f":flags={scale_algorithm}"
            cmd.extend(["-vf", scale_filter])

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
        cmd.extend(build_audio_args(plan.audio_plan, plan.policy))
    else:
        # No audio plan or no changes - copy all audio
        cmd.extend(["-c:a", "copy"])

    # Subtitle - copy all subtitles
    cmd.extend(["-c:s", "copy"])

    # Thread control
    if cpu_cores:
        cmd.extend(["-threads", str(cpu_cores)])

    # Custom FFmpeg arguments (inserted before stats_period and output)
    if ffmpeg_args:
        cmd.extend(ffmpeg_args)

    # Progress output to stderr
    cmd.extend(["-stats_period", "1"])

    # Output file
    cmd.append(str(plan.output_path))

    return cmd


def build_ffmpeg_command_pass1(
    plan: TranscodePlan,
    two_pass_ctx: TwoPassContext,
    cpu_cores: int | None = None,
    quality: QualitySettings | None = None,
    target_codec: str | None = None,
    scale_algorithm: str | None = None,
    ffmpeg_args: tuple[str, ...] | None = None,
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
        scale_algorithm: Scaling algorithm (e.g., 'lanczos', 'bicubic').
        ffmpeg_args: Custom FFmpeg arguments to insert before output.

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
    # Note: build_quality_args() already adds preset for x264/x265 encoders
    two_pass_ctx.current_pass = 1
    cmd.extend(build_quality_args(quality, policy, codec, encoder, two_pass_ctx))

    # Scaling (same as pass 2)
    if plan.needs_video_scale and plan.target_width and plan.target_height:
        scale_filter = f"scale={plan.target_width}:{plan.target_height}"
        if scale_algorithm:
            scale_filter += f":flags={scale_algorithm}"
        cmd.extend(["-vf", scale_filter])

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

    # Custom FFmpeg arguments (inserted before stats_period and output)
    if ffmpeg_args:
        cmd.extend(ffmpeg_args)

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
    plan: TranscodePlan,
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
