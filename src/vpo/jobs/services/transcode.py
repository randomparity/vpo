"""Transcode job processing service.

This module extracts the transcode job business logic from the worker,
providing better testability and separation of concerns.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vpo.config.loader import get_temp_directory
from vpo.db.types import IntrospectionResult, Job, TrackInfo
from vpo.executor.move import MoveExecutor
from vpo.executor.transcode import TranscodeExecutor
from vpo.introspector import (
    FFprobeIntrospector,
    MediaIntrospector,
)
from vpo.jobs.logs import JobLogWriter
from vpo.jobs.progress import FFmpegProgress
from vpo.metadata.parser import parse_filename
from vpo.metadata.templates import parse_template
from vpo.policy.models import TranscodePolicyConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscodeJobResult:
    """Result of processing a transcode job."""

    success: bool
    output_path: str | None = None
    error_message: str | None = None


class TranscodeJobService:
    """Service for processing transcode jobs.

    Separates business logic from worker orchestration for better testability.
    """

    def __init__(
        self,
        introspector: MediaIntrospector | None = None,
        cpu_cores: int | None = None,
    ) -> None:
        """Initialize the transcode job service.

        Args:
            introspector: Media introspector to use. Defaults to FFprobeIntrospector.
            cpu_cores: CPU cores to use for transcoding.
        """
        self.introspector = introspector or FFprobeIntrospector()
        self.cpu_cores = cpu_cores

    def process(
        self,
        job: Job,
        progress_callback: Callable[[FFmpegProgress], None] | None = None,
        job_log: JobLogWriter | None = None,
    ) -> TranscodeJobResult:
        """Process a transcode job end-to-end.

        Args:
            job: The job to process.
            progress_callback: Callback for progress updates.
            job_log: Optional log writer for this job.

        Returns:
            TranscodeJobResult with success/failure status and output path.
        """
        # Parse policy
        policy, policy_data, error = self._parse_policy(job, job_log)
        if error:
            return TranscodeJobResult(success=False, error_message=error)

        # Validate input
        input_path = Path(job.file_path)
        if not input_path.exists():
            error = f"Input file not found: {input_path}"
            if job_log:
                job_log.write_error(error)
            return TranscodeJobResult(success=False, error_message=error)

        # Introspect file
        result, video_track, error = self._introspect_file(input_path, job_log)
        if error:
            return TranscodeJobResult(success=False, error_message=error)

        # Determine output path
        output_path = self._determine_output_path(input_path, policy_data)
        if job_log:
            job_log.write_line(f"Output path: {output_path}")

        # Execute transcode
        transcode_result = self._execute_transcode(
            input_path,
            output_path,
            policy,
            result,
            video_track,
            progress_callback,
            job_log,
        )
        if not transcode_result.success:
            return transcode_result

        # Handle case where transcode succeeded but no output (e.g., skip scenario)
        if not transcode_result.output_path:
            return TranscodeJobResult(success=True, output_path=str(input_path))

        # Move to destination if template specified
        destination_base = policy_data.get("destination_base") if policy_data else None
        final_path = self._apply_destination_template(
            input_path,
            Path(transcode_result.output_path),
            policy,
            destination_base,
            job_log,
        )

        return TranscodeJobResult(success=True, output_path=str(final_path))

    def _parse_policy(
        self, job: Job, job_log: JobLogWriter | None
    ) -> tuple[TranscodePolicyConfig | None, dict[str, Any] | None, str | None]:
        """Parse policy from job JSON.

        Returns:
            Tuple of (policy, policy_data, error_message).
            On success, error_message is None.
            On failure, policy and policy_data are None.
        """
        try:
            policy_data = json.loads(job.policy_json) if job.policy_json else {}
            policy = TranscodePolicyConfig.from_dict(policy_data)
            if job_log:
                job_log.write_line(f"Parsed policy: {job.policy_name or 'default'}")
            return policy, policy_data, None
        except Exception as e:
            error = f"Invalid policy JSON: {e}"
            if job_log:
                job_log.write_error(error)
            return None, None, error

    def _introspect_file(
        self, input_path: Path, job_log: JobLogWriter | None
    ) -> tuple[IntrospectionResult | None, TrackInfo | None, str | None]:
        """Introspect file and extract video track.

        Returns:
            Tuple of (introspection_result, video_track, error_message).
            On success, error_message is None.
            On failure, result and video_track are None.
        """
        if job_log:
            job_log.write_section("Introspecting file")

        result = self.introspector.get_file_info(input_path)
        if not result.success:
            error = f"Introspection failed: {result.error}"
            if job_log:
                job_log.write_error(error)
            return None, None, error

        if job_log:
            job_log.write_line(f"Container: {result.container_format}")
            if result.duration_seconds:
                job_log.write_line(f"Duration: {result.duration_seconds}s")
            job_log.write_line(f"Tracks: {len(result.tracks)}")

        video_track = next((t for t in result.tracks if t.track_type == "video"), None)
        if not video_track:
            error = f"No video track found in: {input_path}"
            if job_log:
                job_log.write_error(error)
            return None, None, error

        if job_log:
            job_log.write_line(
                f"Video: {video_track.codec} {video_track.width}x{video_track.height}"
            )

        return result, video_track, None

    @staticmethod
    def _determine_output_path(input_path: Path, policy_data: dict[str, Any]) -> Path:
        """Compute output path from input and policy.

        Args:
            input_path: Input file path.
            policy_data: Policy configuration dictionary.

        Returns:
            Output path for the transcoded file.
        """
        output_dir = policy_data.get("output_dir")
        if output_dir:
            return Path(output_dir) / input_path.name
        stem = input_path.stem
        return input_path.with_name(f"{stem}.transcoded{input_path.suffix}")

    def _execute_transcode(
        self,
        input_path: Path,
        output_path: Path,
        policy: TranscodePolicyConfig,
        introspection: IntrospectionResult,
        video_track: TrackInfo,
        progress_callback: Callable[[FFmpegProgress], None] | None,
        job_log: JobLogWriter | None,
    ) -> TranscodeJobResult:
        """Execute the transcode operation.

        Args:
            input_path: Input file path.
            output_path: Output file path.
            policy: Transcode policy configuration.
            introspection: Introspection result.
            video_track: Video track info.
            progress_callback: Progress callback.
            job_log: Log writer.

        Returns:
            TranscodeJobResult with success/failure status.
        """
        executor = TranscodeExecutor(
            policy=policy,
            cpu_cores=self.cpu_cores,
            progress_callback=progress_callback,
            temp_directory=get_temp_directory(),
        )

        plan = executor.create_plan(
            input_path=input_path,
            output_path=output_path,
            video_codec=video_track.codec,
            video_width=video_track.width,
            video_height=video_track.height,
            duration_seconds=introspection.duration_seconds,
        )

        if job_log:
            job_log.write_section("Executing transcode")
            job_log.write_line(f"Target codec: {policy.target_video_codec}")
            if policy.target_crf:
                job_log.write_line(f"Target CRF: {policy.target_crf}")
            if self.cpu_cores:
                job_log.write_line(f"CPU cores: {self.cpu_cores}")

        result = executor.execute(plan)

        if not result.success:
            if job_log:
                job_log.write_error(f"Transcode failed: {result.error_message}")
            return TranscodeJobResult(success=False, error_message=result.error_message)

        if job_log:
            job_log.write_line("Transcode completed successfully")

        return TranscodeJobResult(
            success=True, output_path=str(result.output_path or output_path)
        )

    def _apply_destination_template(
        self,
        input_path: Path,
        output_path: Path,
        policy: TranscodePolicyConfig,
        destination_base: str | None,
        job_log: JobLogWriter | None,
    ) -> Path:
        """Apply destination template if specified.

        Args:
            input_path: Original input file path.
            output_path: Current output file path (after transcode).
            policy: Transcode policy configuration with destination settings.
            destination_base: Optional base directory override for destination.
            job_log: Log writer.

        Returns:
            Final output path (may be unchanged if move fails or no template).
        """
        if not policy.destination or not output_path.exists():
            return output_path

        if job_log:
            job_log.write_section("Moving to destination")
            job_log.write_line(f"Template: {policy.destination}")

        try:
            metadata = parse_filename(input_path)
            metadata_dict = metadata.as_dict()
            template = parse_template(policy.destination)

            base_dir = Path(destination_base) if destination_base else input_path.parent
            dest_path = template.render_path(
                base_dir, metadata_dict, policy.destination_fallback
            )
            final_dest = dest_path / output_path.name

            if job_log:
                job_log.write_line(f"Destination: {final_dest}")

            move_executor = MoveExecutor(create_directories=True)
            move_plan = move_executor.create_plan(
                source_path=output_path,
                destination_path=final_dest,
            )
            move_result = move_executor.execute(move_plan)

            if move_result.success:
                logger.info("Moved output to: %s", move_result.destination_path)
                if job_log:
                    job_log.write_line(f"Moved to: {move_result.destination_path}")
                return move_result.destination_path
            else:
                logger.warning(
                    "File movement failed: %s (kept at: %s)",
                    move_result.error_message,
                    output_path,
                )
                if job_log:
                    job_log.write_error(f"Move failed: {move_result.error_message}")
                return output_path

        except Exception as e:
            logger.warning(
                "Destination template failed: %s (kept at: %s)", e, output_path
            )
            if job_log:
                job_log.write_error(f"Template processing failed: {e}")
            return output_path
