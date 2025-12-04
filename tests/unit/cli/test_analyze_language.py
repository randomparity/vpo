"""Unit tests for analyze-language CLI commands.

Tests cover the run, status, and clear subcommands with various options.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from video_policy_orchestrator.cli import main
from video_policy_orchestrator.cli.analyze_language import (
    AnalysisRunResult,
    _check_plugin_available,
    _resolve_files_from_paths,
)


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_conn():
    """Create a mock database connection."""
    return MagicMock()


@pytest.fixture
def mock_file_record():
    """Create a mock FileRecord for testing."""
    from video_policy_orchestrator.db import FileRecord

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
    from video_policy_orchestrator.db import TrackRecord

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


class TestAnalyzeLanguageGroup:
    """Tests for the analyze-language command group."""

    def test_group_help(self, runner):
        """Test that group help is displayed."""
        result = runner.invoke(main, ["analyze-language", "--help"])
        assert result.exit_code == 0
        assert "Analyze and manage multi-language detection results" in result.output
        assert "run" in result.output
        assert "status" in result.output
        assert "clear" in result.output


class TestRunCommand:
    """Tests for the analyze-language run subcommand."""

    def test_run_help(self, runner):
        """Test that run help is displayed."""
        result = runner.invoke(main, ["analyze-language", "run", "--help"])
        assert result.exit_code == 0
        assert "Run language analysis on files" in result.output
        assert "--force" in result.output
        assert "--recursive" in result.output
        assert "--json" in result.output

    @patch("video_policy_orchestrator.cli.analyze_language._check_plugin_available")
    def test_run_no_plugin(self, mock_plugin, runner, mock_conn, tmp_path):
        """Test error when transcription plugin not available."""
        mock_plugin.return_value = False
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        result = runner.invoke(
            main,
            ["analyze-language", "run", str(test_file)],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 1
        assert "Whisper transcription plugin not installed" in result.output

    @patch("video_policy_orchestrator.cli.analyze_language._check_plugin_available")
    @patch("video_policy_orchestrator.cli.analyze_language._resolve_files_from_paths")
    def test_run_no_files_found(
        self, mock_resolve, mock_plugin, runner, mock_conn, tmp_path
    ):
        """Test error when no files found in database."""
        mock_plugin.return_value = True
        mock_resolve.return_value = ([], [str(tmp_path / "test.mkv")])
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        result = runner.invoke(
            main,
            ["analyze-language", "run", str(test_file)],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 2
        assert "No valid files found" in result.output

    @patch("video_policy_orchestrator.cli.analyze_language._check_plugin_available")
    @patch("video_policy_orchestrator.cli.analyze_language._resolve_files_from_paths")
    @patch("video_policy_orchestrator.cli.analyze_language._run_analysis_for_file")
    def test_run_success_json(
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
        mock_run.return_value = AnalysisRunResult(
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
            ["analyze-language", "run", str(test_file), "--json"],
            obj={"db_conn": mock_conn},
            catch_exceptions=False,
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert result.output, "No output from command"
        data = json.loads(result.output)
        assert data["successful"] == 1
        assert data["tracks_analyzed"] == 2


class TestStatusCommand:
    """Tests for the analyze-language status subcommand."""

    def test_status_help(self, runner):
        """Test that status help is displayed."""
        result = runner.invoke(main, ["analyze-language", "status", "--help"])
        assert result.exit_code == 0
        assert "View language analysis status" in result.output
        assert "--filter" in result.output
        assert "--json" in result.output
        assert "--limit" in result.output

    @patch("video_policy_orchestrator.db.views.get_analysis_status_summary")
    def test_status_summary_json(self, mock_summary, runner, mock_conn):
        """Test status summary with JSON output."""
        from video_policy_orchestrator.db.types import AnalysisStatusSummary

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
            ["analyze-language", "status", "--json"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_files"] == 100
        assert data["analyzed_tracks"] == 150
        assert data["multi_language_count"] == 10

    @patch("video_policy_orchestrator.db.views.get_analysis_status_summary")
    def test_status_summary_table(self, mock_summary, runner, mock_conn):
        """Test status summary with table output."""
        from video_policy_orchestrator.db.types import AnalysisStatusSummary

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
            ["analyze-language", "status"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        assert "Language Analysis Status" in result.output
        assert "Total files:" in result.output
        assert "100" in result.output
        assert "Multi-language:" in result.output


class TestClearCommand:
    """Tests for the analyze-language clear subcommand."""

    def test_clear_help(self, runner):
        """Test that clear help is displayed."""
        result = runner.invoke(main, ["analyze-language", "clear", "--help"])
        assert result.exit_code == 0
        assert "Clear cached analysis results" in result.output
        assert "--all" in result.output
        assert "--recursive" in result.output
        assert "--yes" in result.output
        assert "--dry-run" in result.output

    def test_clear_requires_path_or_all(self, runner, mock_conn):
        """Test error when neither path nor --all specified."""
        result = runner.invoke(
            main,
            ["analyze-language", "clear"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 2
        assert "Specify a PATH or use --all" in result.output

    @patch("video_policy_orchestrator.cli.analyze_language._count_affected_results")
    def test_clear_dry_run(self, mock_count, runner, mock_conn):
        """Test dry-run output."""
        mock_count.return_value = (10, 25)

        result = runner.invoke(
            main,
            ["analyze-language", "clear", "--all", "--dry-run"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        assert "Would clear" in result.output
        assert "10" in result.output
        assert "25" in result.output

    @patch("video_policy_orchestrator.cli.analyze_language._count_affected_results")
    def test_clear_dry_run_json(self, mock_count, runner, mock_conn):
        """Test dry-run with JSON output."""
        mock_count.return_value = (10, 25)

        result = runner.invoke(
            main,
            ["analyze-language", "clear", "--all", "--dry-run", "--json"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True
        assert data["files_affected"] == 10
        assert data["tracks_cleared"] == 25

    @patch("video_policy_orchestrator.cli.analyze_language._count_affected_results")
    def test_clear_nothing_to_clear(self, mock_count, runner, mock_conn):
        """Test when there's nothing to clear."""
        mock_count.return_value = (0, 0)

        result = runner.invoke(
            main,
            ["analyze-language", "clear", "--all"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        assert "No analysis results to clear" in result.output

    @patch("video_policy_orchestrator.cli.analyze_language._count_affected_results")
    @patch("video_policy_orchestrator.db.queries.delete_all_analysis")
    def test_clear_all_confirmed(self, mock_delete, mock_count, runner, mock_conn):
        """Test clear all with confirmation."""
        mock_count.return_value = (10, 25)
        mock_delete.return_value = 25

        result = runner.invoke(
            main,
            ["analyze-language", "clear", "--all", "--yes"],
            obj={"db_conn": mock_conn},
        )

        assert result.exit_code == 0
        assert "Cleared 25 analysis results" in result.output
        mock_delete.assert_called_once()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_check_plugin_available_no_registry(self):
        """Test plugin check when registry not available."""
        with patch(
            "video_policy_orchestrator.cli.analyze_language.get_default_registry",
            side_effect=ImportError,
        ):
            assert _check_plugin_available() is False

    def test_check_plugin_available_no_plugins(self):
        """Test plugin check when no plugins available."""
        mock_registry = MagicMock()
        mock_coordinator = MagicMock()
        mock_coordinator.is_available.return_value = False
        with (
            patch(
                "video_policy_orchestrator.cli.analyze_language.get_default_registry"
            ) as mock_get_registry,
            patch(
                "video_policy_orchestrator.transcription.coordinator.TranscriptionCoordinator"
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
            patch(
                "video_policy_orchestrator.cli.analyze_language.get_default_registry"
            ) as mock_get_registry,
            patch(
                "video_policy_orchestrator.transcription.coordinator.TranscriptionCoordinator"
            ) as mock_coord_class,
        ):
            mock_get_registry.return_value = mock_registry
            mock_coord_class.return_value = mock_coordinator
            assert _check_plugin_available() is True

    def test_resolve_files_single_file(self, mock_conn, mock_file_record, tmp_path):
        """Test resolving a single file path."""
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch(
            "video_policy_orchestrator.cli.analyze_language.get_file_by_path"
        ) as mock_get:
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

        with patch(
            "video_policy_orchestrator.cli.analyze_language.get_file_by_path"
        ) as mock_get:
            mock_get.return_value = None
            files, not_found = _resolve_files_from_paths(
                mock_conn, (str(test_file),), recursive=False
            )

        assert files == []
        assert len(not_found) == 1
        assert str(test_file) in not_found[0]


class TestAnalysisRunResult:
    """Tests for AnalysisRunResult dataclass."""

    def test_dataclass_defaults(self):
        """Test that dataclass has correct defaults."""
        result = AnalysisRunResult(
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
        result = AnalysisRunResult(
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
