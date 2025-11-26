"""Transcode executor for video/audio transcoding via FFmpeg."""

import logging
import subprocess  # nosec B404 - subprocess is required for FFmpeg invocation
from collections.abc import Callable
from dataclasses import dataclass
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

        # Check if pattern has aliases we should expand
        aliases = CODEC_ALIASES.get(pattern_lower, ())
        if any(alias in current_lower for alias in aliases):
            return True

        # Check if current codec has aliases
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
) -> list[str]:
    """Build FFmpeg quality-related arguments.

    Supports V6 QualitySettings (takes precedence) and falls back to
    TranscodePolicyConfig for backward compatibility.

    Args:
        quality: V6 quality settings (optional).
        policy: V1-5 transcode policy config.
        codec: Target video codec name.
        encoder: FFmpeg encoder name.

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
                if quality.two_pass:
                    # Note: Two-pass requires running ffmpeg twice
                    # This will be handled by the executor, not here
                    pass

        elif quality.mode == QualityMode.CONSTRAINED_QUALITY:
            # Constrained quality: CRF with max bitrate cap
            crf = quality.crf if quality.crf is not None else get_default_crf(codec)
            args.extend(["-crf", str(crf)])
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
) -> list[str]:
    """Build FFmpeg command for transcoding.

    Args:
        plan: Transcode plan with input/output paths and settings.
        cpu_cores: Number of CPU cores to use (None = auto).
        quality: V6 quality settings (overrides policy settings if provided).
        target_codec: V6 target codec (overrides policy codec if provided).

    Returns:
        List of command arguments.
    """
    ffmpeg_path = require_tool("ffmpeg")
    cmd = [str(ffmpeg_path), "-y", "-hide_banner"]

    # Input file
    cmd.extend(["-i", str(plan.input_path)])

    # Video settings
    if plan.needs_video_transcode:
        policy = plan.policy

        # Determine codec (V6 target_codec takes precedence)
        codec = target_codec or policy.target_video_codec or "hevc"
        encoder = _get_encoder(codec)
        cmd.extend(["-c:v", encoder])

        # Build quality arguments (V6 quality takes precedence over policy)
        cmd.extend(_build_quality_args(quality, policy, codec, encoder))

        # Scaling
        if plan.needs_video_scale and plan.target_width and plan.target_height:
            cmd.extend(
                [
                    "-vf",
                    f"scale={plan.target_width}:{plan.target_height}",
                ]
            )
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


def _build_audio_args(
    audio_plan: AudioPlan, policy: TranscodePolicyConfig
) -> list[str]:
    """Build FFmpeg arguments for audio track handling.

    Args:
        audio_plan: The audio handling plan.
        policy: Transcode policy configuration.

    Returns:
        List of FFmpeg arguments for audio.
    """
    args = []

    # Process each audio track
    for track in audio_plan.tracks:
        if track.action == AudioAction.COPY:
            # Stream copy this track
            args.extend([f"-c:a:{track.stream_index}", "copy"])
        elif track.action == AudioAction.TRANSCODE:
            # Transcode this track
            target = track.target_codec or policy.audio_transcode_to
            encoder = _get_audio_encoder(target)
            args.extend([f"-c:a:{track.stream_index}", encoder])

            # Set bitrate for the track
            bitrate = track.target_bitrate or policy.audio_transcode_bitrate
            if bitrate:
                args.extend([f"-b:a:{track.stream_index}", bitrate])
        elif track.action == AudioAction.REMOVE:
            # Remove tracks are handled by not mapping them
            # This requires a different approach - use -map
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
    if downmix_track.channel_layout == "stereo":
        # Downmix to stereo using Dolby Pro Logic II encoding
        return (
            "[0:a:0]aresample=matrix_encoding=dplii,"
            "pan=stereo|FL=FC+0.30*FL+0.30*BL|FR=FC+0.30*FR+0.30*BR[downmix]"
        )
    elif downmix_track.channel_layout == "5.1":
        # Downmix to 5.1 (usually from 7.1)
        return (
            "[0:a:0]pan=5.1|FL=FL|FR=FR|FC=FC|LFE=LFE|"
            "BL=0.5*BL+0.5*SL|BR=0.5*BR+0.5*SR[downmix]"
        )
    return None


def _get_encoder(codec: str) -> str:
    """Get FFmpeg encoder name for a codec."""
    encoders = {
        "hevc": "libx265",
        "h265": "libx265",
        "h264": "libx264",
        "vp9": "libvpx-vp9",
        "av1": "libaom-av1",
    }
    return encoders.get(codec.lower(), "libx265")


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
        """
        self.policy = policy
        self.skip_if = skip_if
        self.audio_config = audio_config
        self.cpu_cores = cpu_cores
        self.progress_callback = progress_callback
        self.temp_directory = temp_directory
        self.backup_original = backup_original

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

        Returns:
            TranscodePlan with computed actions.
        """
        # Evaluate V6 skip conditions first
        skip_result = should_skip_transcode(
            skip_if=self.skip_if,
            video_codec=video_codec,
            video_width=video_width,
            video_height=video_height,
            video_bitrate=video_bitrate,
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
                video_bitrate=video_bitrate,
                duration_seconds=duration_seconds,
                audio_tracks=audio_tracks,
                skip_result=skip_result,
                needs_video_transcode=False,
                needs_video_scale=False,
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
            video_bitrate=video_bitrate,
            duration_seconds=duration_seconds,
            audio_tracks=audio_tracks,
            skip_result=skip_result,
            needs_video_transcode=needs_transcode,
            needs_video_scale=needs_scale,
            target_width=target_width,
            target_height=target_height,
            audio_plan=audio_plan,
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
        import shutil

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

    def execute(self, plan: TranscodePlan) -> TranscodeResult:
        """Execute a transcode plan with safety features.

        Uses write-to-temp-then-move pattern, backs up originals on success,
        and cleans up partial outputs on failure.

        Args:
            plan: The transcode plan to execute.

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
        )

        cmd = build_ffmpeg_command(temp_plan, self.cpu_cores)
        logger.info("Executing transcode: %s -> %s", plan.input_path, plan.output_path)
        logger.debug("FFmpeg command: %s", " ".join(cmd))

        try:
            # Ensure output directory exists
            temp_output.parent.mkdir(parents=True, exist_ok=True)
            plan.output_path.parent.mkdir(parents=True, exist_ok=True)

            # Run FFmpeg with progress monitoring (cmd built from trusted FFmpeg path)
            process = subprocess.Popen(  # nosec B603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Read stderr for progress
            stderr_output = []
            for line in process.stderr:
                stderr_output.append(line)
                progress = parse_stderr_progress(line)
                if progress and self.progress_callback:
                    self.progress_callback(progress)

            # Wait for completion
            process.wait()

            if process.returncode != 0:
                error_msg = "".join(stderr_output[-10:])  # Last 10 lines
                logger.error("FFmpeg failed: %s", error_msg)
                self._cleanup_partial(temp_output)
                msg = f"FFmpeg exited with code {process.returncode}: {error_msg}"
                return TranscodeResult(success=False, error_message=msg)

            # Verify temp output exists
            if not temp_output.exists():
                return TranscodeResult(
                    success=False,
                    error_message="Output file was not created",
                )

            # Move temp to final destination
            import shutil

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
