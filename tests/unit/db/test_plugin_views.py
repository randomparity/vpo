"""Tests for plugin data view query functions."""

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.db.queries import insert_file
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord
from vpo.db.views import (
    get_files_with_plugin_data,
    get_plugin_data_for_file,
)


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


def create_file_with_plugin_metadata(
    conn: sqlite3.Connection,
    file_id: int,
    filename: str,
    plugin_metadata: dict | None = None,
) -> FileRecord:
    """Create a file record with optional plugin metadata."""
    metadata_json = json.dumps(plugin_metadata) if plugin_metadata else None
    file = FileRecord(
        id=file_id,
        path=f"/test/path/{filename}",
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
        plugin_metadata=metadata_json,
    )
    insert_file(conn, file)
    return file


class TestGetFilesWithPluginData:
    """Tests for get_files_with_plugin_data function."""

    def test_returns_empty_list_when_no_files(self, db_conn):
        """Returns empty list when database has no files."""
        result = get_files_with_plugin_data(db_conn, "whisper-transcriber")
        assert result == []

    def test_returns_empty_list_when_no_plugin_metadata(self, db_conn):
        """Returns empty list when files have no plugin metadata."""
        create_file_with_plugin_metadata(db_conn, 1, "test.mkv", plugin_metadata=None)
        result = get_files_with_plugin_data(db_conn, "whisper-transcriber")
        assert result == []

    def test_returns_empty_list_when_plugin_not_present(self, db_conn):
        """Returns empty list when specific plugin has no data."""
        create_file_with_plugin_metadata(
            db_conn,
            1,
            "test.mkv",
            plugin_metadata={"other-plugin": {"field": "value"}},
        )
        result = get_files_with_plugin_data(db_conn, "whisper-transcriber")
        assert result == []

    def test_returns_files_with_plugin_data(self, db_conn):
        """Returns files that have data from the specified plugin."""
        create_file_with_plugin_metadata(
            db_conn,
            1,
            "test.mkv",
            plugin_metadata={
                "whisper-transcriber": {"language": "en", "confidence": 0.95}
            },
        )
        result = get_files_with_plugin_data(db_conn, "whisper-transcriber")
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["filename"] == "test.mkv"
        assert result[0]["plugin_data"] == {"language": "en", "confidence": 0.95}

    def test_filters_to_specific_plugin(self, db_conn):
        """Only returns files with data from the requested plugin."""
        create_file_with_plugin_metadata(
            db_conn,
            1,
            "file1.mkv",
            plugin_metadata={"whisper-transcriber": {"language": "en"}},
        )
        create_file_with_plugin_metadata(
            db_conn,
            2,
            "file2.mkv",
            plugin_metadata={"other-plugin": {"data": "value"}},
        )
        create_file_with_plugin_metadata(
            db_conn,
            3,
            "file3.mkv",
            plugin_metadata={
                "whisper-transcriber": {"language": "fr"},
                "other-plugin": {"data": "value"},
            },
        )

        result = get_files_with_plugin_data(db_conn, "whisper-transcriber")
        assert len(result) == 2
        filenames = [f["filename"] for f in result]
        assert "file1.mkv" in filenames
        assert "file3.mkv" in filenames
        assert "file2.mkv" not in filenames

    def test_pagination_limit(self, db_conn):
        """Respects limit parameter."""
        for i in range(5):
            create_file_with_plugin_metadata(
                db_conn,
                i + 1,
                f"file{i}.mkv",
                plugin_metadata={"test-plugin": {"index": i}},
            )

        result = get_files_with_plugin_data(db_conn, "test-plugin", limit=2)
        assert len(result) == 2

    def test_pagination_offset(self, db_conn):
        """Respects offset parameter."""
        for i in range(5):
            create_file_with_plugin_metadata(
                db_conn,
                i + 1,
                f"file{i}.mkv",
                plugin_metadata={"test-plugin": {"index": i}},
            )

        result = get_files_with_plugin_data(db_conn, "test-plugin", limit=2, offset=2)
        assert len(result) == 2

    def test_return_total_count(self, db_conn):
        """Returns total count when return_total=True."""
        for i in range(5):
            create_file_with_plugin_metadata(
                db_conn,
                i + 1,
                f"file{i}.mkv",
                plugin_metadata={"test-plugin": {"index": i}},
            )

        result, total = get_files_with_plugin_data(
            db_conn, "test-plugin", limit=2, return_total=True
        )
        assert len(result) == 2
        assert total == 5

    def test_invalid_plugin_name_raises_value_error(self, db_conn):
        """Raises ValueError for invalid plugin name format."""
        with pytest.raises(ValueError, match="Invalid plugin name format"):
            get_files_with_plugin_data(db_conn, "invalid name!")

        with pytest.raises(ValueError, match="Invalid plugin name format"):
            get_files_with_plugin_data(db_conn, "plugin;drop table")

        with pytest.raises(ValueError, match="Invalid plugin name format"):
            get_files_with_plugin_data(db_conn, "plugin/path")

    def test_valid_plugin_name_formats(self, db_conn):
        """Accepts valid plugin name formats."""
        # These should not raise
        get_files_with_plugin_data(db_conn, "whisper-transcriber")
        get_files_with_plugin_data(db_conn, "plugin_name")
        get_files_with_plugin_data(db_conn, "Plugin123")
        get_files_with_plugin_data(db_conn, "test-plugin_v2")


