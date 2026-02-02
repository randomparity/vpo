"""Integration tests for analyze-language CLI commands.

Tests the database functions used by analyze-language commands.
CLI commands create their own database connection, so we test
the underlying view/query functions directly.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vpo.cli import main
from vpo.db.queries import (
    delete_all_analysis,
    delete_analysis_by_path_prefix,
    insert_file,
    insert_track,
)
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord, TrackRecord
from vpo.db.views import (
    get_analysis_status_summary,
    get_file_analysis_detail,
    get_files_analysis_status,
)


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """Create a database with schema for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    conn.commit()
    return conn


def create_test_file(
    conn: sqlite3.Connection,
    file_id: int,
    path: str,
    filename: str,
) -> int:
    """Create a file record in the database."""
    file = FileRecord(
        id=file_id,
        path=path,
        filename=filename,
        directory=str(Path(path).parent),
        extension=Path(filename).suffix,
        size_bytes=1000000,
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
    language: str = "eng",
) -> int:
    """Create an audio track in the database."""
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
) -> None:
    """Create a language analysis result in the database."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
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


class TestAnalyzeLanguageCliAvailability:
    """Tests for CLI command availability."""

    def test_command_group_help(self, runner):
        """Command group shows help with all subcommands."""
        result = runner.invoke(main, ["analyze-language", "--help"])
        assert result.exit_code == 0
        assert "Analyze and manage multi-language detection results" in result.output
        assert "run" in result.output
        assert "status" in result.output
        assert "clear" in result.output

    def test_clear_requires_path_or_all(self, runner):
        """Clear requires either path argument or --all flag."""
        result = runner.invoke(main, ["analyze-language", "clear"])
        assert result.exit_code == 2
        assert "Specify a PATH or use --all" in result.output


class TestStatusFunctionIntegration:
    """Integration tests for status-related view functions."""

    def test_summary_counts_files_and_tracks(self, db_conn):
        """get_analysis_status_summary counts files and tracks correctly."""
        file_id = create_test_file(db_conn, 1, "/media/movies/movie.mkv", "movie.mkv")
        create_audio_track(db_conn, file_id, 0)
        create_audio_track(db_conn, file_id, 1)
        db_conn.commit()

        summary = get_analysis_status_summary(db_conn)

        assert summary.total_files == 1
        assert summary.total_tracks == 2
        assert summary.pending_tracks == 2
        assert summary.analyzed_tracks == 0

    def test_summary_tracks_analysis_results(self, db_conn):
        """get_analysis_status_summary tracks analyzed vs pending."""
        file_id = create_test_file(db_conn, 1, "/media/movies/movie.mkv", "movie.mkv")
        track1_id = create_audio_track(db_conn, file_id, 0)
        create_audio_track(db_conn, file_id, 1)
        create_analysis_result(db_conn, track1_id)
        db_conn.commit()

        summary = get_analysis_status_summary(db_conn)

        assert summary.total_tracks == 2
        assert summary.analyzed_tracks == 1
        assert summary.pending_tracks == 1

    def test_summary_classification_counts(self, db_conn):
        """get_analysis_status_summary counts classifications."""
        file_id = create_test_file(db_conn, 1, "/media/movies/movie.mkv", "movie.mkv")
        track1_id = create_audio_track(db_conn, file_id, 0)
        track2_id = create_audio_track(db_conn, file_id, 1)
        create_analysis_result(db_conn, track1_id, "SINGLE_LANGUAGE")
        create_analysis_result(db_conn, track2_id, "MULTI_LANGUAGE")
        db_conn.commit()

        summary = get_analysis_status_summary(db_conn)

        assert summary.single_language_count == 1
        assert summary.multi_language_count == 1


class TestClearFunctionIntegration:
    """Integration tests for clear-related query functions."""

    def test_delete_all_clears_results(self, db_conn):
        """delete_all_analysis removes all analysis results."""
        file_id = create_test_file(db_conn, 1, "/media/movies/movie.mkv", "movie.mkv")
        track_id = create_audio_track(db_conn, file_id, 0)
        create_analysis_result(db_conn, track_id)

        # Verify result exists
        cursor = db_conn.execute("SELECT COUNT(*) FROM language_analysis_results")
        assert cursor.fetchone()[0] == 1

        # Delete all
        count = delete_all_analysis(db_conn)

        assert count == 1
        cursor = db_conn.execute("SELECT COUNT(*) FROM language_analysis_results")
        assert cursor.fetchone()[0] == 0

    def test_delete_by_path_prefix_selective(self, db_conn):
        """delete_analysis_by_path_prefix only affects matching files."""
        # File in movies directory
        file1_id = create_test_file(db_conn, 1, "/media/movies/movie.mkv", "movie.mkv")
        track1_id = create_audio_track(db_conn, file1_id, 0)
        create_analysis_result(db_conn, track1_id)

        # File in shows directory
        file2_id = create_test_file(db_conn, 2, "/media/shows/show.mkv", "show.mkv")
        track2_id = create_audio_track(db_conn, file2_id, 0)
        create_analysis_result(db_conn, track2_id)

        # Delete only movies
        count = delete_analysis_by_path_prefix(db_conn, "/media/movies/")

        assert count == 1

        # Verify only shows remains
        cursor = db_conn.execute("SELECT COUNT(*) FROM language_analysis_results")
        assert cursor.fetchone()[0] == 1


class TestWorkflowIntegration:
    """Integration tests for full status→clear workflow."""

    def test_status_reflects_clear(self, db_conn):
        """Summary updates after clearing results."""
        file_id = create_test_file(db_conn, 1, "/media/movies/movie.mkv", "movie.mkv")
        track_id = create_audio_track(db_conn, file_id, 0)
        create_analysis_result(db_conn, track_id)

        # Initial state
        summary = get_analysis_status_summary(db_conn)
        assert summary.analyzed_tracks == 1
        assert summary.pending_tracks == 0

        # Clear results
        delete_all_analysis(db_conn)

        # Verify state updated
        summary = get_analysis_status_summary(db_conn)
        assert summary.analyzed_tracks == 0
        assert summary.pending_tracks == 1

    def test_file_detail_shows_pending_after_clear(self, db_conn):
        """File detail shows pending state after clearing."""
        file_id = create_test_file(db_conn, 1, "/media/movies/movie.mkv", "movie.mkv")
        track_id = create_audio_track(db_conn, file_id, 0)
        create_analysis_result(db_conn, track_id)

        # Initial detail has analysis
        detail = get_file_analysis_detail(db_conn, "/media/movies/movie.mkv")
        assert len(detail) == 1
        assert detail[0].classification == "SINGLE_LANGUAGE"

        # Clear results
        delete_all_analysis(db_conn)

        # Detail shows pending (no classification)
        detail = get_file_analysis_detail(db_conn, "/media/movies/movie.mkv")
        assert len(detail) == 1
        assert detail[0].classification is None

    def test_filtered_status_with_classification(self, db_conn):
        """Filtered status respects classification filter."""
        # File with multi-language track
        file1_id = create_test_file(db_conn, 1, "/media/movies/multi.mkv", "multi.mkv")
        track1_id = create_audio_track(db_conn, file1_id, 0)
        create_analysis_result(db_conn, track1_id, "MULTI_LANGUAGE")

        # File with single-language track
        file2_id = create_test_file(
            db_conn, 2, "/media/movies/single.mkv", "single.mkv"
        )
        track2_id = create_audio_track(db_conn, file2_id, 0)
        create_analysis_result(db_conn, track2_id, "SINGLE_LANGUAGE")

        # Filter to multi-language
        multi_files = get_files_analysis_status(
            db_conn, filter_classification="multi-language"
        )
        assert len(multi_files) == 1
        assert "multi.mkv" in multi_files[0].file_path

        # Filter to single-language
        single_files = get_files_analysis_status(
            db_conn, filter_classification="single-language"
        )
        assert len(single_files) == 1
        assert "single.mkv" in single_files[0].file_path
