"""FFmpeg remux executor for container conversion.

This module provides an executor for lossless container conversion
(primarily MKV to MP4) using ffmpeg with stream copy, with optional
selective transcoding for incompatible tracks.
"""

import logging
import subprocess  # nosec B404 - subprocess is required for ffmpeg execution
import tempfile
from pathlib import Path

from vpo.executor.backup import (
    InsufficientDiskSpaceError,
    check_disk_space,
    create_backup,
    safe_restore_from_backup,
)
from vpo.executor.ffmpeg_base import FFmpegExecutorBase
from vpo.executor.interface import ExecutorResult
from vpo.policy.types import ContainerTranscodePlan, Plan

logger = logging.getLogger(__name__)


def _truncate_stderr(stderr: str, max_lines: int = 20) -> str:
    """Truncate long FFmpeg stderr output to the last N lines.

    Args:
        stderr: Full stderr output from FFmpeg.
        max_lines: Maximum number of lines to keep.

    Returns:
        Truncated stderr string, or original if within limit.
    """
    if not stderr:
        return stderr
    lines = stderr.splitlines()
    if len(lines) <= max_lines:
        return stderr
    return f"...(truncated {len(lines) - max_lines} lines)...\n" + "\n".join(
        lines[-max_lines:]
    )


class FFmpegRemuxExecutor(FFmpegExecutorBase):
    """Executor for container conversion using FFmpeg.

    This executor handles container conversion to MP4 using lossless
    stream copy, with optional selective transcoding for incompatible
    tracks when on_incompatible_codec is set to 'transcode'.

    It is used when:
    - Plan has container_change with target=mp4

    When a transcode_plan is present, the executor:
    - Transcodes incompatible audio tracks to AAC
    - Converts text subtitles to mov_text
    - Removes bitmap subtitles (PGS, DVD) that cannot be converted
    - Copies all compatible tracks losslessly

    The executor:
    1. Creates a backup of the original file
    2. Writes to a temp file with -c copy (lossless) or selective transcoding
    3. Uses -movflags +faststart for streaming optimization
    4. Atomically moves the output to the final location
    """

    def __init__(self, timeout: int | None = None) -> None:
        """Initialize the executor.

        Args:
            timeout: Subprocess timeout in seconds. None uses DEFAULT_TIMEOUT.
        """
        super().__init__(timeout)

    def can_handle(self, plan: Plan) -> bool:
        """Check if this executor can handle the given plan.

        Returns True if:
        - Plan has container_change with target=mp4
        """
        if plan.container_change is None:
            return False

        return plan.container_change.target_format == "mp4"

    def _compute_timeout_for_plan(self, plan: Plan) -> int | None:
        """Compute appropriate timeout based on plan and file size.

        When transcoding is required, scales timeout based on file size
        since transcoding takes significantly longer than remuxing.

        Args:
            plan: The execution plan.

        Returns:
            Timeout in seconds, or None for no timeout.
        """
        if self._timeout <= 0:
            return None

        # Check if transcoding is involved
        transcode_plan = None
        if plan.container_change:
            transcode_plan = plan.container_change.transcode_plan

        has_transcode = bool(transcode_plan and transcode_plan.track_plans)

        try:
            file_size_bytes = plan.file_path.stat().st_size
            return self.compute_timeout(file_size_bytes, is_transcode=has_transcode)
        except OSError:
            # If we can't stat the file, use default timeout
            return self._timeout

    def execute(
        self,
        plan: Plan,
        keep_backup: bool = True,
        keep_original: bool = False,
    ) -> ExecutorResult:
        """Execute container conversion using ffmpeg.

        Args:
            plan: The execution plan to apply.
            keep_backup: Whether to keep the backup file after success.
            keep_original: Whether to keep the original file after container
                conversion (only applies when output path differs from input).

        Returns:
            ExecutorResult with success status.
        """
        if plan.is_empty or plan.container_change is None:
            return ExecutorResult(success=True, message="No changes to apply")

        # Pre-flight disk space check
        try:
            check_disk_space(plan.file_path)
        except InsufficientDiskSpaceError as e:
            return ExecutorResult(success=False, message=str(e))

        # Compute output path with .mp4 extension
        output_path = plan.file_path.with_suffix(".mp4")

        # Create backup
        try:
            backup_path = create_backup(plan.file_path)
        except (FileNotFoundError, PermissionError) as e:
            return ExecutorResult(
                success=False, message=f"Backup failed for {plan.file_path}: {e}"
            )

        # Create temp output file
        with tempfile.NamedTemporaryFile(
            suffix=".mp4", delete=False, dir=plan.file_path.parent
        ) as tmp:
            temp_path = Path(tmp.name)

        # Compute timeout (may scale for transcoding)
        timeout = self._compute_timeout_for_plan(plan)

        # Build ffmpeg command
        cmd = self._build_command(plan, temp_path)

        # Use try/finally to guarantee temp file cleanup
        try:
            # Execute command
            try:
                result = subprocess.run(  # nosec B603 - cmd from validated plan
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                )
            except subprocess.TimeoutExpired:
                restored = safe_restore_from_backup(backup_path)
                timeout_mins = timeout // 60 if timeout else 0
                msg = f"ffmpeg timed out after {timeout_mins} min for {plan.file_path}"
                if not restored:
                    msg += (
                        "\nWARNING: Could not restore backup - "
                        "original file may be corrupted"
                    )
                return ExecutorResult(success=False, message=msg)
            except (subprocess.SubprocessError, OSError) as e:
                restored = safe_restore_from_backup(backup_path)
                msg = f"ffmpeg failed for {plan.file_path}: {e}"
                if not restored:
                    msg += (
                        "\nWARNING: Could not restore backup - "
                        "original file may be corrupted"
                    )
                return ExecutorResult(success=False, message=msg)
            except Exception as e:
                logger.exception(
                    "Unexpected error during ffmpeg execution for %s", plan.file_path
                )
                restored = safe_restore_from_backup(backup_path)
                msg = f"Unexpected error for {plan.file_path}: {e}"
                if not restored:
                    msg += (
                        "\nWARNING: Could not restore backup - "
                        "original file may be corrupted"
                    )
                return ExecutorResult(success=False, message=msg)

            if result.returncode != 0:
                restored = safe_restore_from_backup(backup_path)
                truncated_stderr = _truncate_stderr(result.stderr)
                msg = f"ffmpeg failed for {plan.file_path}: {truncated_stderr}"
                if not restored:
                    msg += (
                        "\nWARNING: Could not restore backup - "
                        "original file may be corrupted"
                    )
                return ExecutorResult(success=False, message=msg)

            # Validate output file using base class method
            try:
                input_size = plan.file_path.stat().st_size
            except OSError:
                input_size = None

            is_valid, error_msg = self.validate_output(temp_path, input_size)
            if not is_valid:
                restored = safe_restore_from_backup(backup_path)
                msg = (
                    f"ffmpeg output validation failed for {plan.file_path}: {error_msg}"
                )
                if not restored:
                    msg += (
                        "\nWARNING: Could not restore backup - "
                        "original file may be corrupted"
                    )
                return ExecutorResult(success=False, message=msg)

            # Atomic move: move temp to output path
            try:
                temp_path.replace(output_path)
            except Exception as e:
                restored = safe_restore_from_backup(backup_path)
                msg = f"Failed to move output for {plan.file_path}: {e}"
                if not restored:
                    msg += (
                        "\nWARNING: Could not restore backup - "
                        "original file may be corrupted"
                    )
                return ExecutorResult(success=False, message=msg)

        finally:
            # Guarantee temp file cleanup.
            # After successful replace(), temp_path no longer exists (it was renamed
            # to output_path). This cleanup only runs if replace() failed or the
            # subprocess failed before we reached the replace() call.
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

        # Delete original file if extension changed (container conversion)
        # unless keep_original is True
        if output_path != plan.file_path and not keep_original:
            plan.file_path.unlink(missing_ok=True)

        # Success - optionally keep backup
        result_backup_path = backup_path if keep_backup else None
        if not keep_backup:
            backup_path.unlink(missing_ok=True)

        # Build success message
        src = plan.container_change.source_format
        transcode_plan = plan.container_change.transcode_plan
        if transcode_plan and transcode_plan.track_plans:
            transcode_count = sum(
                1 for p in transcode_plan.track_plans if p.action == "transcode"
            )
            convert_count = sum(
                1 for p in transcode_plan.track_plans if p.action == "convert"
            )
            remove_count = sum(
                1 for p in transcode_plan.track_plans if p.action == "remove"
            )
            details = []
            if transcode_count:
                details.append(f"{transcode_count} transcoded")
            if convert_count:
                details.append(f"{convert_count} converted")
            if remove_count:
                details.append(f"{remove_count} removed")
            detail_str = ", ".join(details)
            message = f"Converted {src} → mp4 ({detail_str})"
        else:
            message = f"Converted {src} → mp4"

        return ExecutorResult(
            success=True,
            message=message,
            backup_path=result_backup_path,
        )

    def _build_command(self, plan: Plan, output_path: Path) -> list[str]:
        """Build ffmpeg command for container conversion.

        Args:
            plan: The execution plan.
            output_path: Path for the output file.

        Returns:
            List of command line arguments.
        """
        # Check if we have a transcode plan for selective transcoding
        transcode_plan = None
        if plan.container_change:
            transcode_plan = plan.container_change.transcode_plan

        if transcode_plan:
            return self._build_transcode_command(plan, output_path, transcode_plan)

        # Standard remux command (no transcoding)
        cmd = [
            str(self.tool_path),
            "-i",
            str(plan.file_path),
            "-map",
            "0",  # Copy all streams (filtering already handled by evaluator)
            "-c",
            "copy",  # Lossless stream copy (no re-encoding)
            "-movflags",
            "+faststart",  # Move moov atom to front for streaming
        ]

        # Handle track filtering if dispositions indicate removal
        # Build stream exclusion args based on track_dispositions
        if plan.track_dispositions:
            # Build exclusion maps for removed tracks
            for disp in plan.track_dispositions:
                if disp.action == "REMOVE":
                    # Exclude this track from output
                    # -map -0:idx excludes global stream index
                    cmd.extend(["-map", f"-0:{disp.track_index}"])

        # Output file (overwrite if exists)
        cmd.extend(["-y", str(output_path)])

        return cmd

    def _build_transcode_command(
        self,
        plan: Plan,
        output_path: Path,
        transcode_plan: ContainerTranscodePlan,
    ) -> list[str]:
        """Build ffmpeg command with selective transcoding.

        This method builds a command that:
        - Copies compatible streams losslessly
        - Transcodes incompatible audio to AAC
        - Converts text subtitles to mov_text
        - Removes bitmap subtitles

        Args:
            plan: The execution plan.
            output_path: Path for the output file.
            transcode_plan: Plan for handling incompatible tracks.

        Returns:
            List of command line arguments.
        """
        cmd = [
            str(self.tool_path),
            "-i",
            str(plan.file_path),
            "-map",
            "0",  # Start with all streams
        ]

        # Build sets for quick lookup: idx -> (codec, bitrate) or target_codec
        tracks_to_remove: set[int] = set()
        tracks_to_transcode: dict[int, tuple[str, str | None]] = {}
        tracks_to_convert: dict[int, str] = {}

        for track_plan in transcode_plan.track_plans:
            if track_plan.action == "remove":
                tracks_to_remove.add(track_plan.track_index)
            elif track_plan.action == "transcode":
                tracks_to_transcode[track_plan.track_index] = (
                    track_plan.target_codec or "aac",
                    track_plan.target_bitrate,
                )
            elif track_plan.action == "convert":
                tracks_to_convert[track_plan.track_index] = (
                    track_plan.target_codec or "mov_text"
                )

        # Collect all excluded track indices (from transcode_plan and dispositions)
        all_excluded: set[int] = set(tracks_to_remove)

        # Handle track filtering if dispositions indicate removal
        if plan.track_dispositions:
            for disp in plan.track_dispositions:
                if disp.action == "REMOVE":
                    all_excluded.add(disp.track_index)

        # Exclude removed tracks (sorted for deterministic order)
        for idx in sorted(all_excluded):
            cmd.extend(["-map", f"-0:{idx}"])

        # Default: copy all streams
        cmd.extend(["-c", "copy"])

        # Calculate output stream index for each input index
        # After removing tracks with -map -0:{idx}, output indices shift.
        # For example, if we remove track 1, input track 2 becomes output track 1.
        def output_index(input_idx: int) -> int:
            """Convert input stream index to output stream index."""
            return input_idx - sum(1 for r in all_excluded if r < input_idx)

        # Override codec for specific streams that need transcoding
        # Use output stream index notation: -c:out_idx codec
        for idx, (codec, bitrate) in tracks_to_transcode.items():
            out_idx = output_index(idx)
            cmd.extend([f"-c:{out_idx}", codec])
            if bitrate:
                cmd.extend([f"-b:{out_idx}", bitrate])

        # Override codec for subtitle conversions
        for idx, codec in tracks_to_convert.items():
            out_idx = output_index(idx)
            cmd.extend([f"-c:{out_idx}", codec])

        # MP4-specific optimizations
        cmd.extend(["-movflags", "+faststart"])

        # Output file (overwrite if exists)
        cmd.extend(["-y", str(output_path)])

        return cmd
