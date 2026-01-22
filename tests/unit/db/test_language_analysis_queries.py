"""Tests for get_language_analysis_for_tracks batch query function."""

import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.db.queries import (
    get_language_analysis_for_tracks,
    upsert_language_analysis_result,
)
from vpo.db.schema import create_schema
from vpo.db.types import LanguageAnalysisResultRecord


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_file(conn: sqlite3.Connection, path: str) -> int:
    """Create a file record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO files (
            path, filename, directory, extension, size_bytes,
            container_format, modified_at, scanned_at, scan_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            path,
            path.split("/")[-1],
            "/".join(path.split("/")[:-1]),
            ".mkv",
            1000,
            "matroska",
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            "ok",
        ),
    )
    conn.commit()
    return cursor.lastrowid


def create_track(
    conn: sqlite3.Connection,
    file_id: int,
    track_index: int,
    track_type: str,
    language: str = "eng",
) -> int:
    """Create a track record and return its ID."""
    cursor = conn.execute(
        """
        INSERT INTO tracks (file_id, track_index, track_type, codec, language)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            file_id,
            track_index,
            track_type,
            "aac" if track_type == "audio" else "h264",
            language,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def create_language_analysis(
    conn: sqlite3.Connection,
    track_id: int,
    primary_language: str = "eng",
    primary_percentage: float = 0.85,
    classification: str = "MULTI_LANGUAGE",
) -> int:
    """Create a language analysis record and return its ID."""
    now = datetime.now(timezone.utc).isoformat()
    record = LanguageAnalysisResultRecord(
        id=None,
        track_id=track_id,
        file_hash="hash123",
        primary_language=primary_language,
        primary_percentage=primary_percentage,
        classification=classification,
        analysis_metadata='{"plugin_name": "whisper", "model_name": "base"}',
        created_at=now,
        updated_at=now,
    )
    return upsert_language_analysis_result(conn, record)


class TestGetLanguageAnalysisForTracks:
    """Tests for get_language_analysis_for_tracks batch lookup function."""

    def test_empty_list_returns_empty_dict(self, db_conn):
        """Empty track_ids list returns empty dict without query."""
        result = get_language_analysis_for_tracks(db_conn, [])
        assert result == {}

    def test_single_track_found(self, db_conn):
        """Single track_id lookup returns matching record."""
        file_id = create_file(db_conn, "/media/movies/test.mkv")
        track_id = create_track(db_conn, file_id, 1, "audio", "eng")
        create_language_analysis(db_conn, track_id, "eng", 0.85)

        result = get_language_analysis_for_tracks(db_conn, [track_id])

        assert len(result) == 1
        assert track_id in result
        assert result[track_id].track_id == track_id
        assert result[track_id].primary_language == "eng"
        assert result[track_id].primary_percentage == 0.85

    def test_multiple_tracks_found(self, db_conn):
        """Multiple track_ids return all matching records."""
        file_id = create_file(db_conn, "/media/movies/test.mkv")
        track_ids = []
        for i in range(3):
            track_id = create_track(db_conn, file_id, i + 1, "audio", "eng")
            create_language_analysis(db_conn, track_id, "eng", 0.90 - i * 0.05)
            track_ids.append(track_id)

        result = get_language_analysis_for_tracks(db_conn, track_ids)

        assert len(result) == 3
        for track_id in track_ids:
            assert track_id in result
            assert result[track_id].track_id == track_id

    def test_partial_results(self, db_conn):
        """Returns only tracks with analysis results."""
        file_id = create_file(db_conn, "/media/movies/test.mkv")
        track1 = create_track(db_conn, file_id, 1, "audio", "eng")
        track2 = create_track(db_conn, file_id, 2, "audio", "spa")
        track3 = create_track(db_conn, file_id, 3, "audio", "fre")

        # Only create analysis for track1 and track3
        create_language_analysis(db_conn, track1, "eng", 0.95)
        create_language_analysis(db_conn, track3, "fre", 0.88)

        result = get_language_analysis_for_tracks(db_conn, [track1, track2, track3])

        assert len(result) == 2
        assert track1 in result
        assert track2 not in result
        assert track3 in result

    def test_no_matching_tracks_returns_empty(self, db_conn):
        """Returns empty dict when no tracks have analysis results."""
        file_id = create_file(db_conn, "/media/movies/test.mkv")
        track_id = create_track(db_conn, file_id, 1, "audio", "eng")
        # No analysis created

        result = get_language_analysis_for_tracks(db_conn, [track_id])

        assert result == {}

    def test_nonexistent_track_ids_ignored(self, db_conn):
        """Nonexistent track IDs are silently ignored."""
        result = get_language_analysis_for_tracks(db_conn, [9999, 8888, 7777])
        assert result == {}

    def test_returns_correct_record_fields(self, db_conn):
        """Returned record has all expected fields."""
        file_id = create_file(db_conn, "/media/movies/test.mkv")
        track_id = create_track(db_conn, file_id, 1, "audio", "eng")
        create_language_analysis(db_conn, track_id, "eng", 0.85, "MULTI_LANGUAGE")

        result = get_language_analysis_for_tracks(db_conn, [track_id])
        record = result[track_id]

        assert record.id is not None
        assert record.track_id == track_id
        assert record.file_hash == "hash123"
        assert record.primary_language == "eng"
        assert record.primary_percentage == 0.85
        assert record.classification == "MULTI_LANGUAGE"
        assert record.analysis_metadata is not None
        assert record.created_at is not None
        assert record.updated_at is not None
