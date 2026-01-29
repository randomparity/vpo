"""Transcode executor for video/audio transcoding via FFmpeg.

This module implements the TranscodeExecutor class for video transcoding
operations, including safety features like disk space checks, backups,
and atomic file replacement.
"""

import logging
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from vpo.db import TrackInfo
from vpo.executor.ffmpeg_base import FFmpegExecutorBase
from vpo.policy.transcode import (
    AudioAction,
    create_audio_plan,
    create_audio_plan_v6,
    describe_audio_plan,
    evaluate_skip_condition,
)
from vpo.policy.types import (
    AudioTranscodeConfig,
    HardwareAccelConfig,
    HardwareAccelMode,
    QualityMode,
    QualitySettings,
    SkipCondition,
    TranscodePolicyConfig,
)
from vpo.policy.video_analysis import (
    HDRType,
    detect_hdr_type,
    detect_missing_bitrate,
    detect_vfr_content,
    select_primary_video_stream,
)
from vpo.tools.encoders import detect_hw_encoder_error
from vpo.tools.ffmpeg_progress import FFmpegProgress

from .command import build_ffmpeg_command, build_ffmpeg_command_pass1
from .decisions import should_transcode_video
from .types import TranscodePlan, TranscodeResult, TwoPassContext

logger = logging.getLogger(__name__)

# Hardware encoder suffix patterns (Issue #264)
HARDWARE_ENCODER_PATTERNS = (
    "_nvenc",  # NVIDIA NVENC
    "_vaapi",  # VA-API (Intel/AMD on Linux)
    "_qsv",  # Intel Quick Sync
    "_amf",  # AMD AMF
    "_videotoolbox",  # Apple VideoToolbox
)

# Known software encoders (explicit library encoders and codec defaults)
SOFTWARE_ENCODERS = frozenset(
    {
        "libx264",
        "libx265",
        "libvpx",
        "libvpx-vp9",
        "libaom-av1",
        "libsvtav1",
        "librav1e",
        "h264",
        "hevc",
        "h265",
        "vp8",
        "vp9",
        "av1",
    }
)


def detect_encoder_type(cmd: list[str]) -> str:
    """Detect whether FFmpeg command uses hardware or software encoding.

    Args:
        cmd: FFmpeg command arguments.

    Returns:
        'hardware' if a hardware encoder is detected,
        'software' if a software encoder is detected,
        'unknown' if encoder cannot be determined.
    """
    video_codec_args = {"-c:v", "-codec:v", "-vcodec"}

    for i, arg in enumerate(cmd):
        if arg in video_codec_args and i + 1 < len(cmd):
            encoder = cmd[i + 1]

            if encoder == "copy":
                return "unknown"

            if any(pattern in encoder for pattern in HARDWARE_ENCODER_PATTERNS):
                return "hardware"

            if encoder in SOFTWARE_ENCODERS:
                return "software"

    return "unknown"


# Patterns that indicate hardware encoder initialization failed
HARDWARE_FALLBACK_PATTERNS = (
    "Failed to initialise VAAPI",
    "No device available",
    "Cannot load nvenc",
    "hwaccel initialisation returned error",
    "Failed to create VAAPI",
    "NVENC not available",
    "No VAAPI support",
    "Cannot open display",
    "Failed to open encoder",  # Generic but often HW-related
)


def check_hardware_fallback(
    cmd: list[str], stderr_lines: list[str]
) -> tuple[str, bool]:
    """Detect if hardware encoder fell back to software.

    Args:
        cmd: FFmpeg command arguments used.
        stderr_lines: Stderr output from FFmpeg.

    Returns:
        Tuple of (encoder_type, was_fallback).
        encoder_type is 'hardware', 'software', or 'unknown'.
        was_fallback is True if hardware was requested but failed.
    """
    requested_type = detect_encoder_type(cmd)

    # If we didn't request hardware, no fallback possible
    if requested_type != "hardware":
        return requested_type, False

    # Check stderr for fallback indicators
    stderr_text = "\n".join(stderr_lines)
    for pattern in HARDWARE_FALLBACK_PATTERNS:
        if pattern.lower() in stderr_text.lower():
            logger.warning(
                "Hardware encoder fallback detected: %s",
                pattern,
                extra={"pattern": pattern, "requested_encoder": requested_type},
            )
            return "software", True

    return requested_type, False


