"""FFmpeg remux executor for container conversion.

This module provides an executor for lossless container conversion
(primarily MKV to MP4) using ffmpeg with stream copy.
"""

import logging
import subprocess  # nosec B404 - subprocess is required for ffmpeg execution
import tempfile
from pathlib import Path

from video_policy_orchestrator.executor.backup import (
    InsufficientDiskSpaceError,
    check_disk_space,
    create_backup,
    restore_from_backup,
)
from video_policy_orchestrator.executor.interface import ExecutorResult, require_tool
from video_policy_orchestrator.policy.models import Plan

logger = logging.getLogger(__name__)


class FFmpegRemuxExecutor:
    """Executor for container conversion using FFmpeg.

    This executor handles container conversion to MP4 using lossless
    stream copy. It is used when:
    - Plan has container_change with target=mp4

    Note: This executor assumes codec compatibility has already been
    checked by the policy evaluator. Incompatible codecs should have
    either raised IncompatibleCodecError or skipped the conversion.

    The executor:
    1. Creates a backup of the original file
    2. Writes to a temp file with -c copy (lossless)
    3. Uses -movflags +faststart for streaming optimization
    4. Atomically moves the output to the final location
    """

    def __init__(self) -> None:
        """Initialize the executor."""
        self._tool_path: Path | None = None

    @property
    def tool_path(self) -> Path:
        """Get path to ffmpeg, verifying availability."""
        if self._tool_path is None:
            self._tool_path = require_tool("ffmpeg")
        return self._tool_path

    def can_handle(self, plan: Plan) -> bool:
        """Check if this executor can handle the given plan.

        Returns True if:
        - Plan has container_change with target=mp4
        """
        if plan.container_change is None:
            return False

        return plan.container_change.target_format == "mp4"

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
            return ExecutorResult(success=False, message=f"Backup failed: {e}")

        # Create temp output file
        with tempfile.NamedTemporaryFile(
            suffix=".mp4", delete=False, dir=plan.file_path.parent
        ) as tmp:
            temp_path = Path(tmp.name)

        # Build ffmpeg command
        cmd = self._build_command(plan, temp_path)

        # Execute command
        try:
            result = subprocess.run(  # nosec B603 - cmd from validated plan
                cmd,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute timeout for large files
            )
        except subprocess.TimeoutExpired:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message="ffmpeg timed out after 30 minutes",
            )
        except (subprocess.SubprocessError, OSError) as e:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"ffmpeg execution failed: {e}",
            )
        except Exception as e:
            logger.exception("Unexpected error during ffmpeg execution")
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"Unexpected error during ffmpeg execution: {e}",
            )

        if result.returncode != 0:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"ffmpeg failed: {result.stderr}",
            )

        # Atomic move: move temp to output path
        try:
            temp_path.replace(output_path)
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            restore_from_backup(backup_path)
            return ExecutorResult(
                success=False,
                message=f"Failed to move output file: {e}",
            )

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
        return ExecutorResult(
            success=True,
            message=f"Converted {src} → mp4",
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
