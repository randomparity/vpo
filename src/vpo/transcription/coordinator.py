"""Transcription coordinator using the plugin system.

This module provides a coordinator that uses PluginRegistry instead of the
separate TranscriptionRegistry. It dispatches TranscriptionRequestedEvent
through the plugin system to find transcription-capable plugins.

Key classes:
- TranscriptionCoordinator: Main coordinator for transcription operations
- PluginTranscriberAdapter: Adapter implementing TranscriptionPlugin protocol
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vpo.db.queries import upsert_transcription_result
from vpo.db.types import (
    TrackClassification,
    TrackInfo,
    TranscriptionResultRecord,
)
from vpo.metrics import get_metrics_store, increment_counter
from vpo.plugin.events import (
    TRANSCRIPTION_COMPLETED,
    TRANSCRIPTION_REQUESTED,
    TranscriptionCompletedEvent,
    TranscriptionRequestedEvent,
)
from vpo.plugin.registry import LoadedPlugin, PluginRegistry
from vpo.transcription.interface import (
    MultiLanguageDetectionResult,
    TranscriptionError,
)
from vpo.transcription.models import (
    TranscriptionResult,
    detect_track_classification,
)
from vpo.transcription.multi_sample import (
    AggregatedResult,
    MultiSampleConfig,
    smart_detect,
)

logger = logging.getLogger(__name__)

# Default confidence threshold for language detection
DEFAULT_CONFIDENCE_THRESHOLD = 0.8


class NoTranscriptionPluginError(Exception):
    """Raised when no transcription plugin is available."""

    pass


@dataclass(frozen=True)
class TranscriptionOptions:
    """Options for transcription analysis."""

    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    max_samples: int = 3
    sample_duration: int = 30
    incumbent_bonus: float = 0.15


@dataclass
class TranscriptionCoordinatorResult:
    """Result of transcribing a single audio track via TranscriptionCoordinator."""

    track_index: int
    detected_language: str | None
    confidence: float
    transcript_sample: str | None
    track_type: TrackClassification
    plugin_name: str


class PluginTranscriberAdapter:
    """Adapter implementing TranscriptionPlugin protocol using PluginRegistry.

    This adapter wraps the plugin dispatch mechanism in a TranscriptionPlugin-
    compatible interface, allowing the existing smart_detect() function to be
    reused without modification.

    The adapter creates TranscriptionRequestedEvent and dispatches it to all
    plugins subscribed to the transcription.requested event.

    IMPORTANT: This adapter is single-use per analyze_track() call. Create a
    new instance for each track analysis. The adapter tracks the plugin that
    handled the request so it can be reported after smart_detect() completes.
    Do not reuse instances across different tracks or concurrent operations.
    """

    # Default sample rate for audio extraction (Whisper-compatible)
    DEFAULT_SAMPLE_RATE = 16000

    def __init__(
        self,
        registry: PluginRegistry,
        file_path: Path,
        track: TrackInfo,
    ) -> None:
        """Initialize the adapter.

        Args:
            registry: Plugin registry to find transcription plugins.
            file_path: Path to the media file being transcribed.
            track: TrackInfo for the audio track being transcribed.
        """
        self._registry = registry
        self._file_path = file_path
        self._track = track
        self._last_plugin_name: str | None = None
        self._finalized = False

    @property
    def name(self) -> str:
        """Plugin identifier (from last successful plugin)."""
        return self._last_plugin_name or "plugin-adapter"

    @property
    def version(self) -> str:
        """Plugin version string."""
        return "1.0.0"

    @property
    def last_plugin_name(self) -> str | None:
        """Name of the last plugin that successfully handled a request.

        Reading this property finalizes the adapter, preventing further use.
        This ensures the adapter is not accidentally reused after results
        are collected.
        """
        self._finalized = True
        return self._last_plugin_name

    def _dispatch_event(
        self,
        audio_data: bytes,
        sample_rate: int,
        options: dict,
    ) -> TranscriptionResult:
        """Dispatch transcription event to plugins.

        Args:
            audio_data: Raw audio bytes (WAV format).
            sample_rate: Sample rate of audio data.
            options: Additional options for transcription.

        Returns:
            TranscriptionResult from the first successful plugin.

        Raises:
            TranscriptionError: If no plugin can handle the request.
            RuntimeError: If adapter has been finalized (reuse attempt).
        """
        if self._finalized:
            raise RuntimeError(
                "PluginTranscriberAdapter has been finalized and cannot be reused. "
                "Create a new adapter instance for each analyze_track() call."
            )

        event = TranscriptionRequestedEvent(
            file_path=self._file_path,
            track=self._track,
            audio_data=audio_data,
            sample_rate=sample_rate,
            options=options,
        )

        plugins = self._registry.get_by_event(TRANSCRIPTION_REQUESTED)
        if not plugins:
            raise TranscriptionError(
                "No transcription plugins available. "
                "Install a transcription plugin (e.g., whisper-local)."
            )

        errors: list[str] = []
        for loaded_plugin in plugins:
            try:
                handler = getattr(
                    loaded_plugin.instance, "on_transcription_requested", None
                )
                if handler is None:
                    logger.debug(
                        "Plugin %s has no on_transcription_requested handler",
                        loaded_plugin.name,
                    )
                    continue

                # Time the handler call
                start_time = time.monotonic()
                result = handler(event)
                duration = time.monotonic() - start_time

                # Record metrics
                increment_counter("plugin.invocations", plugin_name=loaded_plugin.name)
                get_metrics_store().record_duration(
                    "plugin.duration",
                    duration,
                    plugin_name=loaded_plugin.name,
                    event="transcription.requested",
                )

                # Warn on slow plugins
                if duration > 1.0:
                    logger.warning(
                        "Slow plugin: %s took %.2fs for transcription.requested",
                        loaded_plugin.name,
                        duration,
                    )

                if result is not None:
                    self._last_plugin_name = loaded_plugin.name
                    logger.debug(
                        "Plugin %s handled transcription request in %.2fs",
                        loaded_plugin.name,
                        duration,
                    )
                    return result
            except Exception as e:
                logger.warning(
                    "Plugin %s failed: %s",
                    loaded_plugin.name,
                    e,
                )
                errors.append(f"{loaded_plugin.name}: {e}")

        # All plugins failed or returned None
        if errors:
            raise TranscriptionError(
                f"All transcription plugins failed: {'; '.join(errors)}"
            )
        raise TranscriptionError("No transcription plugin could handle the request")

    def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Full transcription with optional language hint.

        Args:
            audio_data: Raw audio bytes (WAV format, mono).
            sample_rate: Sample rate of audio data.
            language: Optional language hint (ISO 639-1/639-2 code).

        Returns:
            TranscriptionResult with transcript_sample and detected_language.

        Raises:
            TranscriptionError: If transcription fails.
        """
        options = {"language": language} if language else {}
        return self._dispatch_event(audio_data, sample_rate, options)

    def detect_language(
        self,
        audio_data: bytes,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ) -> TranscriptionResult:
        """Detect language from audio data.

        Args:
            audio_data: Raw audio bytes (WAV format, mono).
            sample_rate: Sample rate of audio data.

        Returns:
            TranscriptionResult with detected_language and confidence_score.

        Raises:
            TranscriptionError: If detection fails.
        """
        return self._dispatch_event(audio_data, sample_rate, {"detect_only": True})

    def supports_feature(self, feature: str) -> bool:
        """Check if any plugin supports a feature.

        Args:
            feature: Feature name to check.

        Returns:
            True if at least one plugin supports the feature.
        """
        plugins = self._registry.get_by_event(TRANSCRIPTION_REQUESTED)
        for loaded_plugin in plugins:
            supports = getattr(loaded_plugin.instance, "supports_feature", None)
            if supports and supports(feature):
                return True
        return False

    def detect_multi_language(
        self,
        audio_data: bytes,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ) -> MultiLanguageDetectionResult:
        """Detect language from a single audio sample.

        This delegates to the transcribe method and converts the result.

        Args:
            audio_data: Raw audio bytes (WAV format, mono).
            sample_rate: Sample rate of audio data.

        Returns:
            MultiLanguageDetectionResult with language and confidence.
        """
        try:
            result = self.transcribe(audio_data, sample_rate)
            return MultiLanguageDetectionResult(
                position=0.0,  # Position set by caller
                language=result.detected_language,
                confidence=result.confidence_score,
                has_speech=bool(result.transcript_sample),
            )
        except TranscriptionError as e:
            return MultiLanguageDetectionResult(
                position=0.0,
                language=None,
                confidence=0.0,
                has_speech=False,
                errors=[str(e)],
            )