class TranscodeExecutor(FFmpegExecutorBase):
    """Executor for video transcoding operations."""

    def __init__(
        self,
        policy: TranscodePolicyConfig,
        skip_if: SkipCondition | None = None,
        audio_config: AudioTranscodeConfig | None = None,
        hardware_acceleration: HardwareAccelConfig | None = None,
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
            hardware_acceleration: V6 hardware acceleration config.
            cpu_cores: Number of CPU cores to use.
            progress_callback: Optional callback for progress updates.
            temp_directory: Directory for temp files (None = same as output).
            backup_original: Whether to backup original after success.
            transcode_timeout: Maximum time in seconds for transcode (None = no limit).
        """
        # Note: TranscodeExecutor uses transcode_timeout, not base timeout
        super().__init__(timeout=None)
        self.policy = policy
        self.skip_if = skip_if
        self.audio_config = audio_config
        self.hardware_acceleration = hardware_acceleration
        self.cpu_cores = cpu_cores
        self.progress_callback = progress_callback
        self.temp_directory = temp_directory
        self.backup_original = backup_original
        self.transcode_timeout = transcode_timeout

    def _should_retry_with_software(
        self, cmd: list[str], stderr_lines: list[str]
    ) -> bool:
        """Check if we should retry with software encoding after hardware failure.

        Args:
            cmd: FFmpeg command arguments that were used.
            stderr_lines: Stderr output from FFmpeg.

        Returns:
            True if hardware encoder failed and fallback_to_cpu is enabled.
        """
        # Only check if hardware acceleration is configured with fallback enabled
        if not self.hardware_acceleration:
            return False
        if not self.hardware_acceleration.fallback_to_cpu:
            return False
        if self.hardware_acceleration.enabled == HardwareAccelMode.NONE:
            return False

        # Check if the encoder used was hardware
        encoder_type = detect_encoder_type(cmd)
        if encoder_type != "hardware":
            return False

        # Check stderr for hardware encoder error patterns
        stderr_text = "\n".join(stderr_lines)
        return detect_hw_encoder_error(stderr_text)

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
        skip_result = evaluate_skip_condition(
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
                extra={
                    "input_path": str(input_path),
                    "skip_reason": skip_result.reason,
                    "video_codec": video_codec,
                    "resolution": (
                        f"{video_width}x{video_height}" if video_width else None
                    ),
                    "bitrate": effective_bitrate,
                },
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

    def _check_disk_space_for_plan(self, plan: TranscodePlan) -> str | None:
        """Check if there's enough disk space for transcoding.

        Uses codec-aware disk space estimation. Checks the temp directory
        if configured, otherwise checks the output file's parent directory.

        Args:
            plan: The transcode plan.

        Returns:
            Error message if insufficient space, None if OK.
        """
        target_codec = self.policy.target_video_codec or "hevc"

        # Determine which directory to check for space
        if self.temp_directory:
            check_path = self.temp_directory
        else:
            check_path = plan.output_path.parent

        # Estimate output size based on target codec
        try:
            input_size = plan.input_path.stat().st_size
        except OSError as e:
            logger.warning("Could not stat input file: %s", e)
            return None

        codec = target_codec.lower()
        if codec in ("hevc", "h265", "av1"):
            ratio = 0.5
        else:
            ratio = 0.8

        estimated_size = int(input_size * ratio * 1.2)  # 1.2x buffer

        try:
            disk_usage = shutil.disk_usage(check_path)
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

        Uses the base class temp file cleanup method.

        Args:
            path: Path to potentially incomplete output file.
        """
        self.cleanup_temp(path)
        if not path.exists():
            logger.info("Cleaned up partial output: %s", path)

    def _get_temp_output_path(self, output_path: Path) -> Path:
        """Generate temp output path for safe transcoding.

        Uses the base class temp file generation method.

        Args:
            output_path: Final output path.

        Returns:
            Path for temporary output file.
        """
        return self.create_temp_output(output_path, self.temp_directory)

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

        Uses the base class output validation method.

        Args:
            output_path: Path to output file.

        Returns:
            True if file passes integrity checks.
        """
        is_valid, error_msg = self.validate_output(output_path)
        if not is_valid:
            logger.error("Output validation failed: %s", error_msg)
            return False
        return True

    def _execute_two_pass(
        self,
        plan: TranscodePlan,
        quality: QualitySettings,
        target_codec: str | None,
        temp_output: Path,
        scale_algorithm: str | None = None,
        ffmpeg_args: tuple[str, ...] | None = None,
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
            scale_algorithm: Scaling algorithm (e.g., 'lanczos', 'bicubic').
            ffmpeg_args: Custom FFmpeg arguments to insert before output.

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
                plan,
                two_pass_ctx,
                self.cpu_cores,
                quality,
                target_codec,
                scale_algorithm,
                ffmpeg_args,
                self.hardware_acceleration,
            )
            logger.info(
                "Starting two-pass encoding pass 1: %s",
                plan.input_path,
                extra={
                    "input_path": str(plan.input_path),
                    "command": " ".join(cmd1),
                    "pass": 1,
                },
            )

            pass1_start = time.monotonic()
            success1, rc1, stderr1, _ = self._run_ffmpeg_with_timeout(
                cmd1,
                "Pass 1",
                timeout=self.transcode_timeout,
                progress_callback=self.progress_callback,
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

            pass1_elapsed = time.monotonic() - pass1_start
            logger.info(
                "Pass 1 complete (%.1fs), starting pass 2",
                pass1_elapsed,
                extra={"pass": 1, "elapsed_seconds": round(pass1_elapsed, 3)},
            )

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
                temp_plan,
                self.cpu_cores,
                quality,
                target_codec,
                two_pass_ctx,
                scale_algorithm,
                ffmpeg_args,
                self.hardware_acceleration,
            )
            logger.info(
                "Starting two-pass encoding pass 2: %s",
                plan.input_path,
                extra={
                    "input_path": str(plan.input_path),
                    "command": " ".join(cmd2),
                    "pass": 2,
                },
            )

            pass2_start = time.monotonic()
            success2, rc2, stderr2, metrics2 = self._run_ffmpeg_with_timeout(
                cmd2,
                "Pass 2",
                timeout=self.transcode_timeout,
                progress_callback=self.progress_callback,
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

            pass2_elapsed = time.monotonic() - pass2_start
            total_elapsed = pass1_elapsed + pass2_elapsed
            logger.info(
                "Pass 2 complete (%.1fs, total: %.1fs)",
                pass2_elapsed,
                total_elapsed,
                extra={
                    "pass": 2,
                    "pass2_seconds": round(pass2_elapsed, 3),
                    "total_seconds": round(total_elapsed, 3),
                },
            )

            return TranscodeResult(
                success=True,
                output_path=temp_output,
                encoding_fps=metrics2.avg_fps if metrics2 else None,
                encoding_bitrate_kbps=metrics2.avg_bitrate_kbps if metrics2 else None,
                total_frames=metrics2.total_frames if metrics2 else None,
                encoder_type=detect_encoder_type(cmd2),
            )

        finally:
            # Clean up pass log files
            if two_pass_ctx is not None:
                two_pass_ctx.cleanup()

    def execute(
        self,
        plan: TranscodePlan,
        quality: QualitySettings | None = None,
        target_codec: str | None = None,
        scale_algorithm: str | None = None,
        ffmpeg_args: tuple[str, ...] | None = None,
    ) -> TranscodeResult:
        """Execute a transcode plan with safety features.

        Uses write-to-temp-then-move pattern, backs up originals on success,
        and cleans up partial outputs on failure.

        Args:
            plan: The transcode plan to execute.
            quality: V6 quality settings (optional).
            target_codec: V6 target codec (optional).
            scale_algorithm: Scaling algorithm (e.g., 'lanczos', 'bicubic').
            ffmpeg_args: Custom FFmpeg arguments to insert before output.

        Returns:
            TranscodeResult with success status.
        """
        # V6 skip condition check
        if plan.should_skip:
            logger.info(
                "Skipping video transcode - already compliant: %s (%s)",
                plan.input_path,
                plan.skip_reason,
                extra={
                    "input_path": str(plan.input_path),
                    "skip_reason": plan.skip_reason,
                    "video_codec": plan.video_codec,
                    "resolution": (
                        f"{plan.video_width}x{plan.video_height}"
                        if plan.video_width
                        else None
                    ),
                    "bitrate": plan.video_bitrate,
                },
            )
            return TranscodeResult(success=True)

        if not plan.needs_video_transcode:
            logger.info(
                "File already compliant, no transcode needed: %s",
                plan.input_path,
                extra={
                    "input_path": str(plan.input_path),
                    "video_codec": plan.video_codec,
                },
            )
            return TranscodeResult(success=True)

        # Check disk space before starting
        space_error = self._check_disk_space_for_plan(plan)
        if space_error:
            logger.error("Disk space check failed: %s", space_error)
            return TranscodeResult(success=False, error_message=space_error)

        # Start timing for elapsed calculation
        start_time = time.monotonic()

        # Pre-execution summary with structured context
        effective_codec = target_codec or self.policy.target_video_codec or "hevc"
        logger.info(
            "Starting transcode: %s",
            plan.input_path.name,
            extra={
                "input_path": str(plan.input_path),
                "output_path": str(plan.output_path),
                "input_codec": plan.video_codec,
                "target_codec": effective_codec,
                "input_resolution": (
                    f"{plan.video_width}x{plan.video_height}"
                    if plan.video_width
                    else None
                ),
                "needs_scale": plan.needs_video_scale,
                "duration_seconds": plan.duration_seconds,
                "is_hdr": plan.is_hdr,
            },
        )

        # Determine temp path (write to temp, then move to final)
        if self.temp_directory:
            temp_output = self.temp_directory / f".vpo_temp_{plan.output_path.name}"
        else:
            temp_output = plan.output_path.with_name(
                f".vpo_temp_{plan.output_path.name}"
            )

        # Check if two-pass encoding is requested
        if quality and quality.two_pass and quality.mode == QualityMode.BITRATE:
            result = self._execute_two_pass(
                plan, quality, target_codec, temp_output, scale_algorithm, ffmpeg_args
            )
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

                elapsed = time.monotonic() - start_time
                logger.info(
                    "Two-pass transcode completed: %s",
                    plan.output_path.name,
                    extra={
                        "output_path": str(plan.output_path),
                        "elapsed_seconds": round(elapsed, 3),
                    },
                )
                return TranscodeResult(
                    success=True,
                    output_path=plan.output_path,
                    backup_path=backup_path,
                    encoding_fps=result.encoding_fps,
                    encoding_bitrate_kbps=result.encoding_bitrate_kbps,
                    total_frames=result.total_frames,
                    encoder_type=result.encoder_type,
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

        cmd = build_ffmpeg_command(
            temp_plan,
            self.cpu_cores,
            quality=quality,
            target_codec=target_codec,
            scale_algorithm=scale_algorithm,
            ffmpeg_args=ffmpeg_args,
            hardware_acceleration=self.hardware_acceleration,
        )
        logger.info(
            "Executing FFmpeg: %s",
            " ".join(cmd),
            extra={"input_path": str(plan.input_path), "command_type": "transcode"},
        )

        try:
            # Ensure output directory exists
            temp_output.parent.mkdir(parents=True, exist_ok=True)
            plan.output_path.parent.mkdir(parents=True, exist_ok=True)

            # Run FFmpeg with progress monitoring and timeout
            success, rc, stderr_output, metrics = self._run_ffmpeg_with_timeout(
                cmd,
                "Transcode",
                timeout=self.transcode_timeout,
                progress_callback=self.progress_callback,
            )

            if not success:
                self._cleanup_partial(temp_output)
                if rc == -1:  # Timeout
                    timeout_secs = self.transcode_timeout
                    msg = f"Transcode timed out after {timeout_secs} seconds"
                    return TranscodeResult(success=False, error_message=msg)

                # Check if we should retry with software encoding
                if self._should_retry_with_software(cmd, stderr_output):
                    logger.warning(
                        "Hardware encoder failed, retrying with software encoder: %s",
                        plan.input_path.name,
                    )
                    # Retry with hardware acceleration disabled
                    original_hw_accel = self.hardware_acceleration
                    try:
                        self.hardware_acceleration = HardwareAccelConfig(
                            enabled=HardwareAccelMode.NONE,
                            fallback_to_cpu=False,
                        )
                        # Recursive call with software encoding
                        return self.execute(
                            plan,
                            quality=quality,
                            target_codec=target_codec,
                            scale_algorithm=scale_algorithm,
                            ffmpeg_args=ffmpeg_args,
                        )
                    finally:
                        # Restore original config
                        self.hardware_acceleration = original_hw_accel

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

            elapsed = time.monotonic() - start_time

            # Log encoding metrics summary for observability
            if metrics and metrics.sample_count > 0:
                logger.info(
                    "Encoding metrics: avg=%.1f fps, peak=%.1f fps, bitrate=%.0f kbps",
                    metrics.avg_fps or 0,
                    metrics.peak_fps or 0,
                    metrics.avg_bitrate_kbps or 0,
                    extra={
                        "avg_fps": metrics.avg_fps,
                        "peak_fps": metrics.peak_fps,
                        "avg_bitrate_kbps": metrics.avg_bitrate_kbps,
                        "total_frames": metrics.total_frames,
                        "sample_count": metrics.sample_count,
                    },
                )

            logger.info(
                "Transcode completed: %s",
                plan.output_path.name,
                extra={
                    "output_path": str(plan.output_path),
                    "elapsed_seconds": round(elapsed, 3),
                },
            )
            return TranscodeResult(
                success=True,
                output_path=plan.output_path,
                backup_path=backup_path,
                encoding_fps=metrics.avg_fps if metrics else None,
                encoding_bitrate_kbps=metrics.avg_bitrate_kbps if metrics else None,
                total_frames=metrics.total_frames if metrics else None,
                encoder_type=detect_encoder_type(cmd),
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
                build_ffmpeg_command(
                    plan,
                    self.cpu_cores,
                    hardware_acceleration=self.hardware_acceleration,
                )
                if needs_work
                else None
            ),
        }
