"""Unit tests for analyze CLI commands (language analysis).

Tests cover the language subcommand and related status/clear commands.
Updated from test_analyze_language.py as part of CLI reorganization.
The `analyze-language` command was merged into `analyze language`.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from vpo.cli import main
from vpo.cli.analyze import (
    LanguageAnalysisRunResult,
    _check_plugin_available,
    _resolve_files_from_paths,
)
from vpo.cli.exit_codes import ExitCode


@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    return MagicMock()


@pytest.fixture
def mock_file_record():
    """Create a mock FileRecord for testing."""
    from vpo.db import FileRecord

    return FileRecord(
        id=1,
        path="/media/movies/test.mkv",
        filename="test.mkv",
        directory="/media/movies",
        extension=".mkv",
        size_bytes=1024000,
        modified_at="2024-01-01T00:00:00Z",
        content_hash="abc123",
        container_format="mkv",
        scanned_at="2024-01-01T00:00:00Z",
        scan_status="ok",
        scan_error=None,
    )


@pytest.fixture
def mock_track_record():
    """Create a mock TrackRecord for testing."""
    from vpo.db import TrackRecord

    return TrackRecord(
        id=1,
        file_id=1,
        track_index=0,
        track_type="audio",
        codec="aac",
        language="eng",
        title="English",
        is_default=True,
        is_forced=False,
        duration_seconds=3600.0,
        channel_layout="5.1(side)",
        channels=6,
    )


class TestAnalyzeGroup:
    """Tests for the analyze command group."""

    def test_group_help(self, runner):
        """Test that group help is displayed."""
        result = runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "classify" in result.output
        assert "language" in result.output
        assert "status" in result.output
        assert "clear" in result.output


class TestLanguageCommand:
    """Tests for the analyze language subcommand."""

    def test_language_help(self, runner):
        """Test that language help is displayed."""
        result = runner.invoke(main, ["analyze", "language", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output
        assert "--recursive" in result.output
        assert "--json" in result.output

    @patch("vpo.cli.analyze._check_plugin_available")
    def test_language_no_plugin(self, mock_plugin, runner, mock_conn, tmp_path):
        """Test error when transcription plugin not available."""
        mock_plugin.return_value = False
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        result = runner.invoke(
            main,
            ["analyze", "language", str(test_file)],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == ExitCode.PLUGIN_UNAVAILABLE
        assert "Whisper transcription plugin not installed" in result.output

    @patch("vpo.cli.analyze._check_plugin_available")
    @patch("vpo.cli.analyze._resolve_files_from_paths")
    def test_language_no_files_found(
        self, mock_resolve, mock_plugin, runner, mock_conn, tmp_path
    ):
        """Test error when no files found in database."""
        mock_plugin.return_value = True
        mock_resolve.return_value = ([], [str(tmp_path / "test.mkv")])
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        result = runner.invoke(
            main,
            ["analyze", "language", str(test_file)],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == ExitCode.TARGET_NOT_FOUND
        assert "No valid files found" in result.output

    @patch("vpo.cli.analyze._check_plugin_available")
    @patch("vpo.cli.analyze._resolve_files_from_paths")
    @patch("vpo.cli.analyze._run_language_analysis_for_file")
    def test_language_success_json(
        self,
        mock_run,
        mock_resolve,
        mock_plugin,
        runner,
        mock_conn,
        mock_file_record,
        tmp_path,
    ):
        """Test successful run with JSON output."""
        mock_plugin.return_value = True
        mock_resolve.return_value = ([mock_file_record], [])
        mock_run.return_value = LanguageAnalysisRunResult(
            file_path=mock_file_record.path,
            success=True,
            track_count=2,
            analyzed_count=2,
            cached_count=0,
            duration_ms=1000,
        )
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        result = runner.invoke(
            main,
            ["analyze", "language", str(test_file), "--json"],
            obj={"db_conn": mock_conn},
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert result.output, "No output from command"
        data = json.loads(result.output)
        assert data["successful"] == 1
        assert data["tracks_analyzed"] == 2


class TestStatusCommand:
    """Tests for the analyze status subcommand."""

    def test_status_help(self, runner):
        """Test that status help is displayed."""
        result = runner.invoke(main, ["analyze", "status", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.output
        assert "--json" in result.output
        assert "--limit" in result.output

    @patch("vpo.db.views.get_analysis_status_summary")
    def test_status_summary_json(self, mock_summary, runner, mock_conn):
        """Test status summary with JSON output."""
        from vpo.db.types import AnalysisStatusSummary

        mock_summary.return_value = AnalysisStatusSummary(
            total_files=100,
            total_tracks=200,
            analyzed_tracks=150,
            pending_tracks=50,
            multi_language_count=10,
            single_language_count=140,
        )

        result = runner.invoke(
            main,
            ["analyze", "status", "--type", "language", "--json"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_files"] == 100
        assert data["analyzed_tracks"] == 150
        assert data["multi_language_count"] == 10

    @patch("vpo.db.views.get_analysis_status_summary")
    def test_status_summary_table(self, mock_summary, runner, mock_conn):
        """Test status summary with table output."""
        from vpo.db.types import AnalysisStatusSummary

        mock_summary.return_value = AnalysisStatusSummary(
            total_files=100,
            total_tracks=200,
            analyzed_tracks=150,
            pending_tracks=50,
            multi_language_count=10,
            single_language_count=140,
        )

        result = runner.invoke(
            main,
            ["analyze", "status", "--type", "language"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        assert "Language Analysis Status" in result.output
        assert "Total files:" in result.output
        assert "100" in result.output
        assert "Multi-language:" in result.output

    def test_classify_status_exits_nonzero(self, runner, mock_conn):
        """analyze status --type classify exits non-zero (not yet implemented)."""
        result = runner.invoke(
            main,
            ["analyze", "status", "--type", "classify"],
            obj={"db_conn": mock_conn},
        )
        assert result.exit_code != 0

    def test_classify_status_json_exits_nonzero(self, runner, mock_conn):
        """analyze status --type classify --json exits non-zero."""
        result = runner.invoke(
            main,
            ["analyze", "status", "--type", "classify", "--json"],
            obj={"db_conn": mock_conn},
        )
        assert result.exit_code != 0
        assert "not yet implemented" in result.output.lower()


class TestClearCommand:
    """Tests for the analyze clear subcommand."""

    def test_clear_help(self, runner):
        """Test that clear help is displayed."""
        result = runner.invoke(main, ["analyze", "clear", "--help"])
        assert result.exit_code == 0
        assert "--all" in result.output
        assert "--recursive" in result.output
        assert "--yes" in result.output
        assert "--dry-run" in result.output

    def test_clear_requires_path_or_all(self, runner, mock_conn):
        """Test error when neither path nor --all specified."""
        result = runner.invoke(
            main,
            ["analyze", "clear", "--type", "language"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == ExitCode.INVALID_ARGUMENTS
        assert "Specify a PATH or use --all" in result.output

    @patch("vpo.cli.analyze._count_language_results")
    def test_clear_dry_run(self, mock_count, runner, mock_conn):
        """Test dry-run output."""
        mock_count.return_value = (10, 25)

        result = runner.invoke(
            main,
            ["analyze", "clear", "--type", "language", "--all", "--dry-run"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        assert "Would clear" in result.output
        assert "10" in result.output
        assert "25" in result.output

    @patch("vpo.cli.analyze._count_language_results")
    def test_clear_dry_run_json(self, mock_count, runner, mock_conn):
        """Test dry-run with JSON output."""
        mock_count.return_value = (10, 25)

        result = runner.invoke(
            main,
            ["analyze", "clear", "--type", "language", "--all", "--dry-run", "--json"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["files_affected"] == 10
        assert data["language_cleared"] == 25

    @patch("vpo.cli.analyze._count_language_results")
    def test_clear_nothing_to_clear(self, mock_count, runner, mock_conn):
        """Test when there's nothing to clear."""
        mock_count.return_value = (0, 0)

        result = runner.invoke(
            main,
            ["analyze", "clear", "--type", "language", "--all"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        assert "No analysis results to clear" in result.output

    @patch("vpo.cli.analyze._count_language_results")
    @patch("vpo.cli.analyze._clear_language_results")
    def test_clear_all_confirmed(self, mock_clear, mock_count, runner, mock_conn):
        """Test clear all with confirmation."""
        mock_count.return_value = (10, 25)
        mock_clear.return_value = 25

        result = runner.invoke(
            main,
            ["analyze", "clear", "--type", "language", "--all", "--yes"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        assert "Cleared analysis results" in result.output
        assert "10" in result.output
        mock_clear.assert_called_once()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_check_plugin_available_no_registry(self):
        """Test plugin check when registry not available."""
        with patch(
            "vpo.cli.analyze.get_default_registry",
            side_effect=ImportError,
        ):
            assert _check_plugin_available() is False

    def test_check_plugin_available_no_plugins(self):
        """Test plugin check when no plugins available."""
        mock_registry = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.is_available.return_value = False
        with (
            patch("vpo.cli.analyze.get_default_registry") as mock_get_registry,
            patch(
                "vpo.transcription.coordinator.TranscriptionCoordinator"
            ) as mock_coord_class,
        ):
            mock_get_registry.return_value = mock_registry
            mock_coord_class.return_value = mock_coordinator
            assert _check_plugin_available() is False

    def test_check_plugin_available_success(self):
        """Test plugin check when plugin is available."""
        mock_registry = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.is_available.return_value = True
        with (
            patch("vpo.cli.analyze.get_default_registry") as mock_get_registry,
            patch(
                "vpo.transcription.coordinator.TranscriptionCoordinator"
            ) as mock_coord_class,
        ):
            mock_get_registry.return_value = mock_registry
            mock_coord_class.return_value = mock_coordinator
            assert _check_plugin_available() is True

    def test_resolve_files_single_file(self, mock_conn, mock_file_record, tmp_path):
        """Test resolving a single file path."""
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("vpo.cli.analyze.get_file_by_path") as mock_get:
            mock_get.return_value = mock_file_record
            files, not_found = _resolve_files_from_paths(
                mock_conn, (str(test_file),), recursive=False
            )

        assert len(files) == 1
        assert files[0] == mock_file_record
        assert not_found == []

    def test_resolve_files_not_in_database(self, mock_conn, tmp_path):
        """Test resolving a file not in database."""
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("vpo.cli.analyze.get_file_by_path") as mock_get:
            mock_get.return_value = None
            files, not_found = _resolve_files_from_paths(
                mock_conn, (str(test_file),), recursive=False
            )

        assert files == []
        assert len(not_found) == 1
        assert str(test_file) in not_found[0]


class TestLanguageAnalysisRunResult:
    """Tests for LanguageAnalysisRunResult dataclass."""

    def test_dataclass_defaults(self):
        """Test that dataclass has correct defaults."""
        result = LanguageAnalysisRunResult(
            file_path="/test.mkv",
            success=True,
            track_count=2,
            analyzed_count=2,
            cached_count=0,
        )

        assert result.error is None
        assert result.duration_ms == 0

    def test_dataclass_with_error(self):
        """Test dataclass with error set."""
        result = LanguageAnalysisRunResult(
            file_path="/test.mkv",
            success=False,
            track_count=2,
            analyzed_count=0,
            cached_count=0,
            error="Test error",
            duration_ms=500,
        )

        assert result.success is False
        assert result.error == "Test error"
        assert result.duration_ms == 500
