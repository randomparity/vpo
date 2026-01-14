"""Tests for language analysis query functions."""

import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.db.queries import (
    delete_all_analysis,
    delete_analysis_by_path_prefix,
    delete_analysis_for_file,
    get_file_ids_by_path_prefix,
    insert_file,
    insert_track,
)
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord, TrackRecord


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_file(
    conn: sqlite3.Connection,
    file_id: int,
    filename: str,
    path: str | None = None,
) -> int:
    """Create a file record and return its ID."""
    file = FileRecord(
        id=file_id,
        path=path or f"/media/{filename}",
        filename=filename,
        directory="/media",
        extension=".mkv",
        size_bytes=1000,
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_hash=f"hash{file_id}",
        container_format="matroska",
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scan_status="ok",
        scan_error=None,
        job_id=None,
        plugin_metadata=None,
    )
    return insert_file(conn, file)


def create_audio_track(
    conn: sqlite3.Connection,
    file_id: int,
    track_index: int,
) -> int:
    """Create an audio track and return its ID."""
    track = TrackRecord(
        id=None,
        file_id=file_id,
        track_index=track_index,
        track_type="audio",
        codec="aac",
        language="eng",
        title=None,
        is_default=track_index == 0,
        is_forced=False,
        channels=2,
        channel_layout="stereo",
        width=None,
        height=None,
        frame_rate=None,
        color_transfer=None,
        color_primaries=None,
        color_space=None,
        color_range=None,
        duration_seconds=3600.0,
    )
    return insert_track(conn, track)


