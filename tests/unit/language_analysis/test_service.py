"""Unit tests for language analysis service."""

import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.db.schema import initialize_database
from vpo.language_analysis.models import (
    AnalysisMetadata,
    LanguageAnalysisResult,
    LanguageClassification,
    LanguageSegment,
)
from vpo.language_analysis.service import (
    _create_segments_from_samples,
    get_cached_analysis,
    invalidate_analysis_cache,
    persist_analysis_result,
)
from vpo.transcription.interface import (
    MultiLanguageDetectionResult,
)


@pytest.fixture
def db_connection():
    """Create an in-memory database with schema for testing."""
    conn = sqlite3.connect(":memory:")
    initialize_database(conn)

    # Create a test file and track
    conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            modified_at, scanned_at, scan_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "/test/movie.mkv",
            "movie.mkv",
            "/test",
            ".mkv",
            1000000,
            "2024-01-01T00:00:00",
            "2024-01-01T00:00:00",
            "ok",
        ),
    )
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        """
        INSERT INTO tracks (
            file_id, track_index, track_type, codec, language
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (file_id, 1, "audio", "aac", "eng"),
    )
    track_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()

    yield conn, file_id, track_id

    conn.close()


@pytest.fixture
def sample_analysis_result() -> LanguageAnalysisResult:
    """Create a sample analysis result for testing."""
    now = datetime.now(timezone.utc)
    return LanguageAnalysisResult(
        track_id=1,
        file_hash="test_hash_12345",  # pragma: allowlist secret
        primary_language="eng",
        primary_percentage=0.8,
        secondary_languages=(),
        classification=LanguageClassification.MULTI_LANGUAGE,
        segments=(
            LanguageSegment("eng", 0.0, 30.0, 0.95),
            LanguageSegment("eng", 300.0, 330.0, 0.92),
            LanguageSegment("fre", 600.0, 630.0, 0.88),
        ),
        metadata=AnalysisMetadata(
            plugin_name="whisper-local",
            plugin_version="1.0.0",
            model_name="whisper-base",
            sample_positions=(0.0, 300.0, 600.0),
            sample_duration=30.0,
            total_duration=1800.0,
            speech_ratio=0.8,
        ),
        created_at=now,
        updated_at=now,
    )


class TestCreateSegmentsFromSamples:
    """Tests for _create_segments_from_samples helper."""

    def test_creates_segments_for_speech_samples(self) -> None:
        """Test that segments are created for samples with speech."""
        samples = [
            MultiLanguageDetectionResult(
                position=0.0, language="eng", confidence=0.95, has_speech=True
            ),
            MultiLanguageDetectionResult(
                position=300.0, language="fre", confidence=0.88, has_speech=True
            ),
        ]

        segments = _create_segments_from_samples(samples, sample_duration=30.0)

        assert len(segments) == 2
        assert segments[0].language_code == "eng"
        assert segments[0].start_time == 0.0
        assert segments[0].end_time == 30.0
        assert segments[1].language_code == "fre"
        assert segments[1].start_time == 300.0

    def test_skips_samples_without_speech(self) -> None:
        """Test that samples without speech are skipped."""
        samples = [
            MultiLanguageDetectionResult(
                position=0.0, language="eng", confidence=0.95, has_speech=True
            ),
            MultiLanguageDetectionResult(
                position=300.0, language=None, confidence=0.1, has_speech=False
            ),
        ]

        segments = _create_segments_from_samples(samples, sample_duration=30.0)

        assert len(segments) == 1
        assert segments[0].language_code == "eng"

    def test_returns_empty_for_all_no_speech(self) -> None:
        """Test that empty list is returned when no samples have speech."""
        samples = [
            MultiLanguageDetectionResult(
                position=0.0, language=None, confidence=0.1, has_speech=False
            ),
        ]

        segments = _create_segments_from_samples(samples, sample_duration=30.0)

        assert len(segments) == 0


class TestPersistAnalysisResult:
    """Tests for persist_analysis_result function."""

    def test_persists_result_to_database(
        self, db_connection, sample_analysis_result
    ) -> None:
        """Test that analysis result is persisted correctly."""
        conn, file_id, track_id = db_connection

        # Update result with actual track_id
        sample_analysis_result.track_id = track_id

        analysis_id = persist_analysis_result(conn, sample_analysis_result)

        assert analysis_id > 0

        # Verify main record
        cursor = conn.execute(
            "SELECT * FROM language_analysis_results WHERE id = ?", (analysis_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == track_id  # track_id
        assert row[3] == "eng"  # primary_language
        assert row[5] == "MULTI_LANGUAGE"  # classification

    def test_persists_segments(self, db_connection, sample_analysis_result) -> None:
        """Test that segments are persisted correctly."""
        conn, file_id, track_id = db_connection
        sample_analysis_result.track_id = track_id

        analysis_id = persist_analysis_result(conn, sample_analysis_result)

        cursor = conn.execute(
            "SELECT COUNT(*) FROM language_segments WHERE analysis_id = ?",
            (analysis_id,),
        )
        count = cursor.fetchone()[0]
        assert count == 3  # 3 segments in sample_analysis_result

    def test_upsert_updates_existing(
        self, db_connection, sample_analysis_result
    ) -> None:
        """Test that upserting updates existing record."""
        conn, file_id, track_id = db_connection
        sample_analysis_result.track_id = track_id

        # First insert
        analysis_id1 = persist_analysis_result(conn, sample_analysis_result)

        # Modify and upsert
        sample_analysis_result.primary_language = "fre"
        analysis_id2 = persist_analysis_result(conn, sample_analysis_result)

        # Should be same ID (upsert)
        assert analysis_id1 == analysis_id2

        # Verify update
        cursor = conn.execute(
            "SELECT primary_language FROM language_analysis_results WHERE id = ?",
            (analysis_id1,),
        )
        assert cursor.fetchone()[0] == "fre"


class TestGetCachedAnalysis:
    """Tests for get_cached_analysis function."""

    def test_returns_none_when_no_cache(self, db_connection) -> None:
        """Test that None is returned when no cached result exists."""
        conn, file_id, track_id = db_connection

        result = get_cached_analysis(conn, track_id, "somehash")

        assert result is None

    def test_returns_cached_result_when_hash_matches(
        self, db_connection, sample_analysis_result
    ) -> None:
        """Test that cached result is returned when file hash matches."""
        conn, file_id, track_id = db_connection
        sample_analysis_result.track_id = track_id

        persist_analysis_result(conn, sample_analysis_result)

        result = get_cached_analysis(conn, track_id, sample_analysis_result.file_hash)

        assert result is not None
        assert result.primary_language == sample_analysis_result.primary_language
        assert result.classification == sample_analysis_result.classification

    def test_returns_none_when_hash_changed(
        self, db_connection, sample_analysis_result
    ) -> None:
        """Test that None is returned when file hash has changed."""
        conn, file_id, track_id = db_connection
        sample_analysis_result.track_id = track_id

        persist_analysis_result(conn, sample_analysis_result)

        result = get_cached_analysis(conn, track_id, "different_hash")

        assert result is None


class TestInvalidateAnalysisCache:
    """Tests for invalidate_analysis_cache function."""

    def test_deletes_existing_cache(
        self, db_connection, sample_analysis_result
    ) -> None:
        """Test that cached result is deleted."""
        conn, file_id, track_id = db_connection
        sample_analysis_result.track_id = track_id

        persist_analysis_result(conn, sample_analysis_result)

        deleted = invalidate_analysis_cache(conn, track_id)

        assert deleted is True

        # Verify deleted
        result = get_cached_analysis(conn, track_id, sample_analysis_result.file_hash)
        assert result is None

    def test_returns_false_when_no_cache(self, db_connection) -> None:
        """Test that False is returned when no cache exists."""
        conn, file_id, track_id = db_connection

        deleted = invalidate_analysis_cache(conn, track_id)

        assert deleted is False
