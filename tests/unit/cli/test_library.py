"""Tests for the vpo library CLI commands."""

import json
from unittest.mock import patch

from vpo.cli import main
from vpo.cli.exit_codes import ExitCode
from vpo.db.types import ForeignKeyViolation, IntegrityResult
from vpo.db.views import get_missing_files


class TestGetMissingFiles:
    """Tests for the get_missing_files query."""

    def test_returns_missing_files(self, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/ok.mkv", scan_status="ok")
        insert_test_file(id=2, path="/media/missing.mkv", scan_status="missing")

        files = get_missing_files(db_conn)
        assert len(files) == 1
        assert files[0]["path"] == "/media/missing.mkv"

    def test_returns_empty_when_no_missing(self, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/ok.mkv", scan_status="ok")

        files = get_missing_files(db_conn)
        assert files == []

    def test_respects_limit(self, db_conn, insert_test_file):
        for i in range(5):
            insert_test_file(
                id=i + 1,
                path=f"/media/missing{i}.mkv",
                scan_status="missing",
            )

        files = get_missing_files(db_conn, limit=3)
        assert len(files) == 3

    def test_includes_size_bytes(self, db_conn, insert_test_file):
        insert_test_file(
            id=1,
            path="/media/missing.mkv",
            scan_status="missing",
            size_bytes=4200000000,
        )

        files = get_missing_files(db_conn)
        assert files[0]["size_bytes"] == 4200000000


class TestLibraryMissingCommand:
    """Tests for vpo library missing command."""

    def test_human_output_with_files(self, runner, db_conn, insert_test_file):
        """Human output shows table with missing files."""
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["db", "missing"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Missing files: 1" in result.output
        assert "missing.mkv" in result.output

    def test_human_output_empty(self, runner, db_conn):
        """Empty result shows friendly message."""
        result = runner.invoke(
            main,
            ["db", "missing"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "No missing files found" in result.output

    def test_json_output(self, runner, db_conn, insert_test_file):
        """JSON output has correct structure."""
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["db", "missing", "--json"],
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
            ["db", "missing", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total"] == 0
        assert data["files"] == []

    def test_limit_option(self, runner, db_conn, insert_test_file):
        """--limit restricts output count."""
        for i in range(5):
            insert_test_file(
                id=i + 1,
                path=f"/media/missing{i}.mkv",
                scan_status="missing",
            )

        result = runner.invoke(
            main,
            ["db", "missing", "--json", "--limit", "2"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total"] == 2


class TestLibraryMissingEdgeCases:
    """Edge case tests for library missing command."""

    def test_human_output_zero_size(self, runner, db_conn, insert_test_file):
        """Files with zero size_bytes don't crash human output."""
        insert_test_file(
            id=1,
            path="/media/missing.mkv",
            scan_status="missing",
            size_bytes=0,
        )

        result = runner.invoke(
            main,
            ["db", "missing"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "missing.mkv" in result.output

    def test_json_output_zero_size(self, runner, db_conn, insert_test_file):
        """JSON output handles zero size_bytes."""
        insert_test_file(
            id=1,
            path="/media/missing.mkv",
            scan_status="missing",
            size_bytes=0,
        )

        result = runner.invoke(
            main,
            ["db", "missing", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["files"][0]["size_bytes"] == 0

    def test_human_output_large_size(self, runner, db_conn, insert_test_file):
        """Files with very large size_bytes format correctly."""
        insert_test_file(
            id=1,
            path="/media/missing.mkv",
            scan_status="missing",
            size_bytes=42_000_000_000,
        )

        result = runner.invoke(
            main,
            ["db", "missing"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "missing.mkv" in result.output


class TestLibraryInfoCommand:
    """Tests for vpo library info command."""

    def test_human_output(self, runner, db_conn, insert_test_file, insert_test_track):
        fid = insert_test_file(id=1, path="/media/movie.mkv", size_bytes=5000)
        insert_test_track(file_id=fid, track_index=0, track_type="video")
        insert_test_track(file_id=fid, track_index=1, track_type="audio", codec="aac")

        result = runner.invoke(
            main,
            ["db", "info"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Database Summary" in result.output
        assert "Files: 1" in result.output
        assert "Video:" in result.output
        assert "Audio:" in result.output

    def test_json_output(self, runner, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/movie.mkv", size_bytes=5000)

        result = runner.invoke(
            main,
            ["db", "info", "--json"],
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
            ["db", "info"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Files: 0" in result.output


class TestLibraryPruneCommand:
    """Tests for vpo library prune command."""

    def test_dry_run_human(self, runner, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["db", "prune", "--dry-run"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Would prune 1" in result.output
        assert "/media/missing.mkv" in result.output

    def test_dry_run_json(self, runner, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["db", "prune", "--dry-run", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["files_pruned"] == 1

    def test_prune_with_yes(self, runner, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["db", "prune", "--yes"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Pruned 1" in result.output

        # Verify file is actually removed
        files = get_missing_files(db_conn)
        assert len(files) == 0

    def test_prune_json_output(self, runner, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["db", "prune", "--yes", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["files_pruned"] == 1
        assert data["dry_run"] is False

    def test_nothing_to_prune(self, runner, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/ok.mkv", scan_status="ok")

        result = runner.invoke(
            main,
            ["db", "prune", "--yes"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "No missing files to prune" in result.output

    def test_nothing_to_prune_json(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["db", "prune", "--yes", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["files_pruned"] == 0

    def test_prune_aborted(self, runner, db_conn, insert_test_file):
        """Prune without --yes prompts and can be aborted."""
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        result = runner.invoke(
            main,
            ["db", "prune"],
            obj={"db_conn": db_conn},
            input="n\n",
        )
        assert result.exit_code != 0  # Aborted

        # File still exists
        files = get_missing_files(db_conn)
        assert len(files) == 1

    def test_prune_failure_json(self, runner, db_conn, insert_test_file):
        """Prune failure with JSON output shows error."""
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        from vpo.jobs.services.prune import PruneJobResult

        mock_result = PruneJobResult(
            success=False, files_pruned=0, error_message="disk error"
        )

        with patch(
            "vpo.jobs.services.prune.PruneJobService.process",
            return_value=mock_result,
        ):
            result = runner.invoke(
                main,
                ["db", "prune", "--yes", "--json"],
                obj={"db_conn": db_conn},
            )

        assert result.exit_code == ExitCode.OPERATION_FAILED
        data = json.loads(result.output)
        assert data["files_pruned"] == 0
        assert data["error"] == "disk error"

    def test_prune_failure_human(self, runner, db_conn, insert_test_file):
        """Prune failure with human output shows error on stderr."""
        insert_test_file(id=1, path="/media/missing.mkv", scan_status="missing")

        from vpo.jobs.services.prune import PruneJobResult

        mock_result = PruneJobResult(
            success=False, files_pruned=0, error_message="disk error"
        )

        with patch(
            "vpo.jobs.services.prune.PruneJobService.process",
            return_value=mock_result,
        ):
            result = runner.invoke(
                main,
                ["db", "prune", "--yes"],
                obj={"db_conn": db_conn},
            )

        assert result.exit_code == ExitCode.OPERATION_FAILED


class TestLibraryVerifyCommand:
    """Tests for vpo library verify command."""

    def test_healthy_database(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["db", "verify"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Integrity check: OK" in result.output
        assert "Foreign key check: OK" in result.output

    def test_json_output(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["db", "verify", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["integrity_ok"] is True
        assert data["foreign_key_ok"] is True
        assert data["integrity_errors"] == []
        assert data["foreign_key_errors"] == []

    def test_integrity_failure(self, runner, db_conn):
        """Integrity check failure produces non-zero exit and error output."""
        failed_result = IntegrityResult(
            integrity_ok=False,
            integrity_errors=["page 42: btree cell underflow"],
            foreign_key_ok=True,
            foreign_key_errors=[],
        )

        with patch("vpo.db.views.run_integrity_check", return_value=failed_result):
            result = runner.invoke(
                main,
                ["db", "verify"],
                obj={"db_conn": db_conn},
            )

        assert result.exit_code == ExitCode.DATABASE_ERROR
        assert "FAILED" in result.output
        assert "btree cell underflow" in result.output

    def test_fk_failure_json(self, runner, db_conn):
        """FK violation with JSON output shows structured error."""
        failed_result = IntegrityResult(
            integrity_ok=True,
            integrity_errors=[],
            foreign_key_ok=False,
            foreign_key_errors=[
                ForeignKeyViolation(table="tracks", rowid=99, parent="files", fkid=0)
            ],
        )

        with patch("vpo.db.views.run_integrity_check", return_value=failed_result):
            result = runner.invoke(
                main,
                ["db", "verify", "--json"],
                obj={"db_conn": db_conn},
            )

        assert result.exit_code == ExitCode.DATABASE_ERROR
        data = json.loads(result.output)
        assert data["foreign_key_ok"] is False
        assert len(data["foreign_key_errors"]) == 1
        assert data["foreign_key_errors"][0]["table"] == "tracks"
        assert data["foreign_key_errors"][0]["rowid"] == 99
        assert data["foreign_key_errors"][0]["parent"] == "files"
        assert data["foreign_key_errors"][0]["fkid"] == 0


class TestLibraryOptimizeCommand:
    """Tests for vpo library optimize command."""

    def test_dry_run_human(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["db", "optimize", "--dry-run"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Current DB size" in result.output
        assert "Free pages" in result.output

    def test_dry_run_json(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["db", "optimize", "--dry-run", "--json"],
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
            ["db", "optimize", "--yes"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Before:" in result.output
        assert "After:" in result.output

    def test_optimize_json(self, runner, db_conn):
        result = runner.invoke(
            main,
            ["db", "optimize", "--yes", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["dry_run"] is False
        assert "size_before" in data
        assert "size_after" in data


class TestLibraryDuplicatesCommand:
    """Tests for vpo library duplicates command."""

    def test_no_duplicates(self, runner, db_conn, insert_test_file):
        insert_test_file(id=1, path="/media/a.mkv", content_hash="hash_a")

        result = runner.invoke(
            main,
            ["db", "duplicates"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "No duplicate files found" in result.output

    def test_shows_duplicates(self, runner, db_conn, insert_test_file):
        test_hash = "abcdef123456"  # pragma: allowlist secret
        insert_test_file(
            id=1, path="/media/a.mkv", content_hash=test_hash, size_bytes=1000
        )
        insert_test_file(
            id=2, path="/media/b.mkv", content_hash=test_hash, size_bytes=1000
        )

        result = runner.invoke(
            main,
            ["db", "duplicates"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0
        assert "Duplicate groups: 1" in result.output
        assert test_hash in result.output
        assert "/media/a.mkv" in result.output
        assert "/media/b.mkv" in result.output

    def test_json_output(self, runner, db_conn, insert_test_file):
        insert_test_file(
            id=1, path="/media/a.mkv", content_hash="hash1", size_bytes=1000
        )
        insert_test_file(
            id=2, path="/media/b.mkv", content_hash="hash1", size_bytes=1000
        )

        result = runner.invoke(
            main,
            ["db", "duplicates", "--json"],
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
            ["db", "duplicates", "--json"],
            obj={"db_conn": db_conn},
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert data["total_groups"] == 0
        assert data["groups"] == []

    def test_limit_option(self, runner, db_conn, insert_test_file):
        # Two groups
        insert_test_file(id=1, path="/media/a1.mkv", content_hash="h1")
        insert_test_file(id=2, path="/media/a2.mkv", content_hash="h1")
        insert_test_file(id=3, path="/media/b1.mkv", content_hash="h2")
        insert_test_file(id=4, path="/media/b2.mkv", content_hash="h2")

        result = runner.invoke(
            main,
            ["db", "duplicates", "--json", "--limit", "1"],
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

    def test_scan_prune_emits_deprecation_warning(self, runner, db_conn, tmp_path):
        """scan --prune emits deprecation warning."""
        result = runner.invoke(
            main,
            ["scan", "--prune", str(tmp_path)],
            obj={"db_conn": db_conn},
        )
        # CliRunner mixes stderr into output by default.
        # The deprecation warning should appear in the output.
        assert "deprecated" in result.output.lower()
        assert "vpo library prune" in result.output