def create_analysis_result(conn: sqlite3.Connection, track_id: int) -> int:
    """Create a language analysis result and return its ID."""
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO language_analysis_results (
            track_id, file_hash, classification, primary_language,
            primary_percentage, analysis_metadata, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            track_id,
            f"hash{track_id}",
            "SINGLE_LANGUAGE",
            "eng",
            0.95,
            None,
            now,
            now,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def count_analysis_results(conn: sqlite3.Connection) -> int:
    """Count total analysis results in database."""
    cursor = conn.execute("SELECT COUNT(*) FROM language_analysis_results")
    return cursor.fetchone()[0]


class TestDeleteAnalysisForFile:
    """Tests for delete_analysis_for_file function."""

    def test_returns_zero_when_no_results(self, db_conn):
        """Returns zero when file has no analysis results."""
        file_id = create_file(db_conn, 1, "movie.mkv")
        create_audio_track(db_conn, file_id, 0)

        result = delete_analysis_for_file(db_conn, file_id)

        assert result == 0

    def test_deletes_single_result(self, db_conn):
        """Deletes single analysis result for file."""
        file_id = create_file(db_conn, 1, "movie.mkv")
        track_id = create_audio_track(db_conn, file_id, 0)
        create_analysis_result(db_conn, track_id)

        assert count_analysis_results(db_conn) == 1

        result = delete_analysis_for_file(db_conn, file_id)

        assert result == 1
        assert count_analysis_results(db_conn) == 0

    def test_deletes_multiple_results(self, db_conn):
        """Deletes all analysis results for file with multiple tracks."""
        file_id = create_file(db_conn, 1, "movie.mkv")
        track1_id = create_audio_track(db_conn, file_id, 0)
        track2_id = create_audio_track(db_conn, file_id, 1)
        create_analysis_result(db_conn, track1_id)
        create_analysis_result(db_conn, track2_id)

        assert count_analysis_results(db_conn) == 2

        result = delete_analysis_for_file(db_conn, file_id)

        assert result == 2
        assert count_analysis_results(db_conn) == 0

    def test_only_deletes_for_specified_file(self, db_conn):
        """Only deletes results for the specified file, not others."""
        # File 1 with analysis
        file1_id = create_file(db_conn, 1, "movie1.mkv")
        track1_id = create_audio_track(db_conn, file1_id, 0)
        create_analysis_result(db_conn, track1_id)

        # File 2 with analysis
        file2_id = create_file(db_conn, 2, "movie2.mkv")
        track2_id = create_audio_track(db_conn, file2_id, 0)
        create_analysis_result(db_conn, track2_id)

        assert count_analysis_results(db_conn) == 2

        result = delete_analysis_for_file(db_conn, file1_id)

        assert result == 1
        assert count_analysis_results(db_conn) == 1


class TestDeleteAllAnalysis:
    """Tests for delete_all_analysis function."""

    def test_returns_zero_when_no_results(self, db_conn):
        """Returns zero when no analysis results exist."""
        result = delete_all_analysis(db_conn)
        assert result == 0

    def test_deletes_all_results(self, db_conn):
        """Deletes all analysis results across all files."""
        # Create multiple files with analysis results
        for i in range(3):
            file_id = create_file(db_conn, i + 1, f"movie{i}.mkv")
            track_id = create_audio_track(db_conn, file_id, 0)
            create_analysis_result(db_conn, track_id)

        assert count_analysis_results(db_conn) == 3

        result = delete_all_analysis(db_conn)

        assert result == 3
        assert count_analysis_results(db_conn) == 0


class TestDeleteAnalysisByPathPrefix:
    """Tests for delete_analysis_by_path_prefix function."""

    def test_returns_zero_when_no_matching_files(self, db_conn):
        """Returns zero when no files match the path prefix."""
        file_id = create_file(db_conn, 1, "movie.mkv", path="/other/path/movie.mkv")
        track_id = create_audio_track(db_conn, file_id, 0)
        create_analysis_result(db_conn, track_id)

        result = delete_analysis_by_path_prefix(db_conn, "/media/movies/")

        assert result == 0
        assert count_analysis_results(db_conn) == 1

    def test_deletes_results_for_matching_files(self, db_conn):
        """Deletes results for files under the path prefix."""
        # File under target path
        file1_id = create_file(db_conn, 1, "movie.mkv", path="/media/movies/movie.mkv")
        track1_id = create_audio_track(db_conn, file1_id, 0)
        create_analysis_result(db_conn, track1_id)

        # File under different path
        file2_id = create_file(db_conn, 2, "show.mkv", path="/media/shows/show.mkv")
        track2_id = create_audio_track(db_conn, file2_id, 0)
        create_analysis_result(db_conn, track2_id)

        assert count_analysis_results(db_conn) == 2

        result = delete_analysis_by_path_prefix(db_conn, "/media/movies/")

        assert result == 1
        assert count_analysis_results(db_conn) == 1

    def test_includes_subdirectories(self, db_conn):
        """Deletes results for files in subdirectories."""
        # File in subdirectory
        file_id = create_file(
            db_conn, 1, "movie.mkv", path="/media/movies/action/movie.mkv"
        )
        track_id = create_audio_track(db_conn, file_id, 0)
        create_analysis_result(db_conn, track_id)

        result = delete_analysis_by_path_prefix(db_conn, "/media/movies/")

        assert result == 1
        assert count_analysis_results(db_conn) == 0


class TestGetFileIdsByPathPrefix:
    """Tests for get_file_ids_by_path_prefix function."""

    def test_returns_empty_list_when_no_matches(self, db_conn):
        """Returns empty list when no files match."""
        create_file(db_conn, 1, "movie.mkv", path="/other/path/movie.mkv")

        result = get_file_ids_by_path_prefix(db_conn, "/media/")

        assert result == []

    def test_returns_matching_file_ids(self, db_conn):
        """Returns IDs of files under the path prefix."""
        file1_id = create_file(
            db_conn, 1, "movie1.mkv", path="/media/movies/movie1.mkv"
        )
        file2_id = create_file(
            db_conn, 2, "movie2.mkv", path="/media/movies/movie2.mkv"
        )
        create_file(db_conn, 3, "show.mkv", path="/other/show.mkv")

        result = get_file_ids_by_path_prefix(db_conn, "/media/movies/")

        assert set(result) == {file1_id, file2_id}

    def test_includes_subdirectories_by_default(self, db_conn):
        """Includes files in subdirectories by default."""
        file1_id = create_file(db_conn, 1, "movie.mkv", path="/media/movies/movie.mkv")
        file2_id = create_file(
            db_conn, 2, "action.mkv", path="/media/movies/action/action.mkv"
        )

        result = get_file_ids_by_path_prefix(db_conn, "/media/movies/")

        assert set(result) == {file1_id, file2_id}

    def test_excludes_subdirectories_when_requested(self, db_conn):
        """Excludes subdirectory files when include_subdirs=False."""
        file1_id = create_file(db_conn, 1, "movie.mkv", path="/media/movies/movie.mkv")
        create_file(db_conn, 2, "action.mkv", path="/media/movies/action/action.mkv")

        result = get_file_ids_by_path_prefix(
            db_conn, "/media/movies/", include_subdirs=False
        )

        assert result == [file1_id]
