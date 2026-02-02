"""Tests for library info and maintenance view queries."""

from vpo.db.maintenance import run_integrity_check, run_optimize
from vpo.db.views.library_info import (
    get_duplicate_files,
    get_library_info,
)


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

    def test_file_counts_by_status(self, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/ok1.mkv", scan_status="ok")
        insert_test_file(id=2, path="/media/ok2.mkv", scan_status="ok")
        insert_test_file(id=3, path="/media/missing.mkv", scan_status="missing")
        insert_test_file(id=4, path="/media/error.mkv", scan_status="error")

        info = get_library_info(db_conn)
        assert info.total_files == 4
        assert info.files_ok == 2
        assert info.files_missing == 1
        assert info.files_error == 1
        assert info.files_pending == 0

    def test_total_size(self, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/a.mkv", size_bytes=1000)
        insert_test_file(id=2, path="/media/b.mkv", size_bytes=2000)

        info = get_library_info(db_conn)
        assert info.total_size_bytes == 3000

    def test_track_counts(self, db_conn, insert_test_file, insert_test_track):
        fid = insert_test_file(id=1, path="/media/a.mkv")
        insert_test_track(file_id=fid, track_index=0, track_type="video")
        insert_test_track(file_id=fid, track_index=1, track_type="audio", codec="aac")
        insert_test_track(file_id=fid, track_index=2, track_type="audio", codec="ac3")
        insert_test_track(
            file_id=fid, track_index=3, track_type="subtitle", codec="srt"
        )

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

    def test_pending_scan_status_counted(self, db_conn, insert_test_file):
        """Files with scan_status='pending' should be counted."""
        insert_test_file(id=1, path="/media/pending.mkv", scan_status="pending")
        insert_test_file(id=2, path="/media/ok.mkv", scan_status="ok")

        info = get_library_info(db_conn)
        assert info.files_pending == 1
        assert info.total_files == 2


class TestGetDuplicateFiles:
    """Tests for get_duplicate_files."""

    def test_no_duplicates(self, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/a.mkv", content_hash="hash_a")
        insert_test_file(id=2, path="/media/b.mkv", content_hash="hash_b")

        groups = get_duplicate_files(db_conn)
        assert groups == []

    def test_finds_duplicates(self, db_conn, insert_test_file):
        insert_test_file(
            id=1, path="/media/a.mkv", content_hash="hash_dup", size_bytes=1000
        )
        insert_test_file(
            id=2, path="/media/b.mkv", content_hash="hash_dup", size_bytes=1000
        )
        insert_test_file(id=3, path="/media/c.mkv", content_hash="hash_unique")

        groups = get_duplicate_files(db_conn)
        assert len(groups) == 1
        assert groups[0].content_hash == "hash_dup"
        assert groups[0].file_count == 2
        assert groups[0].total_size_bytes == 2000
        assert len(groups[0].paths) == 2

    def test_excludes_null_hashes(self, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/a.mkv", content_hash=None)
        insert_test_file(id=2, path="/media/b.mkv", content_hash=None)

        groups = get_duplicate_files(db_conn)
        assert groups == []

    def test_excludes_empty_string_hashes(self, db_conn, insert_test_file):
        """Empty-string content_hash should be excluded like NULL."""
        insert_test_file(id=1, path="/media/a.mkv", content_hash="")
        insert_test_file(id=2, path="/media/b.mkv", content_hash="")

        groups = get_duplicate_files(db_conn)
        assert groups == []

    def test_respects_limit(self, db_conn, insert_test_file):
        # Create two duplicate groups
        insert_test_file(id=1, path="/media/a1.mkv", content_hash="h1", size_bytes=100)
        insert_test_file(id=2, path="/media/a2.mkv", content_hash="h1", size_bytes=100)
        insert_test_file(id=3, path="/media/b1.mkv", content_hash="h2", size_bytes=200)
        insert_test_file(id=4, path="/media/b2.mkv", content_hash="h2", size_bytes=200)

        groups = get_duplicate_files(db_conn, limit=1)
        assert len(groups) == 1

    def test_negative_limit_clamped(self, db_conn, insert_test_file):
        """Negative limit should be clamped to 1."""
        insert_test_file(id=1, path="/media/a1.mkv", content_hash="h1", size_bytes=100)
        insert_test_file(id=2, path="/media/a2.mkv", content_hash="h1", size_bytes=100)

        groups = get_duplicate_files(db_conn, limit=-5)
        # Should still return results (clamped to 1)
        assert len(groups) == 1

    def test_zero_limit_clamped(self, db_conn, insert_test_file):
        """Zero limit should be clamped to 1."""
        insert_test_file(id=1, path="/media/a1.mkv", content_hash="h1", size_bytes=100)
        insert_test_file(id=2, path="/media/a2.mkv", content_hash="h1", size_bytes=100)

        groups = get_duplicate_files(db_conn, limit=0)
        assert len(groups) == 1

    def test_min_group_size(self, db_conn, insert_test_file):
        # Create a group of 3
        insert_test_file(id=1, path="/media/a1.mkv", content_hash="h1", size_bytes=100)
        insert_test_file(id=2, path="/media/a2.mkv", content_hash="h1", size_bytes=100)
        insert_test_file(id=3, path="/media/a3.mkv", content_hash="h1", size_bytes=100)
        # Create a group of 2
        insert_test_file(id=4, path="/media/b1.mkv", content_hash="h2", size_bytes=200)
        insert_test_file(id=5, path="/media/b2.mkv", content_hash="h2", size_bytes=200)

        # min_group_size=3 should only return the first group
        groups = get_duplicate_files(db_conn, min_group_size=3)
        assert len(groups) == 1
        assert groups[0].file_count == 3

    def test_paths_sorted(self, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/z.mkv", content_hash="h1")
        insert_test_file(id=2, path="/media/a.mkv", content_hash="h1")

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

    def test_actual_optimize(self, db_conn, insert_test_file):
        # Insert and delete data to create freeable space
        for i in range(50):
            insert_test_file(id=i + 1, path=f"/media/file{i}.mkv")
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
