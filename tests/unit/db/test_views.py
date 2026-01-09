"""Tests for language analysis view query functions."""

import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.db.queries import insert_file, insert_track
from vpo.db.schema import create_schema
from vpo.db.types import (
    AnalysisStatusSummary,
    FileAnalysisStatus,
    FileRecord,
    TrackAnalysisDetail,
    TrackRecord,
)
from vpo.db.views import (
    get_analysis_status_summary,
    get_file_analysis_detail,
    get_files_analysis_status,
)


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
        path=path or f"/test/path/{filename}",
        filename=filename,
        directory="/test/path",
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
    language: str | None = "eng",
) -> int:
    """Create an audio track and return its ID."""
    track = TrackRecord(
        id=None,
        file_id=file_id,
        track_index=track_index,
        track_type="audio",
        codec="aac",
        language=language,
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


def create_analysis_result(
    conn: sqlite3.Connection,
    track_id: int,
    classification: str = "SINGLE_LANGUAGE",
    primary_language: str = "eng",
    primary_percentage: float = 0.95,
) -> int:
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
            classification,
            primary_language,
            primary_percentage,
            None,
            now,
            now,
        ),
    )
    conn.commit()
    return cursor.lastrowid


class TestGetAnalysisStatusSummary:
    """Tests for get_analysis_status_summary function."""

    def test_returns_zeros_when_no_files(self, db_conn):
        """Returns zero counts when database has no files."""
        result = get_analysis_status_summary(db_conn)

        assert isinstance(result, AnalysisStatusSummary)
        assert result.total_files == 0
        assert result.total_tracks == 0
        assert result.analyzed_tracks == 0
        assert result.pending_tracks == 0
        assert result.multi_language_count == 0
        assert result.single_language_count == 0

    def test_counts_files_with_audio_tracks(self, db_conn):
        """Counts files that have audio tracks."""
        file_id = create_file(db_conn, 1, "movie.mkv")
        create_audio_track(db_conn, file_id, 0)
        create_audio_track(db_conn, file_id, 1)

        result = get_analysis_status_summary(db_conn)

        assert result.total_files == 1
        assert result.total_tracks == 2
        assert result.analyzed_tracks == 0
        assert result.pending_tracks == 2

    def test_counts_analyzed_tracks(self, db_conn):
        """Counts tracks that have analysis results."""
        file_id = create_file(db_conn, 1, "movie.mkv")
        track1_id = create_audio_track(db_conn, file_id, 0)
        create_audio_track(db_conn, file_id, 1)

        # Analyze only the first track
        create_analysis_result(db_conn, track1_id)

        result = get_analysis_status_summary(db_conn)

        assert result.total_tracks == 2
        assert result.analyzed_tracks == 1
        assert result.pending_tracks == 1

    def test_counts_single_language_tracks(self, db_conn):
        """Counts tracks classified as single language."""
        file_id = create_file(db_conn, 1, "movie.mkv")
        track_id = create_audio_track(db_conn, file_id, 0)
        create_analysis_result(db_conn, track_id, classification="SINGLE_LANGUAGE")

        result = get_analysis_status_summary(db_conn)

        assert result.single_language_count == 1
        assert result.multi_language_count == 0

    def test_counts_multi_language_tracks(self, db_conn):
        """Counts tracks classified as multi language."""
        file_id = create_file(db_conn, 1, "movie.mkv")
        track_id = create_audio_track(db_conn, file_id, 0)
        create_analysis_result(db_conn, track_id, classification="MULTI_LANGUAGE")

        result = get_analysis_status_summary(db_conn)

        assert result.single_language_count == 0
        assert result.multi_language_count == 1

    def test_counts_multiple_files(self, db_conn):
        """Correctly counts across multiple files."""
        # File 1 with 2 analyzed tracks
        file1_id = create_file(db_conn, 1, "movie1.mkv")
        track1_id = create_audio_track(db_conn, file1_id, 0)
        track2_id = create_audio_track(db_conn, file1_id, 1)
        create_analysis_result(db_conn, track1_id, classification="SINGLE_LANGUAGE")
        create_analysis_result(db_conn, track2_id, classification="MULTI_LANGUAGE")

        # File 2 with 1 pending track
        file2_id = create_file(db_conn, 2, "movie2.mkv")
        create_audio_track(db_conn, file2_id, 0)

        result = get_analysis_status_summary(db_conn)

        assert result.total_files == 2
        assert result.total_tracks == 3
        assert result.analyzed_tracks == 2
        assert result.pending_tracks == 1
        assert result.single_language_count == 1
        assert result.multi_language_count == 1


