"""Tests for the vpo library CLI commands."""

import json
import sqlite3

import pytest
from click.testing import CliRunner

from vpo.cli import main
from vpo.db.queries import insert_file
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord
from vpo.db.views import get_missing_files


@pytest.fixture
def db_conn():
    """Create an in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return conn


@pytest.fixture
def runner():
    return CliRunner()


def _insert_file(conn, file_id, path, scan_status="ok", size_bytes=1000):
    """Insert a test file record."""
    record = FileRecord(
        id=file_id,
        path=path,
        filename=path.split("/")[-1],
        directory="/media",
        extension=".mkv",
        size_bytes=size_bytes,
        modified_at="2025-01-15T08:30:00Z",
        content_hash=None,
        container_format="mkv",
        scanned_at="2025-01-15T08:30:00Z",
        scan_status=scan_status,
        scan_error=None,
    )
    return insert_file(conn, record)


class TestGetMissingFiles:
    """Tests for the get_missing_files query."""

    def test_returns_missing_files(self, db_conn):
        _insert_file(db_conn, 1, "/media/ok.mkv", scan_status="ok")
        _insert_file(db_conn, 2, "/media/missing.mkv", scan_status="missing")

        files = get_missing_files(db_conn)
        assert len(files) == 1
        assert files[0]["path"] == "/media/missing.mkv"

    def test_returns_empty_when_no_missing(self, db_conn):
        _insert_file(db_conn, 1, "/media/ok.mkv", scan_status="ok")

        files = get_missing_files(db_conn)
        assert files == []

    def test_respects_limit(self, db_conn):
        for i in range(5):
            _insert_file(
                db_conn,
                i + 1,
                f"/media/missing{i}.mkv",
                scan_status="missing",
            )

        files = get_missing_files(db_conn, limit=3)
        assert len(files) == 3

    def test_includes_size_bytes(self, db_conn):
        _insert_file(
            db_conn,
            1,
            "/media/missing.mkv",
            scan_status="missing",
            size_bytes=4200000000,
        )

        files = get_missing_files(db_conn)
        assert files[0]["size_bytes"] == 4200000000


class TestLibraryMissingCommand:
    """Tests for vpo library missing command."""

    def test_human_output_with_files(self, runner, db_conn):
        """Human output shows table with missing files."""
        _insert_file(db_conn, 1, "/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["library", "missing"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Missing files: 1" in result.output
        assert "missing.mkv" in result.output

    def test_human_output_empty(self, runner, db_conn):
        """Empty result shows friendly message."""
        result = runner.invoke(
            main,
            ["library", "missing"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "No missing files found" in result.output

    def test_json_output(self, runner, db_conn):
        """JSON output has correct structure."""
        _insert_file(db_conn, 1, "/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["library", "missing", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total"] == 1
        assert len(data["files"]) == 1
        assert data["files"][0]["path"] == "/media/missing.mkv"
        assert "size_bytes" in data["files"][0]
        assert "scanned_at" in data["files"][0]

    def test_json_output_empty(self, runner, db_conn):
        """Empty JSON output has zero total."""
        result = runner.invoke(
            main,
            ["library", "missing", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total"] == 0
        assert data["files"] == []

    def test_limit_option(self, runner, db_conn):
        """--limit restricts output count."""
        for i in range(5):
            _insert_file(
                db_conn,
                i + 1,
                f"/media/missing{i}.mkv",
                scan_status="missing",
            )

        result = runner.invoke(
            main,
            ["library", "missing", "--json", "--limit", "2"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total"] == 2


class TestLibraryMissingEdgeCases:
    """Edge case tests for library missing command."""

    def test_human_output_zero_size(self, runner, db_conn):
        """Files with zero size_bytes don't crash human output."""
        _insert_file(
            db_conn,
            1,
            "/media/missing.mkv",
            scan_status="missing",
            size_bytes=0,
        )

        result = runner.invoke(
            main,
            ["library", "missing"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "missing.mkv" in result.output

    def test_json_output_zero_size(self, runner, db_conn):
        """JSON output handles zero size_bytes."""
        _insert_file(
            db_conn,
            1,
            "/media/missing.mkv",
            scan_status="missing",
            size_bytes=0,
        )

        result = runner.invoke(
            main,
            ["library", "missing", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["files"][0]["size_bytes"] == 0

    def test_human_output_large_size(self, runner, db_conn):
        """Files with very large size_bytes format correctly."""
        _insert_file(
            db_conn,
            1,
            "/media/missing.mkv",
            scan_status="missing",
            size_bytes=42_000_000_000,
        )

        result = runner.invoke(
            main,
            ["library", "missing"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "missing.mkv" in result.output
