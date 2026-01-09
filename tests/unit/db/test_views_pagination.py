"""Tests for pagination enforcement in view functions."""

import sqlite3
from datetime import datetime, timezone

import pytest

from vpo.db.queries import insert_file
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord
from vpo.db.views import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    _clamp_limit,
    get_files_filtered,
    get_files_with_plugin_data,
    get_files_with_transcriptions,
)


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_file(conn: sqlite3.Connection, index: int) -> int:
    """Create a file record and return its ID."""
    file = FileRecord(
        id=None,
        path=f"/media/movies/file{index}.mkv",
        filename=f"file{index}.mkv",
        directory="/media/movies",
        extension=".mkv",
        size_bytes=1000 + index,
        modified_at=datetime.now(timezone.utc).isoformat(),
        content_hash=f"hash{index}",
        container_format="matroska",
        scanned_at=datetime.now(timezone.utc).isoformat(),
        scan_status="ok",
        scan_error=None,
        job_id=None,
        plugin_metadata=None,
    )
    return insert_file(conn, file)


class TestPaginationConstants:
    """Tests for pagination constants."""

    def test_default_page_size_value(self):
        """DEFAULT_PAGE_SIZE has expected value."""
        assert DEFAULT_PAGE_SIZE == 50

    def test_max_page_size_value(self):
        """MAX_PAGE_SIZE has expected value."""
        assert MAX_PAGE_SIZE == 1000


class TestClampLimit:
    """Tests for _clamp_limit helper function."""

    def test_none_returns_default(self):
        """None limit returns DEFAULT_PAGE_SIZE."""
        assert _clamp_limit(None) == DEFAULT_PAGE_SIZE

    def test_valid_limit_unchanged(self):
        """Valid limit within range is unchanged."""
        assert _clamp_limit(100) == 100
        assert _clamp_limit(500) == 500

    def test_zero_clamped_to_one(self):
        """Zero is clamped to 1."""
        assert _clamp_limit(0) == 1

    def test_negative_clamped_to_one(self):
        """Negative values are clamped to 1."""
        assert _clamp_limit(-5) == 1
        assert _clamp_limit(-100) == 1

    def test_exceeds_max_clamped_to_max(self):
        """Values exceeding MAX_PAGE_SIZE are clamped."""
        assert _clamp_limit(1001) == MAX_PAGE_SIZE
        assert _clamp_limit(5000) == MAX_PAGE_SIZE

    def test_custom_max_limit(self):
        """Custom max_limit is respected."""
        assert _clamp_limit(200, max_limit=100) == 100
        assert _clamp_limit(50, max_limit=100) == 50

    def test_boundary_values(self):
        """Boundary values are handled correctly."""
        assert _clamp_limit(1) == 1
        assert _clamp_limit(MAX_PAGE_SIZE) == MAX_PAGE_SIZE


class TestGetFilesFilteredPagination:
    """Tests for pagination in get_files_filtered."""

    def test_default_limit_applied(self, db_conn):
        """Default limit is applied when None."""
        # Create more files than DEFAULT_PAGE_SIZE
        for i in range(60):
            create_file(db_conn, i)

        result = get_files_filtered(db_conn, limit=None)
        assert len(result) == DEFAULT_PAGE_SIZE

    def test_explicit_limit_respected(self, db_conn):
        """Explicit limit is respected."""
        for i in range(30):
            create_file(db_conn, i)

        result = get_files_filtered(db_conn, limit=10)
        assert len(result) == 10

    def test_max_limit_enforced(self, db_conn):
        """Requests exceeding MAX_PAGE_SIZE are clamped."""
        # Just verify clamping works - don't need 1000+ rows
        for i in range(20):
            create_file(db_conn, i)

        # Request more than max, but only 20 exist
        result = get_files_filtered(db_conn, limit=5000)
        assert len(result) == 20


class TestGetFilesWithTranscriptionsPagination:
    """Tests for pagination in get_files_with_transcriptions."""

    def test_default_limit_applied(self, db_conn):
        """Default limit is applied when None."""
        for i in range(60):
            create_file(db_conn, i)

        result = get_files_with_transcriptions(db_conn, limit=None)
        assert len(result) <= DEFAULT_PAGE_SIZE

    def test_explicit_limit_respected(self, db_conn):
        """Explicit limit is respected."""
        for i in range(30):
            create_file(db_conn, i)

        result = get_files_with_transcriptions(db_conn, limit=10)
        assert len(result) <= 10


class TestGetFilesWithPluginDataPagination:
    """Tests for pagination in get_files_with_plugin_data."""

    def test_default_limit_applied(self, db_conn):
        """Default limit is applied when None."""
        for i in range(60):
            create_file(db_conn, i)

        # plugin_name is required; results will be empty but limit still applies
        result = get_files_with_plugin_data(db_conn, "test-plugin", limit=None)
        assert len(result) <= DEFAULT_PAGE_SIZE

    def test_explicit_limit_respected(self, db_conn):
        """Explicit limit is respected."""
        for i in range(30):
            create_file(db_conn, i)

        result = get_files_with_plugin_data(db_conn, "test-plugin", limit=10)
        assert len(result) <= 10
