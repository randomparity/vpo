"""Transcode executor for video/audio transcoding via FFmpeg."""

import logging
import subprocess
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
    TranscodePolicyConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class TranscodeResult:
    """Result of a transcode operation."""

    success: bool
    output_path: Path | None = None
    error_message: str | None = None
    backup_path: Path | None = None


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
    duration_seconds: float | None = None

    # Audio tracks info
    audio_tracks: list[TrackInfo] | None = None

    # Computed actions
    needs_video_transcode: bool = False
    needs_video_scale: bool = False
    target_width: int | None = None
    target_height: int | None = None


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


def build_ffmpeg_command(
    plan: TranscodePlan,
    cpu_cores: int | None = None,
) -> list[str]:
    """Build FFmpeg command for transcoding.

    Args:
        plan: Transcode plan with input/output paths and settings.
        cpu_cores: Number of CPU cores to use (None = auto).

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

        # Video codec
        codec = policy.target_video_codec or "hevc"
        encoder = _get_encoder(codec)
        cmd.extend(["-c:v", encoder])

        # CRF or bitrate
        if policy.target_crf is not None:
            cmd.extend(["-crf", str(policy.target_crf)])
        elif policy.target_bitrate:
            cmd.extend(["-b:v", policy.target_bitrate])
        else:
            # Default CRF for good quality
            cmd.extend(["-crf", "23"])

        # Scaling
        if plan.needs_video_scale and plan.target_width and plan.target_height:
            cmd.extend(
                [
                    "-vf",
                    f"scale={plan.target_width}:{plan.target_height}",
                ]
            )

        # Preset for speed/quality balance
        if encoder in ("libx264", "libx265"):
            cmd.extend(["-preset", "medium"])
    else:
        # Copy video stream
        cmd.extend(["-c:v", "copy"])

    # Audio - for Phase 3 (US1), just copy all audio
    # Audio transcoding is handled in Phase 5 (US3)
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
        cpu_cores: int | None = None,
        progress_callback: Callable[[FFmpegProgress], None] | None = None,
    ) -> None:
        """Initialize the transcode executor.

        Args:
            policy: Transcode policy configuration.
            cpu_cores: Number of CPU cores to use.
            progress_callback: Optional callback for progress updates.
        """
        self.policy = policy
        self.cpu_cores = cpu_cores
        self.progress_callback = progress_callback

    def create_plan(
        self,
        input_path: Path,
        output_path: Path,
        video_codec: str | None = None,
        video_width: int | None = None,
        video_height: int | None = None,
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
            duration_seconds: File duration in seconds.
            audio_tracks: List of audio track info.

        Returns:
            TranscodePlan with computed actions.
        """
        needs_transcode, needs_scale, target_width, target_height = (
            should_transcode_video(
                self.policy,
                video_codec,
                video_width,
                video_height,
            )
        )

        return TranscodePlan(
            input_path=input_path,
            output_path=output_path,
            policy=self.policy,
            video_codec=video_codec,
            video_width=video_width,
            video_height=video_height,
            duration_seconds=duration_seconds,
            audio_tracks=audio_tracks,
            needs_video_transcode=needs_transcode,
            needs_video_scale=needs_scale,
            target_width=target_width,
            target_height=target_height,
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

    def execute(self, plan: TranscodePlan) -> TranscodeResult:
        """Execute a transcode plan.

        Args:
            plan: The transcode plan to execute.

        Returns:
            TranscodeResult with success status.
        """
        if not plan.needs_video_transcode:
            logger.info(
                "File already compliant, no transcode needed: %s", plan.input_path
            )
            return TranscodeResult(success=True)

        cmd = build_ffmpeg_command(plan, self.cpu_cores)
        logger.info("Executing transcode: %s -> %s", plan.input_path, plan.output_path)
        logger.debug("FFmpeg command: %s", " ".join(cmd))

        try:
            # Ensure output directory exists
            plan.output_path.parent.mkdir(parents=True, exist_ok=True)

            # Run FFmpeg with progress monitoring
            process = subprocess.Popen(
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
                msg = f"FFmpeg exited with code {process.returncode}: {error_msg}"
                return TranscodeResult(success=False, error_message=msg)

            # Verify output exists
            if not plan.output_path.exists():
                return TranscodeResult(
                    success=False,
                    error_message="Output file was not created",
                )

            logger.info("Transcode completed: %s", plan.output_path)
            return TranscodeResult(
                success=True,
                output_path=plan.output_path,
            )

        except Exception as e:
            logger.exception("Transcode failed: %s", e)
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

        return {
            "input": str(plan.input_path),
            "output": str(plan.output_path),
            "needs_transcode": plan.needs_video_transcode,
            "operations": operations,
            "command": build_ffmpeg_command(plan, self.cpu_cores)
            if operations
            else None,
        }
