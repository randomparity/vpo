"""Integration tests for the report CLI commands."""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from video_policy_orchestrator.cli import main


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


class TestReportHelp:
    """Tests for report command help."""

    def test_report_group_help(self, runner):
        """Show help for report group."""
        result = runner.invoke(main, ["report", "--help"])
        assert result.exit_code == 0
        assert "Generate reports" in result.output
        assert "jobs" in result.output
        assert "library" in result.output
        assert "scans" in result.output
        assert "transcodes" in result.output
        assert "policy-apply" in result.output

    def test_jobs_help(self, runner):
        """Show help for jobs subcommand."""
        result = runner.invoke(main, ["report", "jobs", "--help"])
        assert result.exit_code == 0
        assert "--type" in result.output
        assert "--status" in result.output
        assert "--format" in result.output

    def test_library_help(self, runner):
        """Show help for library subcommand."""
        result = runner.invoke(main, ["report", "library", "--help"])
        assert result.exit_code == 0
        assert "--resolution" in result.output
        assert "--language" in result.output
        assert "--has-subtitles" in result.output

    def test_scans_help(self, runner):
        """Show help for scans subcommand."""
        result = runner.invoke(main, ["report", "scans", "--help"])
        assert result.exit_code == 0
        assert "--since" in result.output
        assert "--format" in result.output

    def test_transcodes_help(self, runner):
        """Show help for transcodes subcommand."""
        result = runner.invoke(main, ["report", "transcodes", "--help"])
        assert result.exit_code == 0
        assert "--codec" in result.output
        assert "--format" in result.output

    def test_policy_apply_help(self, runner):
        """Show help for policy-apply subcommand."""
        result = runner.invoke(main, ["report", "policy-apply", "--help"])
        assert result.exit_code == 0
        assert "--policy" in result.output
        assert "--verbose" in result.output


