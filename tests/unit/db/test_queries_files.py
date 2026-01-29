"""Tests for file query functions in vpo.db.queries.files."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vpo.db.queries import get_file_by_path, insert_file, update_file_path
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


def create_file(
    conn: sqlite3.Connection,
    path: str,
    extension: str | None = None,
) -> int:
    """Create a file record and return its ID."""
    p = Path(path)
    if extension is None:
        extension = p.suffix.lstrip(".") or None
    record = FileRecord(
        id=None,
        path=str(p),
        filename=p.name,
        directory=str(p.parent),
        extension=extension,
        size_bytes=1000000,
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_hash="hash123",
        container_format="matroska",
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scan_status="ok",
        scan_error=None,
        job_id=None,
        plugin_metadata=None,
    )
    file_id = insert_file(conn, record)
    conn.commit()
    return file_id


class TestUpdateFilePath:
    """Tests for update_file_path function."""

    def test_updates_path_fields(self, db_conn):
        """Updates path, filename, and directory fields."""
        file_id = create_file(db_conn, "/media/movies/movie.avi")

        result = update_file_path(db_conn, file_id, "/media/archive/movie.avi")
        db_conn.commit()

        assert result is True
        record = get_file_by_path(db_conn, "/media/archive/movie.avi")
        assert record is not None
        assert record.path == "/media/archive/movie.avi"
        assert record.filename == "movie.avi"
        assert record.directory == "/media/archive"

    def test_updates_extension_on_container_change(self, db_conn):
        """Updates extension field when container format changes."""
        file_id = create_file(db_conn, "/media/movies/movie.avi", extension="avi")

        result = update_file_path(db_conn, file_id, "/media/movies/movie.mkv")
        db_conn.commit()

        assert result is True
        record = get_file_by_path(db_conn, "/media/movies/movie.mkv")
        assert record is not None
        assert record.extension == "mkv"

    def test_extension_avi_to_mkv(self, db_conn):
        """Extension updates from avi to mkv during container conversion."""
        file_id = create_file(db_conn, "/media/video.avi", extension="avi")

        update_file_path(db_conn, file_id, "/media/video.mkv")
        db_conn.commit()

        record = get_file_by_path(db_conn, "/media/video.mkv")
        assert record.extension == "mkv"

    def test_extension_mp4_to_mkv(self, db_conn):
        """Extension updates from mp4 to mkv during container conversion."""
        file_id = create_file(db_conn, "/media/video.mp4", extension="mp4")

        update_file_path(db_conn, file_id, "/media/video.mkv")
        db_conn.commit()

        record = get_file_by_path(db_conn, "/media/video.mkv")
        assert record.extension == "mkv"

    def test_no_extension_raises_integrity_error(self, db_conn):
        """Raises IntegrityError for paths without extension (NOT NULL constraint)."""
        file_id = create_file(db_conn, "/media/video.mkv", extension="mkv")

        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
            update_file_path(db_conn, file_id, "/media/video")

    def test_returns_false_for_nonexistent_file(self, db_conn):
        """Returns False when file_id doesn't exist."""
        result = update_file_path(db_conn, 9999, "/media/nonexistent.mkv")

        assert result is False

    def test_raises_on_duplicate_path(self, db_conn):
        """Raises IntegrityError when new path already exists."""
        create_file(db_conn, "/media/movie1.mkv")
        file2_id = create_file(db_conn, "/media/movie2.mkv")

        with pytest.raises(sqlite3.IntegrityError, match="already exists"):
            update_file_path(db_conn, file2_id, "/media/movie1.mkv")

    def test_does_not_commit(self, db_conn):
        """Function does not commit - caller manages transactions."""
        file_id = create_file(db_conn, "/media/movie.avi")

        update_file_path(db_conn, file_id, "/media/movie.mkv")

        # Rollback and verify change was not persisted
        db_conn.rollback()

        # Original path should still exist
        original = get_file_by_path(db_conn, "/media/movie.avi")
        assert original is not None

        # New path should not exist
        updated = get_file_by_path(db_conn, "/media/movie.mkv")
        assert updated is None

    def test_handles_path_with_multiple_dots(self, db_conn):
        """Correctly extracts extension from paths with multiple dots."""
        file_id = create_file(db_conn, "/media/movie.2024.avi", extension="avi")

        update_file_path(db_conn, file_id, "/media/movie.2024.mkv")
        db_conn.commit()

        record = get_file_by_path(db_conn, "/media/movie.2024.mkv")
        assert record.extension == "mkv"
        assert record.filename == "movie.2024.mkv"
