"""Transcode executor for video/audio transcoding via FFmpeg.

This module implements the TranscodeExecutor class for video transcoding
operations, including safety features like disk space checks, backups,
and atomic file replacement.
"""

import logging
import queue
import shutil
import subprocess  # nosec B404 - subprocess is required for FFmpeg invocation
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

from vpo.db import TrackInfo
from vpo.policy.transcode import (
    AudioAction,
    create_audio_plan,
    create_audio_plan_v6,
    describe_audio_plan,
    evaluate_skip_condition,
)
from vpo.policy.types import (
    AudioTranscodeConfig,
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
from vpo.tools.ffmpeg_metrics import FFmpegMetricsAggregator, FFmpegMetricsSummary
from vpo.tools.ffmpeg_progress import (
    FFmpegProgress,
    parse_stderr_progress,
)

from .command import build_ffmpeg_command, build_ffmpeg_command_pass1
from .decisions import should_transcode_video
from .types import TranscodePlan, TranscodeResult, TwoPassContext

logger = logging.getLogger(__name__)


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
    ) -> tuple[bool, int, list[str], FFmpegMetricsSummary | None]:
        """Run FFmpeg command with timeout and threaded stderr reading.

        Args:
            cmd: FFmpeg command arguments.
            description: Description for logging (e.g., "pass 1", "transcode").
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (success, return_code, stderr_lines, metrics_summary).
            success is False if timeout expired or process failed.
            metrics_summary contains aggregated encoding metrics if available.
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
        stop_event = threading.Event()

        # Metrics aggregator for collecting encoding stats (Issue #264)
        metrics_aggregator = FFmpegMetricsAggregator()

        def read_stderr() -> None:
            """Read stderr lines and put them in the queue."""
            try:
                assert process.stderr is not None
                for line in process.stderr:
                    if stop_event.is_set():
                        break
                    stderr_queue.put(line)
            except (ValueError, OSError):
                # Pipe closed or process terminated
                pass
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
                if progress:
                    # Collect metrics (Issue #264)
                    metrics_aggregator.add_sample(progress)
                    if progress_callback:
                        progress_callback(progress)
            except queue.Empty:
                continue

        # Handle timeout
        if timeout_expired:
            logger.warning(
                "%s timed out after %s seconds", description, self.transcode_timeout
            )
            stop_event.set()  # Signal thread to stop
            process.kill()
            # Close stderr to unblock reader thread
            if process.stderr:
                try:
                    process.stderr.close()
                except Exception:  # nosec B110 - Intentionally ignoring close errors
                    pass
            process.wait()  # Clean up zombie process
            # Wait for reader thread to finish with shorter timeout
            reader_thread.join(timeout=2.0)
            if reader_thread.is_alive():
                logger.warning("Stderr reader thread did not terminate cleanly")
            return (False, -1, stderr_output, metrics_aggregator.summarize())

        # Signal thread to stop (process completed normally)
        stop_event.set()

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

        return (
            process.returncode == 0,
            process.returncode,
            stderr_output,
            metrics_aggregator.summarize(),
        )

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

            success1, rc1, stderr1, _ = self._run_ffmpeg_with_timeout(
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

            success2, rc2, stderr2, metrics2 = self._run_ffmpeg_with_timeout(
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

            return TranscodeResult(
                success=True,
                output_path=temp_output,
                encoding_fps=metrics2.avg_fps if metrics2 else None,
                encoding_bitrate_kbps=metrics2.avg_bitrate_kbps if metrics2 else None,
                total_frames=metrics2.total_frames if metrics2 else None,
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
        logger.debug("FFmpeg command: %s", " ".join(cmd))

        try:
            # Ensure output directory exists
            temp_output.parent.mkdir(parents=True, exist_ok=True)
            plan.output_path.parent.mkdir(parents=True, exist_ok=True)

            # Run FFmpeg with progress monitoring and timeout
            success, rc, stderr_output, metrics = self._run_ffmpeg_with_timeout(
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

            elapsed = time.monotonic() - start_time
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
