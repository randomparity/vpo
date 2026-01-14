"""Unit tests for transcription database operations."""

import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.db.models import (
    FileRecord,
    TrackRecord,
    TranscriptionResultRecord,
    delete_transcription_results_for_file,
    get_transcription_result,
    insert_file,
    insert_track,
    upsert_transcription_result,
)
from vpo.db.schema import create_schema


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema for testing."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_file(db_conn):
    """Create a sample file record and return its ID."""
    record = FileRecord(
        id=None,
        path="/test/movie.mkv",
        filename="movie.mkv",
        directory="/test",
        extension=".mkv",
        size_bytes=1000000,
        modified_at="2025-01-15T10:00:00+00:00",
        content_hash="abc123",
        container_format="matroska",
        scanned_at="2025-01-15T10:30:00+00:00",
        scan_status="ok",
        scan_error=None,
    )
    return insert_file(db_conn, record)


@pytest.fixture
def sample_track(db_conn, sample_file):
    """Create a sample audio track and return its ID."""
    record = TrackRecord(
        id=None,
        file_id=sample_file,
        track_index=1,
        track_type="audio",
        codec="aac",
        language="und",
        title="Main Audio",
        is_default=True,
        is_forced=False,
        channels=2,
        channel_layout="stereo",
    )
    return insert_track(db_conn, record)


class TestUpsertTranscriptionResult:
    """Tests for upsert_transcription_result function."""

    def test_insert_new_result(self, db_conn, sample_track):
        """Test inserting a new transcription result."""
        now = datetime.now(timezone.utc).isoformat()
        record = TranscriptionResultRecord(
            id=None,
            track_id=sample_track,
            detected_language="en",
            confidence_score=0.95,
            track_type="main",
            transcript_sample="Hello world...",
            plugin_name="whisper-local",
            created_at=now,
            updated_at=now,
        )

        result_id = upsert_transcription_result(db_conn, record)

        assert result_id is not None
        assert result_id > 0

        # Verify record was inserted
        stored = get_transcription_result(db_conn, sample_track)
        assert stored is not None
        assert stored.id == result_id
        assert stored.detected_language == "en"
        assert stored.confidence_score == 0.95

    def test_update_existing_result(self, db_conn, sample_track):
        """Test updating an existing transcription result."""
        created_at = "2025-01-15T10:00:00+00:00"
        updated_at_1 = "2025-01-15T10:30:00+00:00"
        updated_at_2 = "2025-01-15T11:00:00+00:00"

        # Insert initial result
        record1 = TranscriptionResultRecord(
            id=None,
            track_id=sample_track,
            detected_language="en",
            confidence_score=0.90,
            track_type="main",
            transcript_sample="Initial...",
            plugin_name="whisper-local",
            created_at=created_at,
            updated_at=updated_at_1,
        )
        id1 = upsert_transcription_result(db_conn, record1)

        # Update with new result
        record2 = TranscriptionResultRecord(
            id=None,
            track_id=sample_track,
            detected_language="fr",  # Changed
            confidence_score=0.95,  # Changed
            track_type="main",
            transcript_sample="Updated...",  # Changed
            plugin_name="whisper-local-v2",  # Changed
            created_at=created_at,  # Should be preserved
            updated_at=updated_at_2,
        )
        id2 = upsert_transcription_result(db_conn, record2)

        # Should update same record
        assert id2 == id1

        # Verify updated values
        stored = get_transcription_result(db_conn, sample_track)
        assert stored.detected_language == "fr"
        assert stored.confidence_score == 0.95
        assert stored.transcript_sample == "Updated..."
        assert stored.plugin_name == "whisper-local-v2"
        assert stored.updated_at == updated_at_2

    def test_result_with_none_language(self, db_conn, sample_track):
        """Test inserting result with no detected language."""
        now = datetime.now(timezone.utc).isoformat()
        record = TranscriptionResultRecord(
            id=None,
            track_id=sample_track,
            detected_language=None,
            confidence_score=0.0,
            track_type="main",
            transcript_sample=None,
            plugin_name="test-plugin",
            created_at=now,
            updated_at=now,
        )

        upsert_transcription_result(db_conn, record)
        stored = get_transcription_result(db_conn, sample_track)

        assert stored.detected_language is None
        assert stored.transcript_sample is None


