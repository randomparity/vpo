"""Unit tests for TranscriptionService.

Tests the high-level service for phase executor transcription operations,
including language detection, track classification, and database persistence.
"""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from video_policy_orchestrator.db.schema import create_schema
from video_policy_orchestrator.db.types import TrackClassification, TrackInfo
from video_policy_orchestrator.transcription.multi_sample import AggregatedResult
from video_policy_orchestrator.transcription.service import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    TranscriptionOptions,
    TranscriptionService,
    TranscriptionServiceResult,
)


@pytest.fixture
def db_conn():
    """Create in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def mock_transcriber():
    """Create a mock transcription plugin."""
    transcriber = MagicMock()
    transcriber.name = "test-transcriber"
    return transcriber


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 100)
    return f


def insert_test_file(conn: sqlite3.Connection, file_path: Path) -> int:
    """Insert a test file record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            container_format, modified_at, scanned_at, scan_status
        )
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'complete')
        """,
        (
            str(file_path),
            file_path.name,
            str(file_path.parent),
            file_path.suffix,
            100,
            "mkv",
        ),
    )
    conn.commit()
    return cursor.lastrowid


def insert_test_track(
    conn: sqlite3.Connection,
    file_id: int,
    index: int,
    track_type: str,
    language: str = "eng",
) -> int:
    """Insert a test track record and return its ID."""
    codec = {"video": "h264", "audio": "aac", "subtitle": "srt"}.get(
        track_type, "unknown"
    )
    cursor = conn.execute(
        """
        INSERT INTO tracks (
            file_id, track_index, track_type, codec, language
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (file_id, index, track_type, codec, language),
    )
    conn.commit()
    return cursor.lastrowid


class TestTranscriptionOptions:
    """Tests for TranscriptionOptions dataclass."""

    def test_default_values(self):
        """TranscriptionOptions has sensible defaults."""
        options = TranscriptionOptions()

        assert options.confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD
        assert options.max_samples == 3
        assert options.sample_duration == 30
        assert options.incumbent_bonus == 0.15

    def test_custom_values(self):
        """TranscriptionOptions accepts custom values."""
        options = TranscriptionOptions(
            confidence_threshold=0.9,
            max_samples=5,
            sample_duration=60,
            incumbent_bonus=0.2,
        )

        assert options.confidence_threshold == 0.9
        assert options.max_samples == 5
        assert options.sample_duration == 60
        assert options.incumbent_bonus == 0.2


class TestTranscriptionServiceAnalyzeTrack:
    """Tests for TranscriptionService.analyze_track method."""

    def test_calls_smart_detect_with_correct_params(self, mock_transcriber, test_file):
        """analyze_track calls smart_detect with correct parameters."""
        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            index=1,
            track_type="audio",
            language="eng",
            duration_seconds=120.0,
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.95,
                samples_taken=1,
                transcript_sample="Hello world",
            )

            service.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
            )

        # Verify smart_detect was called with correct parameters
        mock_detect.assert_called_once()
        call_kwargs = mock_detect.call_args.kwargs
        assert call_kwargs["file_path"] == test_file
        assert call_kwargs["track_index"] == 1
        assert call_kwargs["track_duration"] == 120.0
        assert call_kwargs["transcriber"] is mock_transcriber
        assert call_kwargs["incumbent_language"] == "eng"

    def test_returns_transcription_result(self, mock_transcriber, test_file):
        """analyze_track returns TranscriptionServiceResult."""
        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            index=1,
            track_type="audio",
            language="eng",
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="fra",
                confidence=0.88,
                samples_taken=2,
                transcript_sample="Bonjour le monde",
            )

            result = service.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
            )

        assert isinstance(result, TranscriptionServiceResult)
        assert result.track_index == 1
        assert result.detected_language == "fra"
        assert result.confidence == 0.88
        assert result.transcript_sample == "Bonjour le monde"

    def test_uses_custom_options(self, mock_transcriber, test_file):
        """analyze_track uses custom TranscriptionOptions."""
        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(index=1, track_type="audio")

        options = TranscriptionOptions(
            confidence_threshold=0.9,
            max_samples=5,
            sample_duration=60,
            incumbent_bonus=0.3,
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.95,
                samples_taken=1,
            )

            service.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
                options=options,
            )

        # Verify config was built from options
        call_kwargs = mock_detect.call_args.kwargs
        config = call_kwargs["config"]
        assert config.confidence_threshold == 0.9
        assert config.max_samples == 5
        assert config.sample_duration == 60
        assert config.incumbent_bonus == 0.3


