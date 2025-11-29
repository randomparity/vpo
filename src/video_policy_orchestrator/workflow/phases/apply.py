"""Apply phase for policy application.

This phase applies the policy to the file, handling track ordering,
filtering, metadata changes, and container conversion.
"""

import logging
from pathlib import Path
from sqlite3 import Connection

from video_policy_orchestrator.db.queries import get_file_by_path, get_tracks_for_file
from video_policy_orchestrator.db.types import tracks_to_track_info
from video_policy_orchestrator.policy.models import PolicySchema
from video_policy_orchestrator.workflow.processor import PhaseError

logger = logging.getLogger(__name__)


class ApplyPhase:
    """Policy application phase using PolicyEnginePlugin."""

    def __init__(
        self,
        conn: Connection,
        policy: PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> None:
        """Initialize the apply phase.

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
        self._policy_engine = None

    def _get_policy_engine(self):
        """Get or create PolicyEnginePlugin instance."""
        if self._policy_engine is None:
            from video_policy_orchestrator.plugins.policy_engine import (
                PolicyEnginePlugin,
            )

            self._policy_engine = PolicyEnginePlugin()
        return self._policy_engine

    def run(self, file_path: Path) -> int:
        """Apply the policy to the file.

        Args:
            file_path: Path to the video file.

        Returns:
            Number of changes applied.

        Raises:
            PhaseError: If application fails.
        """
        from video_policy_orchestrator.policy.models import ProcessingPhase

        # Get file record from database
        file_record = get_file_by_path(self.conn, str(file_path))
        if file_record is None:
            raise PhaseError(
                ProcessingPhase.APPLY,
                f"File not found in database. Run 'vpo scan' first: {file_path}",
            )

        # Get tracks and convert to TrackInfo
        track_records = get_tracks_for_file(self.conn, file_record.id)
        tracks = tracks_to_track_info(track_records)

        if not tracks:
            raise PhaseError(
                ProcessingPhase.APPLY,
                f"No tracks found for file: {file_path}",
            )

        # Determine container format
        container = file_record.container_format or file_path.suffix.lstrip(".")

        # Get policy engine
        policy_engine = self._get_policy_engine()

        try:
            # Evaluate the policy to create a plan
            plan = policy_engine.evaluate(
                file_id=str(file_record.id),
                file_path=file_path,
                container=container,
                tracks=tracks,
                policy=self.policy,
            )

            if plan.is_empty:
                logger.info("No changes required for %s", file_path)
                return 0

            changes_count = len(plan.actions) + plan.tracks_removed

            if self.dry_run:
                logger.info(
                    "[DRY-RUN] Would apply %d changes to %s",
                    changes_count,
                    file_path,
                )
                return changes_count

            if self.verbose:
                logger.info("Applying %d changes to %s", changes_count, file_path)

            # Execute the plan
            result = policy_engine.execute(
                plan,
                keep_backup=True,
                keep_original=False,
            )

            if not result.success:
                raise PhaseError(
                    ProcessingPhase.APPLY,
                    f"Execution failed: {result.message}",
                )

            logger.info("Applied %d changes to %s", changes_count, file_path)
            return changes_count

        except PhaseError:
            raise
        except Exception as e:
            raise PhaseError(
                ProcessingPhase.APPLY,
                f"Policy application failed: {e}",
                cause=e,
            ) from e
