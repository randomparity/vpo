"""Tests for batch file lookup function get_files_by_paths()."""

import sqlite3
from datetime import datetime, timezone

from vpo.db.queries import get_files_by_paths, insert_file
from vpo.db.types import FileRecord


def create_file(conn: sqlite3.Connection, path: str) -> int:
    """Create a file record and return its ID."""
    file = FileRecord(
        id=None,
        path=path,
        filename=path.split("/")[-1],
        directory="/".join(path.split("/")[:-1]),
        extension=".mkv",
        size_bytes=1000,
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_hash=f"hash_{path}",
        container_format="matroska",
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scan_status="ok",
        scan_error=None,
        job_id=None,
        plugin_metadata=None,
    )
    return insert_file(conn, file)


class TestGetFilesByPaths:
    """Tests for get_files_by_paths batch lookup function."""

    def test_empty_paths_returns_empty_dict(self, db_conn):
        """Empty paths list returns empty dict without query."""
        result = get_files_by_paths(db_conn, [])
        assert result == {}

    def test_single_path_found(self, db_conn):
        """Single path lookup returns matching record."""
        path = "/media/movies/test.mkv"
        create_file(db_conn, path)

        result = get_files_by_paths(db_conn, [path])

        assert len(result) == 1
        assert path in result
        assert result[path].path == path
        assert result[path].filename == "test.mkv"

    def test_multiple_paths_found(self, db_conn):
        """Multiple paths return all matching records."""
        paths = [
            "/media/movies/movie1.mkv",
            "/media/movies/movie2.mkv",
            "/media/tv/show1.mkv",
        ]
        for path in paths:
            create_file(db_conn, path)

        result = get_files_by_paths(db_conn, paths)

        assert len(result) == 3
        for path in paths:
            assert path in result
            assert result[path].path == path

    def test_missing_paths_not_included(self, db_conn):
        """Missing paths are not in result dict."""
        existing_path = "/media/movies/exists.mkv"
        missing_path = "/media/movies/missing.mkv"
        create_file(db_conn, existing_path)

        result = get_files_by_paths(db_conn, [existing_path, missing_path])

        assert len(result) == 1
        assert existing_path in result
        assert missing_path not in result

    def test_all_paths_missing_returns_empty(self, db_conn):
        """All missing paths returns empty dict."""
        result = get_files_by_paths(
            db_conn, ["/nonexistent/path1.mkv", "/nonexistent/path2.mkv"]
        )
        assert result == {}

    def test_chunking_with_many_paths(self, db_conn):
        """Large path lists are chunked correctly."""
        # Create more paths than the default chunk size
        paths = [f"/media/file{i}.mkv" for i in range(1500)]
        for path in paths:
            create_file(db_conn, path)

        result = get_files_by_paths(db_conn, paths, chunk_size=500)

        assert len(result) == 1500
        for path in paths:
            assert path in result

    def test_custom_chunk_size(self, db_conn):
        """Custom chunk size is respected."""
        paths = [f"/media/file{i}.mkv" for i in range(10)]
        for path in paths:
            create_file(db_conn, path)

        # Use very small chunk size to ensure multiple queries
        result = get_files_by_paths(db_conn, paths, chunk_size=3)

        assert len(result) == 10

    def test_returns_correct_file_record_fields(self, db_conn):
        """Returned FileRecord has all expected fields."""
        path = "/media/movies/test.mkv"
        create_file(db_conn, path)

        result = get_files_by_paths(db_conn, [path])
        record = result[path]

        assert record.id is not None
        assert record.path == path
        assert record.filename == "test.mkv"
        assert record.directory == "/media/movies"
        assert record.extension == ".mkv"
        assert record.size_bytes == 1000
        assert record.container_format == "matroska"
        assert record.scan_status == "ok"

    def test_partial_match_with_duplicates_in_input(self, db_conn):
        """Duplicate paths in input don't cause issues."""
        path = "/media/movies/test.mkv"
        create_file(db_conn, path)

        result = get_files_by_paths(db_conn, [path, path, path])

        assert len(result) == 1
        assert path in result