class TestTranscriptionServiceClassifyTrack:
    """Tests for track classification via _classify_track."""

    def test_classifies_commentary_by_title(self, mock_transcriber, test_file):
        """Classifies track as COMMENTARY based on title metadata."""
        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            index=1,
            track_type="audio",
            title="Director's Commentary",
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.9,
                samples_taken=1,
                transcript_sample="In this scene, we wanted to...",
            )

            result = service.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
            )

        assert result.track_type == TrackClassification.COMMENTARY

    def test_classifies_music_by_title(self, mock_transcriber, test_file):
        """Classifies track as MUSIC based on title metadata."""
        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            index=1,
            track_type="audio",
            title="Isolated Score",
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language=None,
                confidence=0.3,
                samples_taken=1,
            )

            result = service.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
            )

        assert result.track_type == TrackClassification.MUSIC

    def test_classifies_main_for_normal_track(self, mock_transcriber, test_file):
        """Classifies track as MAIN for normal audio with speech."""
        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            index=1,
            track_type="audio",
            language="eng",
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.95,
                samples_taken=1,
                transcript_sample="The quick brown fox jumps over the lazy dog.",
            )

            result = service.analyze_track(
                file_path=test_file,
                track=track,
                track_duration=120.0,
            )

        assert result.track_type == TrackClassification.MAIN


class TestTranscriptionServiceAnalyzeAndPersist:
    """Tests for TranscriptionService.analyze_and_persist method."""

    def test_persists_result_to_database(self, db_conn, mock_transcriber, test_file):
        """analyze_and_persist saves transcription result to database."""
        # Setup: Insert file and track
        file_id = insert_test_file(db_conn, test_file)
        track_id = insert_test_track(db_conn, file_id, 1, "audio", "eng")

        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            id=track_id,  # Must have database ID
            index=1,
            track_type="audio",
            language="eng",
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="fra",
                confidence=0.88,
                samples_taken=2,
                transcript_sample="Bonjour",
            )

            result = service.analyze_and_persist(
                file_path=test_file,
                track=track,
                track_duration=120.0,
                conn=db_conn,
            )

        # Verify result
        assert result.detected_language == "fra"
        assert result.confidence == 0.88

        # Verify database persistence
        cursor = db_conn.execute(
            "SELECT * FROM transcription_results WHERE track_id = ?",
            (track_id,),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row["detected_language"] == "fra"
        assert row["confidence_score"] == 0.88
        assert row["plugin_name"] == "test-transcriber"
        assert row["transcript_sample"] == "Bonjour"

    def test_raises_for_track_without_id(self, db_conn, mock_transcriber, test_file):
        """analyze_and_persist raises ValueError if track has no ID."""
        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            index=1,
            track_type="audio",
            # No id!
        )

        with pytest.raises(ValueError, match="Track 1 has no database ID"):
            service.analyze_and_persist(
                file_path=test_file,
                track=track,
                track_duration=120.0,
                conn=db_conn,
            )

    def test_stores_track_type(self, db_conn, mock_transcriber, test_file):
        """analyze_and_persist stores track classification."""
        file_id = insert_test_file(db_conn, test_file)
        track_id = insert_test_track(db_conn, file_id, 1, "audio", "eng")

        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            id=track_id,
            index=1,
            track_type="audio",
            title="Director Commentary",  # Should classify as COMMENTARY
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.9,
                samples_taken=1,
            )

            service.analyze_and_persist(
                file_path=test_file,
                track=track,
                track_duration=120.0,
                conn=db_conn,
            )

        # Verify track_type was stored
        cursor = db_conn.execute(
            "SELECT track_type FROM transcription_results WHERE track_id = ?",
            (track_id,),
        )
        row = cursor.fetchone()
        assert row["track_type"] == "commentary"

    def test_upserts_existing_result(self, db_conn, mock_transcriber, test_file):
        """analyze_and_persist updates existing transcription result."""
        file_id = insert_test_file(db_conn, test_file)
        track_id = insert_test_track(db_conn, file_id, 1, "audio", "eng")

        service = TranscriptionService(mock_transcriber)

        track = TrackInfo(
            id=track_id,
            index=1,
            track_type="audio",
        )

        with patch(
            "video_policy_orchestrator.transcription.service.smart_detect"
        ) as mock_detect:
            # First call
            mock_detect.return_value = AggregatedResult(
                language="eng",
                confidence=0.7,
                samples_taken=1,
            )

            service.analyze_and_persist(
                file_path=test_file,
                track=track,
                track_duration=120.0,
                conn=db_conn,
            )

            # Second call with different result
            mock_detect.return_value = AggregatedResult(
                language="fra",
                confidence=0.95,
                samples_taken=3,
            )

            service.analyze_and_persist(
                file_path=test_file,
                track=track,
                track_duration=120.0,
                conn=db_conn,
            )

        # Should only have one record (upserted)
        cursor = db_conn.execute(
            "SELECT COUNT(*) as count FROM transcription_results WHERE track_id = ?",
            (track_id,),
        )
        assert cursor.fetchone()["count"] == 1

        # Should have the updated values
        cursor = db_conn.execute(
            "SELECT * FROM transcription_results WHERE track_id = ?",
            (track_id,),
        )
        row = cursor.fetchone()
        assert row["detected_language"] == "fra"
        assert row["confidence_score"] == 0.95