class TestGetFilesAnalysisStatus:
    """Tests for get_files_analysis_status function."""

    def test_returns_empty_list_when_no_files(self, db_conn):
        """Returns empty list when database has no files with audio."""
        result = get_files_analysis_status(db_conn)
        assert result == []

    def test_returns_file_with_analysis_counts(self, db_conn):
        """Returns file analysis status with counts."""
        file_id = create_file(db_conn, 1, "movie.mkv", path="/media/movie.mkv")
        track1_id = create_audio_track(db_conn, file_id, 0)
        create_audio_track(db_conn, file_id, 1)
        create_analysis_result(db_conn, track1_id)

        result = get_files_analysis_status(db_conn)

        assert len(result) == 1
        assert isinstance(result[0], FileAnalysisStatus)
        assert result[0].file_id == file_id
        assert result[0].file_path == "/media/movie.mkv"
        assert result[0].track_count == 2
        assert result[0].analyzed_count == 1

    def test_filters_multi_language(self, db_conn):
        """Filters to files with multi-language tracks."""
        # File with multi-language track
        file1_id = create_file(db_conn, 1, "multi.mkv")
        track1_id = create_audio_track(db_conn, file1_id, 0)
        create_analysis_result(db_conn, track1_id, classification="MULTI_LANGUAGE")

        # File with single-language track
        file2_id = create_file(db_conn, 2, "single.mkv")
        track2_id = create_audio_track(db_conn, file2_id, 0)
        create_analysis_result(db_conn, track2_id, classification="SINGLE_LANGUAGE")

        result = get_files_analysis_status(
            db_conn, filter_classification="multi-language"
        )

        assert len(result) == 1
        assert result[0].file_id == file1_id

    def test_filters_pending(self, db_conn):
        """Filters to files with pending (unanalyzed) tracks."""
        # File with analyzed track
        file1_id = create_file(db_conn, 1, "analyzed.mkv")
        track1_id = create_audio_track(db_conn, file1_id, 0)
        create_analysis_result(db_conn, track1_id)

        # File with pending track
        file2_id = create_file(db_conn, 2, "pending.mkv")
        create_audio_track(db_conn, file2_id, 0)

        result = get_files_analysis_status(db_conn, filter_classification="pending")

        assert len(result) == 1
        assert result[0].file_id == file2_id

    def test_respects_limit(self, db_conn):
        """Respects the limit parameter."""
        for i in range(5):
            file_id = create_file(db_conn, i + 1, f"movie{i}.mkv")
            create_audio_track(db_conn, file_id, 0)

        result = get_files_analysis_status(db_conn, limit=3)

        assert len(result) == 3


class TestGetFileAnalysisDetail:
    """Tests for get_file_analysis_detail function."""

    def test_returns_none_for_nonexistent_file(self, db_conn):
        """Returns None when file doesn't exist."""
        result = get_file_analysis_detail(db_conn, "/nonexistent/path.mkv")
        assert result is None

    def test_returns_empty_list_for_file_without_audio(self, db_conn):
        """Returns empty list for file with no audio tracks."""
        create_file(db_conn, 1, "video-only.mkv", path="/test/video-only.mkv")

        result = get_file_analysis_detail(db_conn, "/test/video-only.mkv")

        # File exists but has no audio tracks - should return empty list
        assert result == []

    def test_returns_track_details_with_analysis(self, db_conn):
        """Returns detailed analysis for analyzed tracks."""
        file_id = create_file(db_conn, 1, "movie.mkv", path="/test/movie.mkv")
        track_id = create_audio_track(db_conn, file_id, 0, language="eng")
        create_analysis_result(
            db_conn,
            track_id,
            classification="SINGLE_LANGUAGE",
            primary_language="eng",
            primary_percentage=0.985,
        )

        result = get_file_analysis_detail(db_conn, "/test/movie.mkv")

        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], TrackAnalysisDetail)
        assert result[0].track_id == track_id
        assert result[0].track_index == 0
        assert result[0].language == "eng"
        assert result[0].classification == "SINGLE_LANGUAGE"
        assert result[0].primary_language == "eng"
        assert result[0].primary_percentage == 0.985

    def test_returns_pending_track_with_nulls(self, db_conn):
        """Returns track with null analysis fields when not analyzed."""
        file_id = create_file(db_conn, 1, "pending.mkv", path="/test/pending.mkv")
        track_id = create_audio_track(db_conn, file_id, 0, language="ger")

        result = get_file_analysis_detail(db_conn, "/test/pending.mkv")

        assert result is not None
        assert len(result) == 1
        assert result[0].track_id == track_id
        assert result[0].language == "ger"
        # Analysis fields should be None for pending tracks (no analysis done)
        assert result[0].classification is None
        assert result[0].primary_language is None
        assert result[0].primary_percentage == 0.0