class TestGetTranscriptionResult:
    """Tests for get_transcription_result function."""

    def test_get_existing_result(self, db_conn, sample_track):
        """Test retrieving an existing transcription result."""
        now = datetime.now(timezone.utc).isoformat()
        record = TranscriptionResultRecord(
            id=None,
            track_id=sample_track,
            detected_language="de",
            confidence_score=0.88,
            track_type="commentary",
            transcript_sample="Guten Tag...",
            plugin_name="whisper-local",
            created_at=now,
            updated_at=now,
        )
        upsert_transcription_result(db_conn, record)

        result = get_transcription_result(db_conn, sample_track)

        assert result is not None
        assert result.track_id == sample_track
        assert result.detected_language == "de"
        assert result.confidence_score == 0.88
        assert result.track_type == "commentary"
        assert result.transcript_sample == "Guten Tag..."
        assert result.plugin_name == "whisper-local"

    def test_get_nonexistent_result(self, db_conn):
        """Test retrieving a result for a track that doesn't exist."""
        result = get_transcription_result(db_conn, 99999)
        assert result is None

    def test_get_result_no_transcription_yet(self, db_conn, sample_track):
        """Test retrieving result for track without transcription."""
        result = get_transcription_result(db_conn, sample_track)
        assert result is None


class TestDeleteTranscriptionResultsForFile:
    """Tests for delete_transcription_results_for_file function."""

    def test_delete_results_for_file(self, db_conn, sample_file):
        """Test deleting all transcription results for a file."""
        # Create multiple tracks for the file
        track_ids = []
        for i in range(3):
            record = TrackRecord(
                id=None,
                file_id=sample_file,
                track_index=i,
                track_type="audio",
                codec="aac",
                language="und",
                title=f"Audio {i}",
                is_default=i == 0,
                is_forced=False,
            )
            track_ids.append(insert_track(db_conn, record))

        # Create transcription results for each track
        now = datetime.now(timezone.utc).isoformat()
        for track_id in track_ids:
            record = TranscriptionResultRecord(
                id=None,
                track_id=track_id,
                detected_language="en",
                confidence_score=0.9,
                track_type="main",
                transcript_sample=None,
                plugin_name="test",
                created_at=now,
                updated_at=now,
            )
            upsert_transcription_result(db_conn, record)

        # Verify results exist
        for track_id in track_ids:
            assert get_transcription_result(db_conn, track_id) is not None

        # Delete all results for file
        deleted_count = delete_transcription_results_for_file(db_conn, sample_file)

        assert deleted_count == 3

        # Verify results are gone
        for track_id in track_ids:
            assert get_transcription_result(db_conn, track_id) is None

    def test_delete_no_results(self, db_conn, sample_file):
        """Test deleting results when none exist."""
        deleted_count = delete_transcription_results_for_file(db_conn, sample_file)
        assert deleted_count == 0

    def test_delete_only_for_specified_file(self, db_conn):
        """Test that only results for specified file are deleted."""
        # Create two files with tracks
        now = datetime.now(timezone.utc).isoformat()

        file1 = FileRecord(
            id=None,
            path="/test/file1.mkv",
            filename="file1.mkv",
            directory="/test",
            extension=".mkv",
            size_bytes=1000,
            modified_at=now,
            content_hash="hash1",
            container_format="matroska",
            scanned_at=now,
            scan_status="ok",
            scan_error=None,
        )
        file1_id = insert_file(db_conn, file1)

        file2 = FileRecord(
            id=None,
            path="/test/file2.mkv",
            filename="file2.mkv",
            directory="/test",
            extension=".mkv",
            size_bytes=1000,
            modified_at=now,
            content_hash="hash2",
            container_format="matroska",
            scanned_at=now,
            scan_status="ok",
            scan_error=None,
        )
        file2_id = insert_file(db_conn, file2)

        # Create track for each file
        track1 = TrackRecord(
            id=None,
            file_id=file1_id,
            track_index=0,
            track_type="audio",
            codec="aac",
            language="und",
            title="Audio",
            is_default=True,
            is_forced=False,
        )
        track1_id = insert_track(db_conn, track1)

        track2 = TrackRecord(
            id=None,
            file_id=file2_id,
            track_index=0,
            track_type="audio",
            codec="aac",
            language="und",
            title="Audio",
            is_default=True,
            is_forced=False,
        )
        track2_id = insert_track(db_conn, track2)

        # Create transcription results for both
        for track_id in [track1_id, track2_id]:
            record = TranscriptionResultRecord(
                id=None,
                track_id=track_id,
                detected_language="en",
                confidence_score=0.9,
                track_type="main",
                transcript_sample=None,
                plugin_name="test",
                created_at=now,
                updated_at=now,
            )
            upsert_transcription_result(db_conn, record)

        # Delete only for file1
        delete_transcription_results_for_file(db_conn, file1_id)

        # Verify file1 result is gone, file2 result remains
        assert get_transcription_result(db_conn, track1_id) is None
        assert get_transcription_result(db_conn, track2_id) is not None


