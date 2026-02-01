"""Tests for library info and maintenance view queries."""

import sqlite3

import pytest

from vpo.db.maintenance import run_integrity_check, run_optimize
from vpo.db.queries import insert_file, insert_track
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord, TrackRecord
from vpo.db.views.library_info import (
    get_duplicate_files,
    get_library_info,
)


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    yield conn
    conn.close()


def _insert_file(
    conn, file_id, path, scan_status="ok", size_bytes=1000, content_hash=None
):
    """Insert a test file record."""
    record = FileRecord(
        id=file_id,
        path=path,
        filename=path.split("/")[-1],
        directory="/media",
        extension=".mkv",
        size_bytes=size_bytes,
        modified_at="2025-01-15T08:30:00Z",
        content_hash=content_hash,
        container_format="mkv",
        scanned_at="2025-01-15T08:30:00Z",
        scan_status=scan_status,
        scan_error=None,
    )
    return insert_file(conn, record)


def _insert_track(conn, file_id, track_index, track_type, codec="h264"):
    """Insert a test track record."""
    record = TrackRecord(
        id=None,
        file_id=file_id,
        track_index=track_index,
        track_type=track_type,
        codec=codec,
        language=None,
        title=None,
        is_default=False,
        is_forced=False,
    )
    return insert_track(conn, record)


class TestGetLibraryInfo:
    """Tests for get_library_info."""

    def test_empty_library(self, db_conn):
        info = get_library_info(db_conn)
        assert info.total_files == 0
        assert info.files_ok == 0
        assert info.files_missing == 0
        assert info.files_error == 0
        assert info.files_pending == 0
        assert info.total_size_bytes == 0
        assert info.video_tracks == 0
        assert info.audio_tracks == 0
        assert info.subtitle_tracks == 0
        assert info.attachment_tracks == 0
        assert info.schema_version > 0

    def test_file_counts_by_status(self, db_conn):
        _insert_file(db_conn, 1, "/media/ok1.mkv", scan_status="ok")
        _insert_file(db_conn, 2, "/media/ok2.mkv", scan_status="ok")
        _insert_file(db_conn, 3, "/media/missing.mkv", scan_status="missing")
        _insert_file(db_conn, 4, "/media/error.mkv", scan_status="error")

        info = get_library_info(db_conn)
        assert info.total_files == 4
        assert info.files_ok == 2
        assert info.files_missing == 1
        assert info.files_error == 1
        assert info.files_pending == 0

    def test_total_size(self, db_conn):
        _insert_file(db_conn, 1, "/media/a.mkv", size_bytes=1000)
        _insert_file(db_conn, 2, "/media/b.mkv", size_bytes=2000)

        info = get_library_info(db_conn)
        assert info.total_size_bytes == 3000

    def test_track_counts(self, db_conn):
        fid = _insert_file(db_conn, 1, "/media/a.mkv")
        _insert_track(db_conn, fid, 0, "video")
        _insert_track(db_conn, fid, 1, "audio", codec="aac")
        _insert_track(db_conn, fid, 2, "audio", codec="ac3")
        _insert_track(db_conn, fid, 3, "subtitle", codec="srt")

        info = get_library_info(db_conn)
        assert info.video_tracks == 1
        assert info.audio_tracks == 2
        assert info.subtitle_tracks == 1
        assert info.attachment_tracks == 0

    def test_db_pragmas(self, db_conn):
        info = get_library_info(db_conn)
        assert info.db_page_size > 0
        assert info.db_page_count > 0
        # In-memory DB size is derived from page_size * page_count
        assert info.db_size_bytes == info.db_page_size * info.db_page_count

    def test_missing_schema_version_defaults_to_zero(self, db_conn):
        """Missing schema_version row in _meta should default to 0."""
        db_conn.execute("DELETE FROM _meta WHERE key = 'schema_version'")
        info = get_library_info(db_conn)
        assert info.schema_version == 0

    def test_pending_scan_status_counted(self, db_conn):
        """Files with scan_status='pending' should be counted."""
        _insert_file(db_conn, 1, "/media/pending.mkv", scan_status="pending")
        _insert_file(db_conn, 2, "/media/ok.mkv", scan_status="ok")

        info = get_library_info(db_conn)
        assert info.files_pending == 1
        assert info.total_files == 2


