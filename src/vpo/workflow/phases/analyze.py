"""Analyze phase for language detection.

This phase runs automatic language analysis on audio tracks using the
transcription plugin to detect spoken languages.
"""

from __future__ import annotations

import logging
from pathlib import Path
from sqlite3 import Connection
from typing import TYPE_CHECKING

from vpo.db.queries import get_file_by_path, get_tracks_for_file
from vpo.policy.models import PolicySchema
from vpo.workflow.processor import PhaseError

if TYPE_CHECKING:
    from vpo.plugin import PluginRegistry

logger = logging.getLogger(__name__)


class AnalyzePhase:
    """Language detection phase using LanguageAnalysisOrchestrator."""

    def __init__(
        self,
        conn: Connection,
        policy: PolicySchema,
        dry_run: bool = False,
        verbose: bool = False,
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        """Initialize the analyze phase.

        Args:
            conn: Database connection.
            policy: PolicySchema configuration.
            dry_run: If True, preview without making changes.
            verbose: If True, emit detailed logging.
            plugin_registry: Optional plugin registry for coordinator-based
                transcription. If provided, uses TranscriptionCoordinator.
                If None, falls back to legacy TranscriberFactory.
        """
        self.conn = conn
        self.policy = policy
        self.dry_run = dry_run
        self.verbose = verbose
        self._plugin_registry = plugin_registry

    def run(self, file_path: Path) -> int:
        """Run language analysis on the file's audio tracks.

        Args:
            file_path: Path to the video file.

        Returns:
            Number of tracks analyzed.

        Raises:
            PhaseError: If analysis fails.
        """
        from vpo.policy.models import ProcessingPhase

        # Get file record from database
        file_record = get_file_by_path(self.conn, str(file_path))
        if file_record is None:
            raise PhaseError(
                ProcessingPhase.ANALYZE,
                f"File not found in database. Run 'vpo scan' first: {file_path}",
            )

        # Get tracks
        track_records = get_tracks_for_file(self.conn, file_record.id)
        audio_tracks = [t for t in track_records if t.track_type == "audio"]

        if not audio_tracks:
            logger.info("No audio tracks to analyze in %s", file_path.name)
            return 0

        # Import orchestrator here to avoid circular imports
        from vpo.language_analysis.orchestrator import (
            LanguageAnalysisOrchestrator,
        )

        orchestrator = LanguageAnalysisOrchestrator(
            plugin_registry=self._plugin_registry,
        )

        if self.dry_run:
            logger.info(
                "[DRY-RUN] Would analyze %d audio track(s) in %s",
                len(audio_tracks),
                file_path.name,
            )
            return len(audio_tracks)

        if self.verbose:
            count = len(audio_tracks)
            logger.info("Analyzing %d audio track(s) in %s", count, file_path.name)

        try:
            result = orchestrator.analyze_tracks_for_file(
                conn=self.conn,
                file_record=file_record,
                track_records=track_records,
                file_path=file_path,
            )

            if not result.transcriber_available:
                logger.warning(
                    "Transcription plugin not available. Language analysis skipped."
                )
                return 0

            # Note: Commit is handled by WorkflowProcessor after successful phase
            analyzed_count = len(result.results) if result.results else 0
            logger.info(
                "Analyzed %d track(s) in %s",
                analyzed_count,
                file_path,
            )
            return analyzed_count

        except Exception as e:
            raise PhaseError(
                ProcessingPhase.ANALYZE,
                f"Language analysis failed: {e}",
                cause=e,
            ) from e
