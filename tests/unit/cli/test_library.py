"""Tests for the vpo library CLI commands."""

import json
import sqlite3

import pytest
from click.testing import CliRunner

from vpo.cli import main
from vpo.db.queries import insert_file, insert_track
from vpo.db.schema import create_schema
from vpo.db.types import FileRecord, TrackRecord
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


class TestLibraryInfoCommand:
    """Tests for vpo library info command."""

    def test_human_output(self, runner, db_conn):
        fid = _insert_file(db_conn, 1, "/media/movie.mkv", size_bytes=5000)
        _insert_track(db_conn, fid, 0, "video")
        _insert_track(db_conn, fid, 1, "audio", codec="aac")

        result = runner.invoke(
            main,
            ["library", "info"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Library Summary" in result.output
        assert "Files: 1" in result.output
        assert "Video:" in result.output
        assert "Audio:" in result.output

    def test_json_output(self, runner, db_conn):
        _insert_file(db_conn, 1, "/media/movie.mkv", size_bytes=5000)

        result = runner.invoke(
            main,
            ["library", "info", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["files"]["total"] == 1
        assert data["files"]["ok"] == 1
        assert "tracks" in data
        assert "database" in data
        assert data["database"]["schema_version"] > 0

    def test_empty_library(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "info"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Files: 0" in result.output


class TestLibraryPruneCommand:
    """Tests for vpo library prune command."""

    def test_dry_run_human(self, runner, db_conn):
        _insert_file(db_conn, 1, "/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["library", "prune", "--dry-run"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Would prune 1" in result.output
        assert "/media/missing.mkv" in result.output

    def test_dry_run_json(self, runner, db_conn):
        _insert_file(db_conn, 1, "/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["library", "prune", "--dry-run", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["files_pruned"] == 1

    def test_prune_with_yes(self, runner, db_conn):
        _insert_file(db_conn, 1, "/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["library", "prune", "--yes"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Pruned 1" in result.output

        # Verify file is actually removed
        files = get_missing_files(db_conn)
        assert len(files) == 0

    def test_prune_json_output(self, runner, db_conn):
        _insert_file(db_conn, 1, "/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["library", "prune", "--yes", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["files_pruned"] == 1
        assert data["dry_run"] is False

    def test_nothing_to_prune(self, runner, db_conn):
        _insert_file(db_conn, 1, "/media/ok.mkv", scan_status="ok")

        result = runner.invoke(
            main,
            ["library", "prune", "--yes"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "No missing files to prune" in result.output

    def test_nothing_to_prune_json(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "prune", "--yes", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["files_pruned"] == 0

    def test_prune_aborted(self, runner, db_conn):
        """Prune without --yes prompts and can be aborted."""
        _insert_file(db_conn, 1, "/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["library", "prune"],
            obj={"db_conn": db_conn},
            input="n\n",
        )
        assert result.exit_code != 0  # Aborted

        # File still exists
        files = get_missing_files(db_conn)
        assert len(files) == 1


class TestLibraryVerifyCommand:
    """Tests for vpo library verify command."""

    def test_healthy_database(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "verify"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Integrity check: OK" in result.output
        assert "Foreign key check: OK" in result.output

    def test_json_output(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "verify", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["integrity_ok"] is True
        assert data["foreign_key_ok"] is True
        assert data["integrity_errors"] == []
        assert data["foreign_key_errors"] == []


class TestLibraryOptimizeCommand:
    """Tests for vpo library optimize command."""

    def test_dry_run_human(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "optimize", "--dry-run"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Current DB size" in result.output
        assert "Free pages" in result.output

    def test_dry_run_json(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "optimize", "--dry-run", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert "size_before" in data
        assert "space_saved" in data

    def test_optimize_with_yes(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "optimize", "--yes"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Before:" in result.output
        assert "After:" in result.output

    def test_optimize_json(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "optimize", "--yes", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["dry_run"] is False
        assert "size_before" in data
        assert "size_after" in data


class TestLibraryDuplicatesCommand:
    """Tests for vpo library duplicates command."""

    def test_no_duplicates(self, runner, db_conn):
        _insert_file(db_conn, 1, "/media/a.mkv", content_hash="hash_a")

        result = runner.invoke(
            main,
            ["library", "duplicates"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "No duplicate files found" in result.output

    def test_shows_duplicates(self, runner, db_conn):
        test_hash = "abcdef123456"  # pragma: allowlist secret
        _insert_file(
            db_conn, 1, "/media/a.mkv", content_hash=test_hash, size_bytes=1000
        )
        _insert_file(
            db_conn, 2, "/media/b.mkv", content_hash=test_hash, size_bytes=1000
        )

        result = runner.invoke(
            main,
            ["library", "duplicates"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Duplicate groups: 1" in result.output
        assert test_hash in result.output
        assert "/media/a.mkv" in result.output
        assert "/media/b.mkv" in result.output

    def test_json_output(self, runner, db_conn):
        _insert_file(db_conn, 1, "/media/a.mkv", content_hash="hash1", size_bytes=1000)
        _insert_file(db_conn, 2, "/media/b.mkv", content_hash="hash1", size_bytes=1000)

        result = runner.invoke(
            main,
            ["library", "duplicates", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total_groups"] == 1
        assert data["groups"][0]["file_count"] == 2
        assert len(data["groups"][0]["paths"]) == 2

    def test_json_empty(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["library", "duplicates", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total_groups"] == 0
        assert data["groups"] == []

    def test_limit_option(self, runner, db_conn):
        # Two groups
        _insert_file(db_conn, 1, "/media/a1.mkv", content_hash="h1")
        _insert_file(db_conn, 2, "/media/a2.mkv", content_hash="h1")
        _insert_file(db_conn, 3, "/media/b1.mkv", content_hash="h2")
        _insert_file(db_conn, 4, "/media/b2.mkv", content_hash="h2")

        result = runner.invoke(
            main,
            ["library", "duplicates", "--json", "--limit", "1"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total_groups"] == 1


class TestScanPruneDeprecation:
    """Tests for the deprecated --prune flag on scan."""

    def test_prune_hidden_from_help(self, runner, db_conn):
        """--prune should not appear in scan --help."""
        result = runner.invoke(
            main,
            ["scan", "--help"],
        )
        assert result.exit_code == 0
        assert "--prune" not in result.output
