"""FFmpeg executor for audio synthesis operations.

This module implements the execution of synthesis plans using FFmpeg
to transcode audio tracks and mkvmerge to assemble the final file.
"""

from __future__ import annotations

import logging
import shutil
import subprocess  # nosec B404 - subprocess needed for FFmpeg/mkvmerge
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from video_policy_orchestrator.executor.interface import require_tool
from video_policy_orchestrator.policy.synthesis.encoders import (
    get_encoder_for_codec,
)
from video_policy_orchestrator.policy.synthesis.models import (
    AudioCodec,
    SynthesisOperation,
    SynthesisPlan,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class SynthesisExecutionResult:
    """Result of executing a synthesis plan."""

    success: bool
    """Whether the execution completed successfully."""

    output_path: Path | None = None
    """Path to the output file if successful."""

    backup_path: Path | None = None
    """Path to the backup of the original file."""

    tracks_created: int = 0
    """Number of synthesized tracks created."""

    message: str = ""
    """Human-readable status message."""

    errors: list[str] = field(default_factory=list)
    """List of error messages if not successful."""


class FFmpegSynthesisExecutor:
    """Executor for audio synthesis using FFmpeg and mkvmerge.

    This executor:
    1. Transcodes source tracks to target codec using FFmpeg
    2. Uses mkvmerge to add synthesized tracks to the output file
    3. Preserves all original tracks
    """

    def __init__(
        self,
        ffmpeg_path: Path | None = None,
        mkvmerge_path: Path | None = None,
        temp_dir: Path | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            ffmpeg_path: Path to ffmpeg binary, or None to auto-detect.
            mkvmerge_path: Path to mkvmerge binary, or None to auto-detect.
            temp_dir: Directory for temporary files, or None for system default.
        """
        self._ffmpeg_path = ffmpeg_path
        self._mkvmerge_path = mkvmerge_path
        self._temp_dir = temp_dir

    def _get_ffmpeg(self) -> Path:
        """Get the FFmpeg path, raising if unavailable."""
        if self._ffmpeg_path:
            return self._ffmpeg_path
        return require_tool("ffmpeg")

    def _get_mkvmerge(self) -> Path:
        """Get the mkvmerge path, raising if unavailable."""
        if self._mkvmerge_path:
            return self._mkvmerge_path
        return require_tool("mkvmerge")

    def _build_ffmpeg_args(
        self,
        input_path: Path,
        operation: SynthesisOperation,
        output_path: Path,
    ) -> list[str]:
        """Build FFmpeg command arguments for a synthesis operation.

        Args:
            input_path: Path to input file.
            operation: The synthesis operation to perform.
            output_path: Path for output audio file.

        Returns:
            List of command arguments.
        """
        ffmpeg = str(self._get_ffmpeg())
        encoder = get_encoder_for_codec(operation.target_codec)

        args = [
            ffmpeg,
            "-hide_banner",
            "-y",  # Overwrite output
            "-i",
            str(input_path),
            "-map",
            f"0:a:{operation.source_track.track_index}",
        ]

        # Apply downmix filter if needed
        if operation.downmix_filter:
            args.extend(["-af", operation.downmix_filter])

        # Set encoder
        args.extend(["-c:a", encoder])

        # Set bitrate (if applicable)
        if operation.target_bitrate:
            args.extend(["-b:a", str(operation.target_bitrate)])

        # Set output format based on codec
        if operation.target_codec == AudioCodec.EAC3:
            args.extend(["-f", "eac3"])
        elif operation.target_codec == AudioCodec.AAC:
            args.extend(["-f", "adts"])
        elif operation.target_codec == AudioCodec.AC3:
            args.extend(["-f", "ac3"])
        elif operation.target_codec == AudioCodec.OPUS:
            args.extend(["-f", "opus"])
        elif operation.target_codec == AudioCodec.FLAC:
            args.extend(["-f", "flac"])

        args.append(str(output_path))
        return args

    def _transcode_track(
        self,
        input_path: Path,
        operation: SynthesisOperation,
        work_dir: Path,
    ) -> Path | None:
        """Transcode a single audio track.

        Args:
            input_path: Path to input file.
            operation: The synthesis operation to perform.
            work_dir: Working directory for temp files.

        Returns:
            Path to transcoded audio file, or None on failure.
        """
        # Determine output extension
        ext_map = {
            AudioCodec.EAC3: ".eac3",
            AudioCodec.AAC: ".aac",
            AudioCodec.AC3: ".ac3",
            AudioCodec.OPUS: ".opus",
            AudioCodec.FLAC: ".flac",
        }
        ext = ext_map.get(operation.target_codec, ".audio")
        output_path = work_dir / f"synth_{operation.definition_name}{ext}"

        args = self._build_ffmpeg_args(input_path, operation, output_path)
        logger.debug("FFmpeg command: %s", " ".join(args))

        try:
            result = subprocess.run(  # nosec B603 - args are controlled
                args,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout
            )

            if result.returncode != 0:
                logger.error(
                    "FFmpeg transcode failed for '%s': %s",
                    operation.definition_name,
                    result.stderr,
                )
                return None

            if not output_path.exists():
                logger.error(
                    "FFmpeg did not create output file for '%s'",
                    operation.definition_name,
                )
                return None

            logger.info(
                "Transcoded track '%s' to %s",
                operation.definition_name,
                output_path.name,
            )
            return output_path

        except subprocess.TimeoutExpired:
            logger.error(
                "FFmpeg transcode timed out for '%s'",
                operation.definition_name,
            )
            return None
        except Exception as e:
            logger.exception(
                "Error transcoding track '%s': %s",
                operation.definition_name,
                e,
            )
            return None

    def _build_mkvmerge_args(
        self,
        input_path: Path,
        transcoded_tracks: list[tuple[SynthesisOperation, Path]],
        output_path: Path,
    ) -> list[str]:
        """Build mkvmerge command to merge transcoded tracks.

        Args:
            input_path: Path to original input file.
            transcoded_tracks: List of (operation, audio_path) tuples.
            output_path: Path for final output file.

        Returns:
            List of command arguments.
        """
        mkvmerge = str(self._get_mkvmerge())

        args = [
            mkvmerge,
            "-o",
            str(output_path),
            str(input_path),  # Include all original tracks
        ]

        # Add each transcoded track
        for operation, audio_path in transcoded_tracks:
            # Set track properties
            args.extend(
                [
                    "--language",
                    f"0:{operation.target_language}",
                ]
            )
            if operation.target_title:
                args.extend(
                    [
                        "--track-name",
                        f"0:{operation.target_title}",
                    ]
                )
            args.append(str(audio_path))

        return args

    def execute(
        self,
        plan: SynthesisPlan,
        keep_backup: bool = True,
        dry_run: bool = False,
    ) -> SynthesisExecutionResult:
        """Execute a synthesis plan.

        Args:
            plan: The synthesis plan to execute.
            keep_backup: Whether to keep a backup of the original file.
            dry_run: If True, only validate without making changes.

        Returns:
            SynthesisExecutionResult with execution details.
        """
        if not plan.has_operations:
            return SynthesisExecutionResult(
                success=True,
                output_path=plan.file_path,
                message="No synthesis operations to perform",
            )

        if dry_run:
            return SynthesisExecutionResult(
                success=True,
                output_path=plan.file_path,
                tracks_created=len(plan.operations),
                message=f"Would create {len(plan.operations)} synthesized track(s)",
            )

        # Create working directory
        temp_dir = self._temp_dir or Path(tempfile.gettempdir())
        work_dir = temp_dir / f"vpo_synthesis_{plan.file_id[:8]}"
        work_dir.mkdir(parents=True, exist_ok=True)

        errors: list[str] = []
        transcoded_tracks: list[tuple[SynthesisOperation, Path]] = []

        try:
            # Step 1: Transcode each track
            for operation in plan.operations:
                audio_path = self._transcode_track(
                    plan.file_path,
                    operation,
                    work_dir,
                )
                if audio_path is None:
                    errors.append(f"Failed to transcode '{operation.definition_name}'")
                else:
                    transcoded_tracks.append((operation, audio_path))

            if errors:
                return SynthesisExecutionResult(
                    success=False,
                    message="Some transcoding operations failed",
                    errors=errors,
                )

            if not transcoded_tracks:
                return SynthesisExecutionResult(
                    success=True,
                    output_path=plan.file_path,
                    message="No tracks to add",
                )

            # Step 2: Create backup if requested
            backup_path = None
            if keep_backup:
                backup_path = plan.file_path.with_suffix(f".bak{plan.file_path.suffix}")
                shutil.copy2(plan.file_path, backup_path)
                logger.info("Created backup at %s", backup_path)

            # Step 3: Merge with mkvmerge
            output_path = work_dir / f"output{plan.file_path.suffix}"
            merge_args = self._build_mkvmerge_args(
                plan.file_path,
                transcoded_tracks,
                output_path,
            )
            logger.debug("mkvmerge command: %s", " ".join(merge_args))

            result = subprocess.run(  # nosec B603 - args are controlled
                merge_args,
                capture_output=True,
                text=True,
                timeout=3600,
            )

            if result.returncode not in (0, 1):  # mkvmerge returns 1 for warnings
                return SynthesisExecutionResult(
                    success=False,
                    backup_path=backup_path,
                    message="mkvmerge failed to merge tracks",
                    errors=[result.stderr],
                )

            # Step 4: Replace original with output
            shutil.move(str(output_path), str(plan.file_path))

            return SynthesisExecutionResult(
                success=True,
                output_path=plan.file_path,
                backup_path=backup_path,
                tracks_created=len(transcoded_tracks),
                message=f"Created {len(transcoded_tracks)} synthesized track(s)",
            )

        finally:
            # Cleanup temp files (but keep transcoded files for debugging if failed)
            if not errors:
                for _, audio_path in transcoded_tracks:
                    if audio_path.exists():
                        audio_path.unlink()
                try:
                    work_dir.rmdir()
                except OSError:
                    pass  # Directory not empty or other issue


def execute_synthesis_plan(
    plan: SynthesisPlan,
    keep_backup: bool = True,
    dry_run: bool = False,
) -> SynthesisExecutionResult:
    """Execute a synthesis plan using the default executor.

    Args:
        plan: The synthesis plan to execute.
        keep_backup: Whether to keep a backup of the original file.
        dry_run: If True, only validate without making changes.

    Returns:
        SynthesisExecutionResult with execution details.
    """
    executor = FFmpegSynthesisExecutor()
    return executor.execute(plan, keep_backup=keep_backup, dry_run=dry_run)
