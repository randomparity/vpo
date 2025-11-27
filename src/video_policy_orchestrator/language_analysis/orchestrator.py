"""Orchestrator for batch language analysis operations.

This module provides the high-level orchestration layer for analyzing
multiple files/tracks. CLI commands delegate to this orchestrator instead
of implementing analysis loops themselves.

This is the single implementation of the language analysis loop, replacing
duplicate implementations in apply.py, scan.py, analyze_language.py, and inspect.py.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from video_policy_orchestrator.db.models import FileRecord, TrackRecord

from video_policy_orchestrator.language_analysis.models import LanguageAnalysisResult
from video_policy_orchestrator.language_analysis.service import (
    InsufficientSpeechError,
    LanguageAnalysisError,
    ShortTrackError,
    TranscriptionPluginError,
    analyze_track_languages,
    get_cached_analysis,
    persist_analysis_result,
)
from video_policy_orchestrator.transcription.factory import TranscriberFactory
from video_policy_orchestrator.transcription.interface import (
    MultiLanguageDetectionConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisProgress:
    """Progress information for analysis callback.

    Passed to the progress_callback during batch analysis to allow
    CLI commands to display progress updates.
    """

    current: int  # Current track number (1-indexed)
    total: int  # Total tracks to analyze
    track_index: int  # Track index in the media file
    file_path: str  # Path to the media file
    status: str  # "analyzing", "cached", "skipped", "error"
    result: LanguageAnalysisResult | None = None  # Result if available
    error: str | None = None  # Error message if status is "error" or "skipped"


@dataclass
class BatchAnalysisResult:
    """Result of batch language analysis.

    Contains counts of analyzed, cached, skipped, and errored tracks,
    along with a mapping of track IDs to analysis results.
    """

    analyzed: int = 0  # Newly analyzed tracks
    cached: int = 0  # Results retrieved from cache
    skipped: int = 0  # Tracks skipped (too short, no speech, etc.)
    errors: int = 0  # Tracks that failed with errors
    results: dict[int, LanguageAnalysisResult] = field(default_factory=dict)
    transcriber_available: bool = True


# Type alias for progress callback
ProgressCallback = Callable[[AnalysisProgress], None]


class LanguageAnalysisOrchestrator:
    """Orchestrates batch language analysis across multiple files/tracks.

    This is the single implementation of the language analysis loop.
    CLI commands (apply, scan, analyze-language, inspect) delegate here.

    Example:
        orchestrator = LanguageAnalysisOrchestrator()
        result = orchestrator.analyze_tracks_for_file(
            conn=conn,
            file_record=file_record,
            track_records=track_records,
            file_path=target,
            progress_callback=lambda p: click.echo(f"Track {p.track_index}: {p.status}")
        )
        if result.results:
            # Use results for policy evaluation
            pass
    """

    def __init__(
        self,
        config: MultiLanguageDetectionConfig | None = None,
    ) -> None:
        """Initialize orchestrator.

        Args:
            config: Optional detection configuration. If not provided,
                    uses default configuration.
        """
        self._config = config or MultiLanguageDetectionConfig()
        self._transcriber = None

    def analyze_tracks_for_file(
        self,
        conn,
        file_record: FileRecord,
        track_records: list[TrackRecord],
        file_path: Path,
        force: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> BatchAnalysisResult:
        """Analyze audio tracks for a single file.

        This is the main entry point for language analysis. It:
        1. Gets or initializes the transcriber
        2. Filters to audio tracks
        3. Checks cache for each track
        4. Runs analysis for uncached tracks
        5. Persists new results

        Args:
            conn: Database connection.
            file_record: FileRecord for the file.
            track_records: List of TrackRecord objects.
            file_path: Path to the media file.
            force: If True, re-analyze even if cached.
            progress_callback: Optional callback for progress updates.

        Returns:
            BatchAnalysisResult with counts and per-track results.
        """
        result = BatchAnalysisResult()

        # Get transcriber
        transcriber = self._get_transcriber()
        if transcriber is None:
            result.transcriber_available = False
            return result

        # Filter to audio tracks
        audio_tracks = [t for t in track_records if t.track_type == "audio"]
        if not audio_tracks:
            return result

        file_hash = file_record.content_hash or ""

        for i, track in enumerate(audio_tracks):
            if track.id is None:
                continue

            progress = AnalysisProgress(
                current=i + 1,
                total=len(audio_tracks),
                track_index=track.track_index,
                file_path=str(file_path),
                status="analyzing",
            )

            # Check cache first (unless force=True)
            if not force:
                cached = get_cached_analysis(conn, track.id, file_hash)
                if cached is not None:
                    result.cached += 1
                    result.results[track.id] = cached
                    if progress_callback:
                        progress.status = "cached"
                        progress.result = cached
                        progress_callback(progress)
                    continue

            # Run analysis
            track_duration = track.duration_seconds or 3600.0
            try:
                analysis_result = analyze_track_languages(
                    file_path=file_path,
                    track_index=track.track_index,
                    track_id=track.id,
                    track_duration=track_duration,
                    file_hash=file_hash,
                    transcriber=transcriber,
                    config=self._config,
                )
                persist_analysis_result(conn, analysis_result)
                result.analyzed += 1
                result.results[track.id] = analysis_result

                if progress_callback:
                    progress.status = "analyzed"
                    progress.result = analysis_result
                    progress_callback(progress)

            except (ShortTrackError, InsufficientSpeechError) as e:
                result.skipped += 1
                logger.debug("Track %d skipped: %s", track.track_index, e)
                if progress_callback:
                    progress.status = "skipped"
                    progress.error = str(e)
                    progress_callback(progress)

            except (LanguageAnalysisError, TranscriptionPluginError) as e:
                result.errors += 1
                logger.warning(
                    "Language analysis failed for track %d: %s",
                    track.track_index,
                    e,
                )
                if progress_callback:
                    progress.status = "error"
                    progress.error = str(e)
                    progress_callback(progress)

            except Exception as e:
                result.errors += 1
                logger.exception(
                    "Unexpected error analyzing track %d: %s",
                    track.track_index,
                    e,
                )
                if progress_callback:
                    progress.status = "error"
                    progress.error = str(e)
                    progress_callback(progress)

        return result

    def _get_transcriber(self):
        """Get transcriber with caching."""
        if self._transcriber is None:
            self._transcriber = TranscriberFactory.get_transcriber(
                require_multi_language=True
            )
        return self._transcriber


def analyze_file_audio_tracks(
    conn,
    file_record: FileRecord,
    track_records: list[TrackRecord],
    file_path: Path,
    force: bool = False,
    verbose: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> dict[int, LanguageAnalysisResult] | None:
    """Convenience function to analyze audio tracks for a file.

    This provides a simpler interface for common use cases, wrapping
    the LanguageAnalysisOrchestrator.

    Args:
        conn: Database connection.
        file_record: FileRecord for the file.
        track_records: List of TrackRecord objects.
        file_path: Path to the media file.
        force: If True, re-analyze even if cached.
        verbose: If True, log progress (only used if no progress_callback).
        progress_callback: Optional callback for progress updates.

    Returns:
        Dict mapping track_id to LanguageAnalysisResult, or None if
        no transcriber available or no results.
    """
    orchestrator = LanguageAnalysisOrchestrator()

    # Create a verbose callback if requested and no callback provided
    if verbose and progress_callback is None:

        def verbose_callback(p: AnalysisProgress) -> None:
            if p.status == "cached":
                logger.info(
                    "Track %d: %s (cached)",
                    p.track_index,
                    p.result.classification.value if p.result else "unknown",
                )
            elif p.status == "analyzed" and p.result:
                logger.info(
                    "Track %d: %s (%s %.0f%%)",
                    p.track_index,
                    p.result.classification.value,
                    p.result.primary_language,
                    p.result.primary_percentage * 100,
                )
            elif p.status == "skipped":
                logger.info("Track %d: skipped - %s", p.track_index, p.error)
            elif p.status == "error":
                logger.warning("Track %d: error - %s", p.track_index, p.error)

        progress_callback = verbose_callback

    result = orchestrator.analyze_tracks_for_file(
        conn=conn,
        file_record=file_record,
        track_records=track_records,
        file_path=file_path,
        force=force,
        progress_callback=progress_callback,
    )

    if not result.transcriber_available:
        return None

    # Commit any new results
    if result.analyzed > 0:
        conn.commit()

    return result.results if result.results else None