class TestTrackClassificationConstraint:
    """Tests for track_type constraint in database."""

    def test_valid_track_types(self, db_conn, sample_track):
        """Test that valid track types are accepted."""
        now = datetime.now(timezone.utc).isoformat()

        for track_type in ["main", "commentary", "alternate"]:
            # Delete existing result first
            db_conn.execute(
                "DELETE FROM transcription_results WHERE track_id = ?",
                (sample_track,),
            )
            db_conn.commit()

            record = TranscriptionResultRecord(
                id=None,
                track_id=sample_track,
                detected_language="en",
                confidence_score=0.9,
                track_type=track_type,
                transcript_sample=None,
                plugin_name="test",
                created_at=now,
                updated_at=now,
            )
            result_id = upsert_transcription_result(db_conn, record)
            assert result_id is not None

    def test_invalid_track_type(self, db_conn, sample_track):
        """Test that invalid track type raises error."""
        now = datetime.now(timezone.utc).isoformat()

        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                """
                INSERT INTO transcription_results (
                    track_id, detected_language, confidence_score, track_type,
                    transcript_sample, plugin_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_track,
                    "en",
                    0.9,
                    "invalid_type",
                    None,
                    "test",
                    now,
                    now,
                ),
            )


class TestCascadeDelete:
    """Tests for CASCADE DELETE behavior on transcription_results."""

    def test_cascade_delete_when_track_deleted(self, db_conn, sample_file):
        """Test that transcription results are deleted when track is deleted."""
        # Create a track
        track_record = TrackRecord(
            id=None,
            file_id=sample_file,
            track_index=0,
            track_type="audio",
            codec="aac",
            language="und",
            title="Test Audio",
            is_default=True,
            is_forced=False,
        )
        track_id = insert_track(db_conn, track_record)

        # Create a transcription result for this track
        now = datetime.now(timezone.utc).isoformat()
        transcription_record = TranscriptionResultRecord(
            id=None,
            track_id=track_id,
            detected_language="en",
            confidence_score=0.95,
            track_type="main",
            transcript_sample="Hello world...",
            plugin_name="whisper-local",
            created_at=now,
            updated_at=now,
        )
        upsert_transcription_result(db_conn, transcription_record)

        # Verify transcription result exists
        result = get_transcription_result(db_conn, track_id)
        assert result is not None
        assert result.detected_language == "en"

        # Delete the track
        db_conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        db_conn.commit()

        # Verify transcription result was cascade deleted
        result = get_transcription_result(db_conn, track_id)
        assert result is None

    def test_cascade_delete_when_file_deleted(self, db_conn):
        """Test transcription results deleted when parent file is deleted."""
        # Create a file
        now = datetime.now(timezone.utc).isoformat()
        file_record = FileRecord(
            id=None,
            path="/test/cascade_test.mkv",
            filename="cascade_test.mkv",
            directory="/test",
            extension=".mkv",
            size_bytes=1000000,
            modified_at=now,
            content_hash="cascade123",
            container_format="matroska",
            scanned_at=now,
            scan_status="ok",
            scan_error=None,
        )
        file_id = insert_file(db_conn, file_record)

        # Create a track for this file
        track_record = TrackRecord(
            id=None,
            file_id=file_id,
            track_index=0,
            track_type="audio",
            codec="aac",
            language="und",
            title="Test Audio",
            is_default=True,
            is_forced=False,
        )
        track_id = insert_track(db_conn, track_record)

        # Create a transcription result
        transcription_record = TranscriptionResultRecord(
            id=None,
            track_id=track_id,
            detected_language="fr",
            confidence_score=0.88,
            track_type="main",
            transcript_sample="Bonjour...",
            plugin_name="whisper-local",
            created_at=now,
            updated_at=now,
        )
        upsert_transcription_result(db_conn, transcription_record)

        # Verify transcription result exists
        result = get_transcription_result(db_conn, track_id)
        assert result is not None

        # Delete the file (should cascade to tracks, then to transcription_results)
        db_conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        db_conn.commit()

        # Verify transcription result was cascade deleted
        result = get_transcription_result(db_conn, track_id)
        assert result is None


class TestConfidenceConstraint:
    """Tests for confidence_score constraint in database."""

    def test_confidence_below_zero(self, db_conn, sample_track):
        """Test that confidence below 0 raises error."""
        now = datetime.now(timezone.utc).isoformat()

        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                """
                INSERT INTO transcription_results (
                    track_id, detected_language, confidence_score, track_type,
                    transcript_sample, plugin_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sample_track, "en", -0.1, "main", None, "test", now, now),
            )

    def test_confidence_above_one(self, db_conn, sample_track):
        """Test that confidence above 1 raises error."""
        now = datetime.now(timezone.utc).isoformat()

        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                """
                INSERT INTO transcription_results (
                    track_id, detected_language, confidence_score, track_type,
                    transcript_sample, plugin_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sample_track, "en", 1.5, "main", None, "test", now, now),
            )