class TestGetPluginDataForFile:
    """Tests for get_plugin_data_for_file function."""

    def test_returns_empty_dict_for_nonexistent_file(self, db_conn):
        """Returns empty dict when file doesn't exist."""
        result = get_plugin_data_for_file(db_conn, 999)
        assert result == {}

    def test_returns_empty_dict_for_file_without_metadata(self, db_conn):
        """Returns empty dict when file has no plugin metadata."""
        create_file_with_plugin_metadata(db_conn, 1, "test.mkv", plugin_metadata=None)
        result = get_plugin_data_for_file(db_conn, 1)
        assert result == {}

    def test_returns_plugin_metadata(self, db_conn):
        """Returns all plugin metadata for a file."""
        metadata = {
            "whisper-transcriber": {"language": "en", "confidence": 0.95},
            "other-plugin": {"processed": True},
        }
        create_file_with_plugin_metadata(
            db_conn, 1, "test.mkv", plugin_metadata=metadata
        )

        result = get_plugin_data_for_file(db_conn, 1)
        assert result == metadata

    def test_handles_malformed_json_gracefully(self, db_conn):
        """Returns empty dict and logs warning for malformed JSON."""
        # Insert file with malformed JSON directly
        conn = db_conn
        conn.execute(
            """
            INSERT INTO files (
                id, path, filename, directory, extension, size_bytes,
                modified_at, content_hash, container_format, scanned_at,
                scan_status, plugin_metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "/test/path/test.mkv",
                "test.mkv",
                "/test/path",
                ".mkv",
                1000,
                datetime.now(timezone.utc).isoformat(),
                "hash1",
                "matroska",
                datetime.now(timezone.utc).isoformat(),
                "ok",
                "not valid json {{{",
            ),
        )
        conn.commit()

        # Should return empty dict without raising
        result = get_plugin_data_for_file(conn, 1)
        assert result == {}

    def test_returns_nested_plugin_data(self, db_conn):
        """Returns nested plugin data structures correctly."""
        metadata = {
            "analysis-plugin": {
                "tracks": [
                    {"index": 0, "language": "en"},
                    {"index": 1, "language": "fr"},
                ],
                "summary": {"total": 2, "analyzed": True},
            }
        }
        create_file_with_plugin_metadata(
            db_conn, 1, "test.mkv", plugin_metadata=metadata
        )

        result = get_plugin_data_for_file(db_conn, 1)
        assert result == metadata


class TestPluginDataExports:
    """Tests that plugin data functions are properly exported."""

    def test_import_from_db_package(self):
        """Functions can be imported from db package."""
        from vpo.db import (
            get_files_with_plugin_data,
            get_plugin_data_for_file,
        )

        assert callable(get_files_with_plugin_data)
        assert callable(get_plugin_data_for_file)


class TestWindowFunctionOptimization:
    """Tests for window function optimization in pagination queries.

    These tests verify that the COUNT(*) OVER() window function returns
    correct totals across different pagination scenarios.
    """

    def test_total_count_consistent_across_pages(self, db_conn):
        """Total count remains consistent when paginating through results."""
        # Create test data
        for i in range(20):
            create_file_with_plugin_metadata(
                db_conn,
                i + 1,
                f"file{i:02d}.mkv",
                plugin_metadata={"test-plugin": {"index": i}},
            )

        # Query different pages and verify total is consistent
        totals = []
        for offset in [0, 5, 10, 15]:
            _, total = get_files_with_plugin_data(
                db_conn,
                "test-plugin",
                limit=5,
                offset=offset,
                return_total=True,
            )
            totals.append(total)

        assert all(t == 20 for t in totals), f"Inconsistent totals: {totals}"

    def test_total_correct_when_limit_exceeds_results(self, db_conn):
        """Total reflects actual count even when limit is larger."""
        # Create only 3 files
        for i in range(3):
            create_file_with_plugin_metadata(
                db_conn,
                i + 1,
                f"file{i}.mkv",
                plugin_metadata={"test-plugin": {"index": i}},
            )

        # Query with limit larger than data
        result, total = get_files_with_plugin_data(
            db_conn,
            "test-plugin",
            limit=100,
            offset=0,
            return_total=True,
        )

        assert len(result) == 3
        assert total == 3

    def test_total_zero_when_no_matches(self, db_conn):
        """Total is zero when no files match the plugin filter."""
        # Create files with different plugin
        for i in range(5):
            create_file_with_plugin_metadata(
                db_conn,
                i + 1,
                f"file{i}.mkv",
                plugin_metadata={"other-plugin": {"index": i}},
            )

        result, total = get_files_with_plugin_data(
            db_conn,
            "nonexistent-plugin",
            limit=10,
            return_total=True,
        )

        assert result == []
        assert total == 0