class TranscriptionCoordinator:
    """Coordinates transcription through the plugin system.

    This coordinator uses PluginRegistry to find plugins subscribed to the
    transcription.requested event, replacing the separate TranscriptionRegistry.

    Design principles:
    - Single Responsibility: coordinate transcription workflow
    - Dependency Injection: accepts PluginRegistry
    - Testability: all dependencies explicit
    - Type Safety: validates inputs, returns typed results
    """

    def __init__(self, registry: PluginRegistry) -> None:
        """Initialize the coordinator.

        Args:
            registry: Plugin registry to find transcription plugins.
        """
        self._registry = registry

    def get_transcription_plugins(self) -> list[LoadedPlugin]:
        """Get plugins subscribed to transcription.requested event.

        Returns:
            List of enabled plugins registered for transcription events.
        """
        return self._registry.get_by_event(TRANSCRIPTION_REQUESTED)

    def is_available(self) -> bool:
        """Check if any transcription plugin is available.

        Returns:
            True if at least one transcription plugin is enabled.
        """
        return len(self.get_transcription_plugins()) > 0

    def get_default_plugin(self) -> LoadedPlugin | None:
        """Get the default transcription plugin.

        Returns the first available transcription plugin, or None if none available.

        Returns:
            First enabled transcription plugin, or None.
        """
        plugins = self.get_transcription_plugins()
        return plugins[0] if plugins else None

    def analyze_track(
        self,
        file_path: Path,
        track: TrackInfo,
        track_duration: float,
        options: TranscriptionOptions | None = None,
    ) -> TranscriptionCoordinatorResult:
        """Analyze a single audio track for language detection.

        Args:
            file_path: Path to the media file.
            track: TrackInfo for the audio track to analyze.
            track_duration: Duration of track in seconds.
            options: Transcription options (uses defaults if None).

        Returns:
            TranscriptionCoordinatorResult with detected language and confidence.

        Raises:
            NoTranscriptionPluginError: If no transcription plugin is available.
            ValueError: If track_duration is not positive.
            TranscriptionError: If analysis fails.
        """
        if not self.is_available():
            raise NoTranscriptionPluginError(
                "No transcription plugins available. "
                "Install a transcription plugin (e.g., whisper-local)."
            )

        if track_duration <= 0:
            raise ValueError(f"track_duration must be positive, got {track_duration}")

        if options is None:
            options = TranscriptionOptions()

        logger.debug("Analyzing track %d for language detection", track.index)

        # Create adapter that dispatches to plugins via events
        adapter = PluginTranscriberAdapter(
            registry=self._registry,
            file_path=file_path,
            track=track,
        )

        # Create multi-sample config from options
        config = MultiSampleConfig(
            max_samples=options.max_samples,
            sample_duration=options.sample_duration,
            confidence_threshold=options.confidence_threshold,
            incumbent_bonus=options.incumbent_bonus,
        )

        # Perform multi-sample detection using existing smart_detect
        aggregated = smart_detect(
            file_path=file_path,
            track_index=track.index,
            track_duration=track_duration,
            transcriber=adapter,
            config=config,
            incumbent_language=track.language,
        )

        # Determine track type from metadata and transcript
        track_type = self._classify_track(track, aggregated)

        # Get the plugin name from the adapter
        plugin_name = adapter.last_plugin_name or "unknown"

        return TranscriptionCoordinatorResult(
            track_index=track.index,
            detected_language=aggregated.language,
            confidence=aggregated.confidence,
            transcript_sample=aggregated.transcript_sample,
            track_type=track_type,
            plugin_name=plugin_name,
        )

    def analyze_and_persist(
        self,
        file_path: Path,
        track: TrackInfo,
        track_duration: float,
        conn: sqlite3.Connection,
        options: TranscriptionOptions | None = None,
    ) -> TranscriptionCoordinatorResult:
        """Analyze track and persist results to database.

        Args:
            file_path: Path to the media file.
            track: TrackInfo for the audio track (must have database ID).
            track_duration: Duration of track in seconds.
            conn: Database connection.
            options: Transcription options.

        Returns:
            TranscriptionCoordinatorResult with detected language.

        Raises:
            ValueError: If track has no database ID.
            NoTranscriptionPluginError: If no transcription plugin is available.
            TranscriptionError: If analysis fails.
            sqlite3.Error: If database operation fails.
        """
        # Validate track has database ID
        if track.id is None:
            raise ValueError(f"Track {track.index} has no database ID")

        # Analyze the track
        result = self.analyze_track(file_path, track, track_duration, options)

        # Build database record
        now = datetime.now(timezone.utc).isoformat()
        record = TranscriptionResultRecord(
            id=None,  # Will be assigned by database
            track_id=track.id,
            detected_language=result.detected_language,
            confidence_score=result.confidence,
            track_type=result.track_type.value,
            transcript_sample=result.transcript_sample,
            plugin_name=result.plugin_name,
            created_at=now,
            updated_at=now,
        )

        # Persist to database
        upsert_transcription_result(conn, record)

        logger.info(
            "Track %d: detected language=%s (confidence=%.2f, type=%s, plugin=%s)",
            track.index,
            result.detected_language,
            result.confidence,
            result.track_type.value,
            result.plugin_name,
        )

        # Dispatch completion event to interested plugins
        self._dispatch_completion_event(file_path, track.id, result)

        return result

    def _classify_track(
        self,
        track: TrackInfo,
        aggregated: AggregatedResult,
    ) -> TrackClassification:
        """Classify track type using metadata and transcript analysis.

        Uses the detect_track_classification function which applies
        multi-stage detection:
        1. Metadata keywords (most reliable - SFX/MUSIC/COMMENTARY)
        2. Speech detection + confidence (for unlabeled tracks)
        3. Transcript analysis (for commentary detection)

        Args:
            track: TrackInfo with metadata.
            aggregated: AggregatedResult from multi-sample detection.

        Returns:
            TrackClassification enum value.
        """
        # Determine if we detected speech based on confidence
        # Low confidence + empty/hallucinated transcript = no speech
        has_speech = aggregated.confidence > 0.4 or bool(aggregated.transcript_sample)

        return detect_track_classification(
            title=track.title,
            transcript_sample=aggregated.transcript_sample,
            has_speech=has_speech,
            confidence=aggregated.confidence,
        )

    def _dispatch_completion_event(
        self,
        file_path: Path,
        track_id: int,
        result: TranscriptionCoordinatorResult,
    ) -> None:
        """Dispatch transcription completion event to interested plugins.

        Args:
            file_path: Path to the media file.
            track_id: Database ID of the transcribed track.
            result: Transcription result.
        """
        # Create a minimal result for the event
        # Note: We use TranscriptionResult from models for the event payload
        now = datetime.now(timezone.utc)
        transcription_result = TranscriptionResult(
            track_id=track_id,
            detected_language=result.detected_language,
            confidence_score=result.confidence,
            track_type=result.track_type,
            transcript_sample=result.transcript_sample,
            plugin_name=result.plugin_name,
            created_at=now,
            updated_at=now,
        )

        event = TranscriptionCompletedEvent(
            file_path=file_path,
            track_id=track_id,
            result=transcription_result,
        )

        # Dispatch to plugins subscribed to transcription.completed
        plugins = self._registry.get_by_event(TRANSCRIPTION_COMPLETED)
        for loaded_plugin in plugins:
            try:
                handler = getattr(
                    loaded_plugin.instance, "on_transcription_completed", None
                )
                if handler:
                    # Time the handler call
                    start_time = time.monotonic()
                    handler(event)
                    duration = time.monotonic() - start_time

                    # Record metrics
                    increment_counter(
                        "plugin.invocations", plugin_name=loaded_plugin.name
                    )
                    get_metrics_store().record_duration(
                        "plugin.duration",
                        duration,
                        plugin_name=loaded_plugin.name,
                        event="transcription.completed",
                    )

                    # Warn on slow plugins
                    if duration > 1.0:
                        logger.warning(
                            "Slow plugin: %s took %.2fs for transcription.completed",
                            loaded_plugin.name,
                            duration,
                        )
            except Exception as e:
                logger.warning(
                    "Plugin %s failed to handle completion event: %s",
                    loaded_plugin.name,
                    e,
                )
