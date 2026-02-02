"""Tests for language analysis view query functions."""

import sqlite3
from datetime import datetime, timezone

from vpo.db.types import (
    AnalysisStatusSummary,
    FileAnalysisStatus,
    TrackAnalysisDetail,
)
from vpo.db.views import (
    get_analysis_status_summary,
    get_file_analysis_detail,
    get_files_analysis_status,
)


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

    def test_counts_files_with_audio_tracks(
        self, db_conn, insert_test_file, insert_audio_track
    ):
        """Counts files that have audio tracks."""
        file_id = insert_test_file(id=1, path="/test/path/movie.mkv")
        insert_audio_track(file_id=file_id)
        insert_audio_track(file_id=file_id, track_index=1, is_default=False)

        result = get_analysis_status_summary(db_conn)

        assert result.total_files == 1
        assert result.total_tracks == 2
        assert result.analyzed_tracks == 0
        assert result.pending_tracks == 2

    def test_counts_analyzed_tracks(
        self, db_conn, insert_test_file, insert_audio_track
    ):
        """Counts tracks that have analysis results."""
        file_id = insert_test_file(id=1, path="/test/path/movie.mkv")
        track1_id = insert_audio_track(file_id=file_id)
        insert_audio_track(file_id=file_id, track_index=1, is_default=False)

        # Analyze only the first track
        create_analysis_result(db_conn, track1_id)

        result = get_analysis_status_summary(db_conn)

        assert result.total_tracks == 2
        assert result.analyzed_tracks == 1
        assert result.pending_tracks == 1

    def test_counts_single_language_tracks(
        self, db_conn, insert_test_file, insert_audio_track
    ):
        """Counts tracks classified as single language."""
        file_id = insert_test_file(id=1, path="/test/path/movie.mkv")
        track_id = insert_audio_track(file_id=file_id)
        create_analysis_result(db_conn, track_id, classification="SINGLE_LANGUAGE")

        result = get_analysis_status_summary(db_conn)

        assert result.single_language_count == 1
        assert result.multi_language_count == 0

    def test_counts_multi_language_tracks(
        self, db_conn, insert_test_file, insert_audio_track
    ):
        """Counts tracks classified as multi language."""
        file_id = insert_test_file(id=1, path="/test/path/movie.mkv")
        track_id = insert_audio_track(file_id=file_id)
        create_analysis_result(db_conn, track_id, classification="MULTI_LANGUAGE")

        result = get_analysis_status_summary(db_conn)

        assert result.single_language_count == 0
        assert result.multi_language_count == 1

    def test_counts_multiple_files(self, db_conn, insert_test_file, insert_audio_track):
        """Correctly counts across multiple files."""
        # File 1 with 2 analyzed tracks
        file1_id = insert_test_file(id=1, path="/test/path/movie1.mkv")
        track1_id = insert_audio_track(file_id=file1_id)
        track2_id = insert_audio_track(
            file_id=file1_id, track_index=1, is_default=False
        )
        create_analysis_result(db_conn, track1_id, classification="SINGLE_LANGUAGE")
        create_analysis_result(db_conn, track2_id, classification="MULTI_LANGUAGE")

        # File 2 with 1 pending track
        file2_id = insert_test_file(id=2, path="/test/path/movie2.mkv")
        insert_audio_track(file_id=file2_id)

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

    def test_returns_file_with_analysis_counts(
        self, db_conn, insert_test_file, insert_audio_track
    ):
        """Returns file analysis status with counts."""
        file_id = insert_test_file(id=1, path="/media/movie.mkv")
        track1_id = insert_audio_track(file_id=file_id)
        insert_audio_track(file_id=file_id, track_index=1, is_default=False)
        create_analysis_result(db_conn, track1_id)

        result = get_files_analysis_status(db_conn)

        assert len(result) == 1
        assert isinstance(result[0], FileAnalysisStatus)
        assert result[0].file_id == file_id
        assert result[0].file_path == "/media/movie.mkv"
        assert result[0].track_count == 2
        assert result[0].analyzed_count == 1

    def test_filters_multi_language(
        self, db_conn, insert_test_file, insert_audio_track
    ):
        """Filters to files with multi-language tracks."""
        # File with multi-language track
        file1_id = insert_test_file(id=1, path="/test/path/multi.mkv")
        track1_id = insert_audio_track(file_id=file1_id)
        create_analysis_result(db_conn, track1_id, classification="MULTI_LANGUAGE")

        # File with single-language track
        file2_id = insert_test_file(id=2, path="/test/path/single.mkv")
        track2_id = insert_audio_track(file_id=file2_id)
        create_analysis_result(db_conn, track2_id, classification="SINGLE_LANGUAGE")

        result = get_files_analysis_status(
            db_conn, filter_classification="multi-language"
        )

        assert len(result) == 1
        assert result[0].file_id == file1_id

    def test_filters_pending(self, db_conn, insert_test_file, insert_audio_track):
        """Filters to files with pending (unanalyzed) tracks."""
        # File with analyzed track
        file1_id = insert_test_file(id=1, path="/test/path/analyzed.mkv")
        track1_id = insert_audio_track(file_id=file1_id)
        create_analysis_result(db_conn, track1_id)

        # File with pending track
        file2_id = insert_test_file(id=2, path="/test/path/pending.mkv")
        insert_audio_track(file_id=file2_id)

        result = get_files_analysis_status(db_conn, filter_classification="pending")

        assert len(result) == 1
        assert result[0].file_id == file2_id

    def test_respects_limit(self, db_conn, insert_test_file, insert_audio_track):
        """Respects the limit parameter."""
        for i in range(5):
            file_id = insert_test_file(
                id=i + 1,
                path=f"/test/path/movie{i}.mkv",
            )
            insert_audio_track(file_id=file_id)

        result = get_files_analysis_status(db_conn, limit=3)

        assert len(result) == 3


class TestGetFileAnalysisDetail:
    """Tests for get_file_analysis_detail function."""

    def test_returns_none_for_nonexistent_file(self, db_conn):
        """Returns None when file doesn't exist."""
        result = get_file_analysis_detail(db_conn, "/nonexistent/path.mkv")
        assert result is None

    def test_returns_empty_list_for_file_without_audio(self, db_conn, insert_test_file):
        """Returns empty list for file with no audio tracks."""
        insert_test_file(id=1, path="/test/video-only.mkv")

        result = get_file_analysis_detail(db_conn, "/test/video-only.mkv")

        # File exists but has no audio tracks - should return empty list
        assert result == []

    def test_returns_track_details_with_analysis(
        self, db_conn, insert_test_file, insert_audio_track
    ):
        """Returns detailed analysis for analyzed tracks."""
        file_id = insert_test_file(id=1, path="/test/movie.mkv")
        track_id = insert_audio_track(file_id=file_id)
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

    def test_returns_pending_track_with_nulls(
        self, db_conn, insert_test_file, insert_audio_track
    ):
        """Returns track with null analysis fields when not analyzed."""
        file_id = insert_test_file(id=1, path="/test/pending.mkv")
        track_id = insert_audio_track(file_id=file_id, language="ger")

        result = get_file_analysis_detail(db_conn, "/test/pending.mkv")

        assert result is not None
        assert len(result) == 1
        assert result[0].track_id == track_id
        assert result[0].language == "ger"
        # Analysis fields should be None for pending tracks (no analysis done)
        assert result[0].classification is None
        assert result[0].primary_language is None
        assert result[0].primary_percentage == 0.0