class TestReportJobsWithMock:
    """Tests for vpo report jobs command with mocked queries."""

    def test_list_all_jobs(self, runner):
        """List all jobs with mocked data."""
        mock_rows = [
            {
                "job_id": "scan-001",
                "type": "scan",
                "status": "completed",
                "target": "/movies",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "error": "-",
            },
            {
                "job_id": "tc-002",
                "type": "transcode",
                "status": "completed",
                "target": "/movies/movie1.mkv",
                "started_at": "2025-01-15 13:00:00",
                "completed_at": "2025-01-15 13:30:00",
                "duration": "30m 0s",
                "error": "-",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(main, ["report", "jobs"])
            assert result.exit_code == 0
            assert "scan-001" in result.output
            assert "tc-002" in result.output
            assert "completed" in result.output

    def test_filter_by_type(self, runner):
        """Filter jobs by type."""
        mock_rows = [
            {
                "job_id": "scan-001",
                "type": "scan",
                "status": "completed",
                "target": "/movies",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "error": "-",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ) as mock_query:
            result = runner.invoke(main, ["report", "jobs", "--type", "scan"])
            assert result.exit_code == 0
            # Verify the filter was passed correctly
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["job_type"] == "scan"

    def test_json_format(self, runner):
        """Output in JSON format."""
        mock_rows = [
            {
                "job_id": "scan-001",
                "type": "scan",
                "status": "completed",
                "target": "/movies",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "error": "-",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(main, ["report", "jobs", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["job_id"] == "scan-001"

    def test_csv_format(self, runner):
        """Output in CSV format."""
        mock_rows = [
            {
                "job_id": "scan-001",
                "type": "scan",
                "status": "completed",
                "target": "/movies",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "error": "-",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(main, ["report", "jobs", "--format", "csv"])
            assert result.exit_code == 0
            assert "job_id" in result.output
            assert "scan-001" in result.output
            lines = result.output.strip().split("\n")
            assert len(lines) == 2  # Header + 1 data row

    def test_empty_results(self, runner):
        """Handle empty results."""
        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report", return_value=[]
        ):
            result = runner.invoke(main, ["report", "jobs"])
            assert result.exit_code == 0
            assert "No records found" in result.output


class TestReportLibraryWithMock:
    """Tests for vpo report library command with mocked queries."""

    def test_list_all_files(self, runner):
        """List all library files."""
        mock_rows = [
            {
                "path": "/movies/movie1.mkv",
                "title": "movie1",
                "container": "mkv",
                "resolution": "1080p",
                "audio_languages": "eng",
                "has_subtitles": "Yes",
                "scanned_at": "2025-01-15 12:00:00",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_library_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(main, ["report", "library"])
            assert result.exit_code == 0
            assert "movie1.mkv" in result.output
            assert "1080p" in result.output

    def test_filter_by_resolution(self, runner):
        """Filter by resolution."""
        mock_rows = [
            {
                "path": "/movies/4k-movie.mkv",
                "title": "4k-movie",
                "container": "mkv",
                "resolution": "4K",
                "audio_languages": "eng",
                "has_subtitles": "No",
                "scanned_at": "2025-01-15 12:00:00",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_library_report",
            return_value=mock_rows,
        ) as mock_query:
            result = runner.invoke(main, ["report", "library", "--resolution", "4K"])
            assert result.exit_code == 0
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["resolution"] == "4K"

    def test_conflicting_subtitle_flags(self, runner):
        """Error on conflicting subtitle flags."""
        result = runner.invoke(
            main, ["report", "library", "--has-subtitles", "--no-subtitles"]
        )
        assert result.exit_code != 0
        assert "Cannot use both" in result.output


class TestReportScansWithMock:
    """Tests for vpo report scans command with mocked queries."""

    def test_list_scans(self, runner):
        """List scan operations."""
        mock_rows = [
            {
                "scan_id": "scan-001",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "files_scanned": 100,
                "files_new": 10,
                "files_changed": 5,
                "status": "completed",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_scans_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(main, ["report", "scans"])
            assert result.exit_code == 0
            assert "scan-001" in result.output
            assert "100" in result.output  # files_scanned

    def test_json_format(self, runner):
        """Output in JSON format."""
        mock_rows = [
            {
                "scan_id": "scan-001",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "files_scanned": 100,
                "files_new": 10,
                "files_changed": 5,
                "status": "completed",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_scans_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(main, ["report", "scans", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data) == 1
            assert data[0]["files_scanned"] == 100


class TestReportTranscodesWithMock:
    """Tests for vpo report transcodes command with mocked queries."""

    def test_list_transcodes(self, runner):
        """List transcode operations."""
        mock_rows = [
            {
                "job_id": "tc-001",
                "file_path": "/movies/movie.mkv",
                "source_codec": "h264",
                "target_codec": "hevc",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:30:00",
                "duration": "30m 0s",
                "status": "completed",
                "size_change": "-25%",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_transcodes_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(main, ["report", "transcodes"])
            assert result.exit_code == 0
            assert "hevc" in result.output

    def test_filter_by_codec(self, runner):
        """Filter by target codec."""
        mock_rows = []

        with patch(
            "video_policy_orchestrator.reports.queries.get_transcodes_report",
            return_value=mock_rows,
        ) as mock_query:
            result = runner.invoke(main, ["report", "transcodes", "--codec", "hevc"])
            assert result.exit_code == 0
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["codec"] == "hevc"


class TestReportPolicyApplyWithMock:
    """Tests for vpo report policy-apply command with mocked queries."""

    def test_list_applications(self, runner):
        """List policy applications."""
        mock_rows = [
            {
                "operation_id": "apply-01",
                "policy_name": "normalize.yaml",
                "files_affected": 5,
                "metadata_changes": 10,
                "heavy_changes": 2,
                "status": "completed",
                "started_at": "2025-01-15 12:00:00",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_policy_apply_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(main, ["report", "policy-apply"])
            assert result.exit_code == 0
            assert "normalize" in result.output

    def test_verbose_mode(self, runner):
        """Show per-file details in verbose mode."""
        mock_rows = [
            {
                "file_path": "/movies/movie1.mkv",
                "changes": "set_title, set_language",
            },
        ]

        with patch(
            "video_policy_orchestrator.reports.queries.get_policy_apply_report",
            return_value=mock_rows,
        ) as mock_query:
            result = runner.invoke(main, ["report", "policy-apply", "--verbose"])
            assert result.exit_code == 0
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["verbose"] is True


class TestReportFileOutput:
    """Tests for file output functionality."""

    def test_write_to_file(self, runner, tmp_path):
        """Write report to file."""
        mock_rows = [
            {
                "job_id": "scan-001",
                "type": "scan",
                "status": "completed",
                "target": "/movies",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "error": "-",
            },
        ]

        output_file = tmp_path / "report.csv"

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(
                main,
                ["report", "jobs", "--format", "csv", "--output", str(output_file)],
            )
            assert result.exit_code == 0
            assert output_file.exists()
            content = output_file.read_text()
            assert "job_id" in content
            assert "scan-001" in content

    def test_no_overwrite_without_force(self, runner, tmp_path):
        """Don't overwrite existing file without --force."""
        mock_rows = [
            {
                "job_id": "scan-001",
                "type": "scan",
                "status": "completed",
                "target": "/movies",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "error": "-",
            },
        ]

        output_file = tmp_path / "report.csv"
        output_file.write_text("existing content")

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(
                main,
                ["report", "jobs", "--format", "csv", "--output", str(output_file)],
            )
            assert result.exit_code != 0
            assert "exists" in result.output.lower() or "force" in result.output.lower()
            # Verify file wasn't overwritten
            assert output_file.read_text() == "existing content"

    def test_overwrite_with_force(self, runner, tmp_path):
        """Overwrite existing file with --force."""
        mock_rows = [
            {
                "job_id": "scan-001",
                "type": "scan",
                "status": "completed",
                "target": "/movies",
                "started_at": "2025-01-15 12:00:00",
                "completed_at": "2025-01-15 12:05:00",
                "duration": "5m 0s",
                "error": "-",
            },
        ]

        output_file = tmp_path / "report.csv"
        output_file.write_text("existing content")

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ):
            result = runner.invoke(
                main,
                [
                    "report",
                    "jobs",
                    "--format",
                    "csv",
                    "--output",
                    str(output_file),
                    "--force",
                ],
            )
            assert result.exit_code == 0
            content = output_file.read_text()
            assert "job_id" in content
            assert "existing content" not in content


class TestReportTimeFilters:
    """Tests for time filter options."""

    def test_since_filter(self, runner):
        """Test --since filter is passed correctly."""
        mock_rows = []

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ) as mock_query:
            result = runner.invoke(main, ["report", "jobs", "--since", "7d"])
            assert result.exit_code == 0
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["time_filter"] is not None
            assert call_kwargs["time_filter"].since is not None

    def test_until_filter(self, runner):
        """Test --until filter is passed correctly."""
        mock_rows = []

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ) as mock_query:
            result = runner.invoke(main, ["report", "jobs", "--until", "1d"])
            assert result.exit_code == 0
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["time_filter"] is not None
            assert call_kwargs["time_filter"].until is not None

    def test_invalid_time_format(self, runner):
        """Test error for invalid time format."""
        result = runner.invoke(main, ["report", "jobs", "--since", "invalid"])
        assert result.exit_code != 0
        assert "Invalid time format" in result.output


class TestReportLimitOptions:
    """Tests for limit options."""

    def test_limit_option(self, runner):
        """Test --limit option is passed correctly."""
        mock_rows = []

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ) as mock_query:
            result = runner.invoke(main, ["report", "jobs", "--limit", "50"])
            assert result.exit_code == 0
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["limit"] == 50

    def test_no_limit_option(self, runner):
        """Test --no-limit option is passed correctly."""
        mock_rows = []

        with patch(
            "video_policy_orchestrator.reports.queries.get_jobs_report",
            return_value=mock_rows,
        ) as mock_query:
            result = runner.invoke(main, ["report", "jobs", "--no-limit"])
            assert result.exit_code == 0
            call_kwargs = mock_query.call_args[1]
            assert call_kwargs["limit"] is None
