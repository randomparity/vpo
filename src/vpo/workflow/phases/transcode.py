"""Transcode phase for video/audio codec conversion.

This phase handles video transcoding using the TranscodeExecutor,
including conditional skip logic and hardware acceleration.
"""

import logging
from pathlib import Path
from sqlite3 import Connection

from vpo.config.loader import get_temp_directory
from vpo.db.queries import get_file_by_path, get_tracks_for_file
from vpo.db.types import TrackInfo, tracks_to_track_info
from vpo.policy.models import PolicySchema
from vpo.workflow.processor import PhaseError

logger = logging.getLogger(__name__)


class TranscodePhase:
    """Video transcoding phase using TranscodeExecutor."""

    def __init__(
        self,
        conn: Connection,
        policy: PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        """Initialize the transcode phase.

        Args:
            conn: Database connection.
            policy: PolicySchema configuration.
            dry_run: If True, preview without making changes.
            verbose: If True, emit detailed logging.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose

    def run(self, file_path: Path) -> int:
        """Run transcoding on the file.

        Args:
            file_path: Path to the video file.

        Returns:
            1 if transcoded, 0 if skipped.

        Raises:
            PhaseError: If transcoding fails.
        """
        from vpo.policy.models import ProcessingPhase

        # Check if policy has transcode config
        if not self._has_transcode_config():
            logger.info("No transcode configuration in policy, skipping")
            return 0

        # Get file record from database
        file_record = get_file_by_path(self.conn, str(file_path))
        if file_record is None:
            raise PhaseError(
                ProcessingPhase.TRANSCODE,
                f"File not found in database. Run 'vpo scan' first: {file_path}",
            )

        # Get tracks
        track_records = get_tracks_for_file(self.conn, file_record.id)
        tracks = tracks_to_track_info(track_records)

        video_track = self._get_primary_video_track(tracks)
        if video_track is None:
            logger.info(
                "No video track found in %s, skipping transcode", file_path.name
            )
            return 0

        audio_tracks = [t for t in tracks if t.track_type == "audio"]

        try:
            # Build transcode plan
            from vpo.executor.transcode import TranscodeExecutor

            # Get the appropriate config based on policy version
            transcode_config = self._get_transcode_config()
            skip_if = self._get_skip_condition()
            audio_config = self._get_audio_config()

            executor = TranscodeExecutor(
                policy=transcode_config,
                skip_if=skip_if,
                audio_config=audio_config,
                backup_original=True,
                temp_directory=get_temp_directory(),
            )

            # Create plan (output_path same as input for in-place transcode;
            # executor handles temp file + atomic replacement internally)
            plan = executor.create_plan(
                input_path=file_path,
                output_path=file_path,
                video_codec=video_track.codec,
                video_width=video_track.width,
                video_height=video_track.height,
                duration_seconds=video_track.duration_seconds,
                audio_tracks=audio_tracks,
                all_tracks=tracks,
                file_size_bytes=file_record.size_bytes,
            )

            # Check if transcoding should be skipped
            if plan.skip_reason:
                logger.info(
                    "Skipping transcode for %s: %s",
                    file_path.name,
                    plan.skip_reason,
                )
                return 0

            if self.dry_run:
                logger.info("[DRY-RUN] Would transcode %s", file_path.name)
                return 1

            if self.verbose:
                logger.info("Transcoding %s", file_path.name)

            # Execute transcode (plan contains input_path and output_path)
            result = executor.execute(plan)

            if not result.success:
                raise PhaseError(
                    ProcessingPhase.TRANSCODE,
                    f"Transcode failed: {result.error_message}",
                )

            logger.info("Transcoded %s successfully", file_path.name)
            return 1

        except PhaseError:
            raise
        except Exception as e:
            raise PhaseError(
                ProcessingPhase.TRANSCODE,
                f"Transcode failed: {e}",
                cause=e,
            ) from e

    def _has_transcode_config(self) -> bool:
        """Check if policy has any transcode configuration."""
        return (
            self.policy.video_transcode is not None or self.policy.transcode is not None
        )

    def _get_transcode_config(self):
        """Get the TranscodePolicyConfig from policy."""
        from vpo.policy.models import TranscodePolicyConfig

        if self.policy.transcode is not None:
            return self.policy.transcode

        # Create a minimal config from V6+ video_transcode
        if self.policy.video_transcode is not None:
            vt = self.policy.video_transcode
            return TranscodePolicyConfig(
                target_video_codec=vt.target_codec,
                target_crf=vt.quality.crf if vt.quality else None,
                max_resolution=vt.scaling.max_resolution if vt.scaling else None,
            )

        return TranscodePolicyConfig()

    def _get_skip_condition(self):
        """Get the skip condition from V6+ config."""
        if self.policy.video_transcode is not None:
            return self.policy.video_transcode.skip_if
        return None

    def _get_audio_config(self):
        """Get the audio transcode config from policy."""
        return self.policy.audio_transcode

    def _get_primary_video_track(self, tracks: list[TrackInfo]) -> TrackInfo | None:
        """Get the primary video track."""
        video_tracks = [t for t in tracks if t.track_type == "video"]
        return video_tracks[0] if video_tracks else None
