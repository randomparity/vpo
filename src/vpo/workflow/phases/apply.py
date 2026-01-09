"""Apply phase for policy application.

This phase applies the policy to the file, handling track ordering,
filtering, metadata changes, and container conversion.
"""

import json
import logging
from pathlib import Path
from sqlite3 import Connection

from vpo.db.operations import (
    OperationStatus,
    create_operation,
    update_operation_status,
)
from vpo.db.queries import (
    get_file_by_path,
    get_tracks_for_file,
    get_transcriptions_for_tracks,
)
from vpo.db.types import tracks_to_track_info
from vpo.executor.backup import FileLockError, file_lock
from vpo.policy.models import Plan, PolicySchema
from vpo.workflow.processor import PhaseError

logger = logging.getLogger(__name__)


class ApplyPhase:
    """Policy application phase using PolicyEnginePlugin."""

    def __init__(
        self,
        conn: Connection,
        policy: PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
        policy_name: str = "workflow",
    ) -> None:
        """Initialize the apply phase.

        Args:
            conn: Database connection.
            policy: PolicySchema configuration.
            dry_run: If True, preview without making changes.
            verbose: If True, emit detailed logging.
            policy_name: Name of the policy for audit records.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self.policy_name = policy_name
        self._policy_engine = None
        self._last_plan: Plan | None = None  # Store for dry-run output

    def _get_policy_engine(self):
        """Get or create PolicyEnginePlugin instance."""
        if self._policy_engine is None:
            from vpo.plugins.policy_engine import (
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
        from vpo.policy.models import ProcessingPhase

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

        # Load transcription results for audio tracks
        audio_track_ids = [t.id for t in track_records if t.track_type == "audio"]
        transcription_results = get_transcriptions_for_tracks(
            self.conn, audio_track_ids
        )

        # Parse plugin metadata from FileRecord (stored as JSON string)
        plugin_metadata: dict | None = None
        if file_record.plugin_metadata:
            try:
                plugin_metadata = json.loads(file_record.plugin_metadata)
            except json.JSONDecodeError as e:
                logger.error(
                    "Corrupted plugin_metadata JSON for file %s (file_id=%s): %s. "
                    "Plugin metadata conditions will not be evaluated. "
                    "Re-scan the file to regenerate metadata.",
                    file_path,
                    file_record.id,
                    e,
                )

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
                transcription_results=transcription_results,
                plugin_metadata=plugin_metadata,
            )

            # Store plan for dry-run output access
            self._last_plan = plan

            if plan.is_empty:
                logger.info("No changes required for %s", file_path.name)
                return 0

            changes_count = len(plan.actions) + plan.tracks_removed

            if self.dry_run:
                logger.info(
                    "[DRY-RUN] Would apply %d changes to %s",
                    changes_count,
                    file_path.name,
                )
                return changes_count

            if self.verbose:
                logger.info("Applying %d changes to %s", changes_count, file_path.name)

            # Create operation record for audit trail
            operation = create_operation(
                conn=self.conn,
                plan=plan,
                file_id=file_record.id,
                policy_name=self.policy_name,
            )

            # Acquire file lock and execute the plan
            try:
                with file_lock(file_path):
                    result = policy_engine.execute(
                        plan,
                        keep_backup=True,
                        keep_original=False,
                    )
            except FileLockError as e:
                update_operation_status(
                    self.conn,
                    operation.id,
                    OperationStatus.FAILED,
                    error_message=f"File lock error: {e}",
                )
                raise PhaseError(
                    ProcessingPhase.APPLY,
                    f"Cannot acquire file lock: {e}",
                ) from e

            if not result.success:
                update_operation_status(
                    self.conn,
                    operation.id,
                    OperationStatus.FAILED,
                    error_message=result.message,
                )
                raise PhaseError(
                    ProcessingPhase.APPLY,
                    f"Execution failed: {result.message}",
                )

            # Update operation as completed
            update_operation_status(
                self.conn,
                operation.id,
                OperationStatus.COMPLETED,
                backup_path=str(result.backup_path) if result.backup_path else None,
            )

            logger.info("Applied %d changes to %s", changes_count, file_path.name)
            return changes_count

        except PhaseError:
            raise
        except Exception as e:
            raise PhaseError(
                ProcessingPhase.APPLY,
                f"Policy application failed: {e}",
                cause=e,
            ) from e