class TestGetDuplicateFiles:
    """Tests for get_duplicate_files."""

    def test_no_duplicates(self, db_conn):
        _insert_file(db_conn, 1, "/media/a.mkv", content_hash="hash_a")
        _insert_file(db_conn, 2, "/media/b.mkv", content_hash="hash_b")

        groups = get_duplicate_files(db_conn)
        assert groups == []

    def test_finds_duplicates(self, db_conn):
        _insert_file(
            db_conn, 1, "/media/a.mkv", content_hash="hash_dup", size_bytes=1000
        )
        _insert_file(
            db_conn, 2, "/media/b.mkv", content_hash="hash_dup", size_bytes=1000
        )
        _insert_file(db_conn, 3, "/media/c.mkv", content_hash="hash_unique")

        groups = get_duplicate_files(db_conn)
        assert len(groups) == 1
        assert groups[0].content_hash == "hash_dup"
        assert groups[0].file_count == 2
        assert groups[0].total_size_bytes == 2000
        assert len(groups[0].paths) == 2

    def test_excludes_null_hashes(self, db_conn):
        _insert_file(db_conn, 1, "/media/a.mkv", content_hash=None)
        _insert_file(db_conn, 2, "/media/b.mkv", content_hash=None)

        groups = get_duplicate_files(db_conn)
        assert groups == []

    def test_excludes_empty_string_hashes(self, db_conn):
        """Empty-string content_hash should be excluded like NULL."""
        _insert_file(db_conn, 1, "/media/a.mkv", content_hash="")
        _insert_file(db_conn, 2, "/media/b.mkv", content_hash="")

        groups = get_duplicate_files(db_conn)
        assert groups == []

    def test_respects_limit(self, db_conn):
        # Create two duplicate groups
        _insert_file(db_conn, 1, "/media/a1.mkv", content_hash="h1", size_bytes=100)
        _insert_file(db_conn, 2, "/media/a2.mkv", content_hash="h1", size_bytes=100)
        _insert_file(db_conn, 3, "/media/b1.mkv", content_hash="h2", size_bytes=200)
        _insert_file(db_conn, 4, "/media/b2.mkv", content_hash="h2", size_bytes=200)

        groups = get_duplicate_files(db_conn, limit=1)
        assert len(groups) == 1

    def test_negative_limit_clamped(self, db_conn):
        """Negative limit should be clamped to 1."""
        _insert_file(db_conn, 1, "/media/a1.mkv", content_hash="h1", size_bytes=100)
        _insert_file(db_conn, 2, "/media/a2.mkv", content_hash="h1", size_bytes=100)

        groups = get_duplicate_files(db_conn, limit=-5)
        # Should still return results (clamped to 1)
        assert len(groups) == 1

    def test_zero_limit_clamped(self, db_conn):
        """Zero limit should be clamped to 1."""
        _insert_file(db_conn, 1, "/media/a1.mkv", content_hash="h1", size_bytes=100)
        _insert_file(db_conn, 2, "/media/a2.mkv", content_hash="h1", size_bytes=100)

        groups = get_duplicate_files(db_conn, limit=0)
        assert len(groups) == 1

    def test_min_group_size(self, db_conn):
        # Create a group of 3
        _insert_file(db_conn, 1, "/media/a1.mkv", content_hash="h1", size_bytes=100)
        _insert_file(db_conn, 2, "/media/a2.mkv", content_hash="h1", size_bytes=100)
        _insert_file(db_conn, 3, "/media/a3.mkv", content_hash="h1", size_bytes=100)
        # Create a group of 2
        _insert_file(db_conn, 4, "/media/b1.mkv", content_hash="h2", size_bytes=200)
        _insert_file(db_conn, 5, "/media/b2.mkv", content_hash="h2", size_bytes=200)

        # min_group_size=3 should only return the first group
        groups = get_duplicate_files(db_conn, min_group_size=3)
        assert len(groups) == 1
        assert groups[0].file_count == 3

    def test_paths_sorted(self, db_conn):
        _insert_file(db_conn, 1, "/media/z.mkv", content_hash="h1")
        _insert_file(db_conn, 2, "/media/a.mkv", content_hash="h1")

        groups = get_duplicate_files(db_conn)
        assert groups[0].paths == ["/media/a.mkv", "/media/z.mkv"]


class TestRunIntegrityCheck:
    """Tests for run_integrity_check."""

    def test_healthy_database(self, db_conn):
        result = run_integrity_check(db_conn)
        assert result.integrity_ok is True
        assert result.integrity_errors == []
        assert result.foreign_key_ok is True
        assert result.foreign_key_errors == []


class TestRunOptimize:
    """Tests for run_optimize."""

    def test_dry_run(self, db_conn):
        result = run_optimize(db_conn, dry_run=True)
        assert result.dry_run is True
        assert result.size_before > 0
        # Dry run: size_after is estimated
        assert result.size_after <= result.size_before

    def test_actual_optimize(self, db_conn):
        # Insert and delete data to create freeable space
        for i in range(50):
            _insert_file(db_conn, i + 1, f"/media/file{i}.mkv")
        db_conn.commit()

        # Delete them to create free pages
        for i in range(50):
            db_conn.execute("DELETE FROM files WHERE id = ?", (i + 1,))
        db_conn.commit()

        result = run_optimize(db_conn, dry_run=False)
        assert result.dry_run is False
        assert result.size_before > 0
        assert result.size_after > 0
        assert result.space_saved >= 0
