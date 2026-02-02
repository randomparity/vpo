"""Tests for file query functions in vpo.db.queries.files."""

import sqlite3

import pytest

from vpo.db.queries import get_file_by_path, update_file_path


class TestUpdateFilePath:
    """Tests for update_file_path function."""

    def test_updates_path_fields(self, db_conn, insert_test_file):
        """Updates path, filename, and directory fields."""
        file_id = insert_test_file(
            path="/media/movies/movie.avi",
            extension="avi",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()

        result = update_file_path(db_conn, file_id, "/media/archive/movie.avi")
        db_conn.commit()

        assert result is True
        record = get_file_by_path(db_conn, "/media/archive/movie.avi")
        assert record is not None
        assert record.path == "/media/archive/movie.avi"
        assert record.filename == "movie.avi"
        assert record.directory == "/media/archive"

    def test_updates_extension_on_container_change(self, db_conn, insert_test_file):
        """Updates extension field when container format changes."""
        file_id = insert_test_file(
            path="/media/movies/movie.avi",
            extension="avi",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()

        result = update_file_path(db_conn, file_id, "/media/movies/movie.mkv")
        db_conn.commit()

        assert result is True
        record = get_file_by_path(db_conn, "/media/movies/movie.mkv")
        assert record is not None
        assert record.extension == "mkv"

    def test_extension_avi_to_mkv(self, db_conn, insert_test_file):
        """Extension updates from avi to mkv during container conversion."""
        file_id = insert_test_file(
            path="/media/video.avi",
            extension="avi",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()

        update_file_path(db_conn, file_id, "/media/video.mkv")
        db_conn.commit()

        record = get_file_by_path(db_conn, "/media/video.mkv")
        assert record.extension == "mkv"

    def test_extension_mp4_to_mkv(self, db_conn, insert_test_file):
        """Extension updates from mp4 to mkv during container conversion."""
        file_id = insert_test_file(
            path="/media/video.mp4",
            extension="mp4",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()

        update_file_path(db_conn, file_id, "/media/video.mkv")
        db_conn.commit()

        record = get_file_by_path(db_conn, "/media/video.mkv")
        assert record.extension == "mkv"

    def test_no_extension_raises_integrity_error(self, db_conn, insert_test_file):
        """Raises IntegrityError for paths without extension (NOT NULL constraint)."""
        file_id = insert_test_file(
            path="/media/video.mkv",
            extension="mkv",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()

        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
            update_file_path(db_conn, file_id, "/media/video")

    def test_returns_false_for_nonexistent_file(self, db_conn):
        """Returns False when file_id doesn't exist."""
        result = update_file_path(db_conn, 9999, "/media/nonexistent.mkv")

        assert result is False

    def test_raises_on_duplicate_path(self, db_conn, insert_test_file):
        """Raises IntegrityError when new path already exists."""
        insert_test_file(
            path="/media/movie1.mkv",
            extension="mkv",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()
        file2_id = insert_test_file(
            path="/media/movie2.mkv",
            extension="mkv",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()

        with pytest.raises(sqlite3.IntegrityError, match="already exists"):
            update_file_path(db_conn, file2_id, "/media/movie1.mkv")

    def test_does_not_commit(self, db_conn, insert_test_file):
        """Function does not commit - caller manages transactions."""
        file_id = insert_test_file(
            path="/media/movie.avi",
            extension="avi",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()

        update_file_path(db_conn, file_id, "/media/movie.mkv")

        # Rollback and verify change was not persisted
        db_conn.rollback()

        # Original path should still exist
        original = get_file_by_path(db_conn, "/media/movie.avi")
        assert original is not None

        # New path should not exist
        updated = get_file_by_path(db_conn, "/media/movie.mkv")
        assert updated is None

    def test_handles_path_with_multiple_dots(self, db_conn, insert_test_file):
        """Correctly extracts extension from paths with multiple dots."""
        file_id = insert_test_file(
            path="/media/movie.2024.avi",
            extension="avi",
            content_hash="hash123",
            container_format="matroska",
            size_bytes=1000000,
        )
        db_conn.commit()

        update_file_path(db_conn, file_id, "/media/movie.2024.mkv")
        db_conn.commit()

        record = get_file_by_path(db_conn, "/media/movie.2024.mkv")
        assert record.extension == "mkv"
        assert record.filename == "movie.2024.mkv"
