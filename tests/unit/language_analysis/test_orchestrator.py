"""Unit tests for language analysis orchestrator dual-path logic."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.db.schema import initialize_database
from vpo.db.types import FileRecord, TrackRecord
from vpo.language_analysis.orchestrator import (
    BatchAnalysisResult,
    LanguageAnalysisOrchestrator,
)


@pytest.fixture
def db_connection():
    """Create an in-memory database with schema for testing."""
    conn = sqlite3.connect(":memory:")
    initialize_database(conn)
    yield conn
    conn.close()


@pytest.fixture
def file_record() -> FileRecord:
    """Create a sample file record for testing."""
    return FileRecord(
        id=1,
        path="/test/movie.mkv",
        filename="movie.mkv",
        directory="/test",
        extension=".mkv",
        size_bytes=1000000,
        modified_at="2024-01-01T00:00:00",
        content_hash="test_hash_12345",
        container_format="matroska",
        scanned_at="2024-01-01T00:00:00",
        scan_status="ok",
        scan_error=None,
    )


@pytest.fixture
def audio_tracks() -> list[TrackRecord]:
    """Create sample audio track records for testing."""
    return [
        TrackRecord(
            id=1,
            file_id=1,
            track_index=0,
            track_type="audio",
            codec="aac",
            language="eng",
            title="English",
            is_default=True,
            is_forced=False,
            duration_seconds=3600.0,
        ),
        TrackRecord(
            id=2,
            file_id=1,
            track_index=1,
            track_type="audio",
            codec="aac",
            language="jpn",
            title="Japanese",
            is_default=False,
            is_forced=False,
            duration_seconds=3600.0,
        ),
    ]


class TestLanguageAnalysisOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_init_defaults(self) -> None:
        """Test initialization with default values."""
        orchestrator = LanguageAnalysisOrchestrator()

        assert orchestrator._plugin_registry is None
        assert orchestrator._coordinator is None
        assert orchestrator._config is not None

    def test_init_with_plugin_registry(self) -> None:
        """Test initialization with plugin registry."""
        mock_registry = MagicMock()
        orchestrator = LanguageAnalysisOrchestrator(plugin_registry=mock_registry)

        assert orchestrator._plugin_registry is mock_registry
        assert orchestrator._coordinator is None  # Lazy init


class TestLanguageAnalysisOrchestratorPluginRegistry:
    """Tests for plugin registry requirement."""

    def test_no_registry_returns_unavailable(
        self,
        db_connection: sqlite3.Connection,
        file_record: FileRecord,
        audio_tracks: list[TrackRecord],
    ) -> None:
        """With plugin_registry=None, transcriber_available is False."""
        orchestrator = LanguageAnalysisOrchestrator(plugin_registry=None)

        result = orchestrator.analyze_tracks_for_file(
            conn=db_connection,
            file_record=file_record,
            track_records=audio_tracks,
            file_path=Path("/test/movie.mkv"),
        )

        # Result should indicate transcriber unavailable
        assert result.transcriber_available is False

    def test_uses_coordinator_when_registry_provided(
        self,
        db_connection: sqlite3.Connection,
        file_record: FileRecord,
        audio_tracks: list[TrackRecord],
    ) -> None:
        """With plugin_registry, uses TranscriptionCoordinator."""
        mock_registry = MagicMock()

        orchestrator = LanguageAnalysisOrchestrator(plugin_registry=mock_registry)

        # Mock the coordinator import and instantiation
        with patch(
            "vpo.transcription.coordinator.TranscriptionCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator.is_available.return_value = False
            mock_coordinator_class.return_value = mock_coordinator

            result = orchestrator.analyze_tracks_for_file(
                conn=db_connection,
                file_record=file_record,
                track_records=audio_tracks,
                file_path=Path("/test/movie.mkv"),
            )

            # Result should indicate transcriber unavailable
            # (coordinator has no plugins)
            assert result.transcriber_available is False

    def test_coordinator_unavailable_returns_false(
        self,
        db_connection: sqlite3.Connection,
        file_record: FileRecord,
        audio_tracks: list[TrackRecord],
    ) -> None:
        """When coordinator has no plugins, transcriber_available=False."""
        mock_registry = MagicMock()

        orchestrator = LanguageAnalysisOrchestrator(plugin_registry=mock_registry)

        with patch(
            "vpo.transcription.coordinator.TranscriptionCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator.is_available.return_value = False
            mock_coordinator_class.return_value = mock_coordinator

            result = orchestrator.analyze_tracks_for_file(
                conn=db_connection,
                file_record=file_record,
                track_records=audio_tracks,
                file_path=Path("/test/movie.mkv"),
            )

            mock_coordinator.is_available.assert_called_once()
            assert result.transcriber_available is False
            assert result.analyzed == 0
            assert result.cached == 0

    def test_coordinator_lazy_initialized(
        self,
        db_connection: sqlite3.Connection,
        file_record: FileRecord,
        audio_tracks: list[TrackRecord],
    ) -> None:
        """Coordinator is only created when first track is analyzed."""
        mock_registry = MagicMock()

        orchestrator = LanguageAnalysisOrchestrator(plugin_registry=mock_registry)

        # Before any analysis, coordinator should be None
        assert orchestrator._coordinator is None

        with patch(
            "vpo.transcription.coordinator.TranscriptionCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = MagicMock()
            mock_coordinator.is_available.return_value = False
            mock_coordinator_class.return_value = mock_coordinator

            orchestrator.analyze_tracks_for_file(
                conn=db_connection,
                file_record=file_record,
                track_records=audio_tracks,
                file_path=Path("/test/movie.mkv"),
            )

            # Now coordinator should be set
            assert orchestrator._coordinator is mock_coordinator
            mock_coordinator_class.assert_called_once_with(mock_registry)


class TestBatchAnalysisResult:
    """Tests for BatchAnalysisResult dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        result = BatchAnalysisResult()

        assert result.analyzed == 0
        assert result.cached == 0
        assert result.skipped == 0
        assert result.errors == 0
        assert result.results == {}
        assert result.transcriber_available is True

    def test_tracks_counts(self) -> None:
        """Test that counts can be modified."""
        result = BatchAnalysisResult()
        result.analyzed = 5
        result.cached = 3
        result.skipped = 1
        result.errors = 1

        assert result.analyzed == 5
        assert result.cached == 3
        assert result.skipped == 1
        assert result.errors == 1
