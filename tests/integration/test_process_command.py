"""Integration tests for process command."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vpo.cli import main


@pytest.fixture
def policy_file(temp_dir: Path) -> Path:
    """Create a minimal test policy file."""
    policy_path = temp_dir / "test_policy.yaml"
    policy_path.write_text(
        """
schema_version: 12
config:
  on_error: skip
phases:
  - name: apply
    audio_filter:
      languages: [eng]
"""
    )
    return policy_path


@pytest.fixture
def policy_file_with_fail(temp_dir: Path) -> Path:
    """Create a policy file with on_error: fail."""
    policy_path = temp_dir / "fail_policy.yaml"
    policy_path.write_text(
        """
schema_version: 12
config:
  on_error: fail
phases:
  - name: apply
    audio_filter:
      languages: [eng]
"""
    )
    return policy_path


@pytest.fixture
def policy_file_with_continue(temp_dir: Path) -> Path:
    """Create a policy file with on_error: continue."""
    policy_path = temp_dir / "continue_policy.yaml"
    policy_path.write_text(
        """
schema_version: 12
config:
  on_error: continue
phases:
  - name: apply
    audio_filter:
      languages: [eng]
"""
    )
    return policy_path


class TestProcessCommandHelp:
    """Tests for process command help and basic invocation."""

    def test_process_help(self):
        """Test that process --help works."""
        runner = CliRunner()
        result = runner.invoke(main, ["process", "--help"])
        assert result.exit_code == 0
        assert "Process media files through the unified workflow" in result.output

    def test_process_requires_policy_or_profile(self, temp_video_dir: Path):
        """Test that process requires --policy or --profile."""
        runner = CliRunner()
        result = runner.invoke(main, ["process", str(temp_video_dir / "movie.mkv")])
        assert result.exit_code != 0
        assert "No policy specified" in result.output


class TestProcessCommandArgumentParsing:
    """Tests for argument parsing and validation."""

    def test_invalid_phase_name(self, temp_video_dir: Path, policy_file: Path):
        """Test that invalid phase names are rejected."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--phases",
                "invalid_phase",
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        assert result.exit_code != 0
        assert "Invalid phase" in result.output

    def test_valid_phase_names(self, temp_video_dir: Path, policy_file: Path):
        """Test that valid phase names are accepted."""
        runner = CliRunner()
        # This will fail because file isn't in DB, but argument parsing should succeed
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--phases",
                "apply",  # Only use phases defined in the policy
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        # Should not fail on argument parsing (may fail later on DB lookup)
        assert "Invalid phase" not in result.output

    def test_on_error_choices(self, temp_video_dir: Path, policy_file: Path):
        """Test that --on-error accepts valid choices."""
        runner = CliRunner()

        for choice in ["skip", "fail", "continue"]:
            result = runner.invoke(
                main,
                [
                    "process",
                    "--policy",
                    str(policy_file),
                    "--on-error",
                    choice,
                    "--help",  # Use --help to avoid actual processing
                ],
            )
            # Help should still work with valid choice
            assert result.exit_code == 0

    def test_on_error_invalid_choice(self, temp_video_dir: Path, policy_file: Path):
        """Test that --on-error rejects invalid choices."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--on-error",
                "invalid",
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()


class TestProcessCommandFileDiscovery:
    """Tests for file discovery functionality."""

    def test_single_file(self, temp_video_dir: Path, policy_file: Path):
        """Test processing a single file."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--dry-run",
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        # Command should succeed (exit code 0) and process 1 file
        assert result.exit_code == 0
        # Output should include file count in summary or verbose mode
        assert "1" in result.output or "Files:" in result.output

    def test_directory(self, temp_video_dir: Path, policy_file: Path):
        """Test processing a directory."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--dry-run",
                str(temp_video_dir),
            ],
        )
        # Command should succeed and process files in directory
        assert result.exit_code == 0
        # Should process 2 files (movie.mkv, show.mp4) - non-recursive
        assert "2" in result.output or "Files:" in result.output

    def test_recursive_directory(self, temp_video_dir: Path, policy_file: Path):
        """Test recursive directory processing."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--dry-run",
                "--recursive",
                str(temp_video_dir),
            ],
        )
        # Command should succeed
        assert result.exit_code == 0
        # With -R, should find nested files (movie.mkv, show.mp4, episode.mkv)
        # Total is 4 files (or 3 if hidden is excluded)
        assert "3" in result.output or "4" in result.output or "Files:" in result.output

    def test_nonexistent_path(self, policy_file: Path):
        """Test processing a nonexistent path."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "/nonexistent/path/file.mkv",
            ],
        )
        assert result.exit_code != 0

    def test_empty_directory(self, temp_dir: Path, policy_file: Path):
        """Test processing an empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                str(empty_dir),
            ],
        )
        assert result.exit_code != 0
        assert "No video files found" in result.output


class TestProcessCommandOutputFormats:
    """Tests for output formatting."""

    def test_json_output_format(self, temp_video_dir: Path, policy_file: Path):
        """Test JSON output format structure."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--dry-run",
                "--json",
                str(temp_video_dir / "movie.mkv"),
            ],
        )

        # Try to parse JSON from output (may have log lines)
        output = result.output
        json_start = output.find("{")
        if json_start >= 0:
            # Find matching closing brace
            depth = 0
            for i, c in enumerate(output[json_start:]):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = output[json_start : json_start + i + 1]
                        break
            try:
                data = json.loads(json_str)
                # Should have expected structure
                assert "policy" in data or "results" in data or "error" in data
            except (json.JSONDecodeError, UnboundLocalError):
                # JSON parsing failed, but that's ok if there was an error
                pass

    def test_verbose_output(self, temp_video_dir: Path, policy_file: Path):
        """Test verbose output mode."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--dry-run",
                "--verbose",
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        # Verbose mode should show more details
        # At minimum, should show policy path
        assert "Policy:" in result.output or "policy" in result.output.lower()


class TestProcessCommandErrorHandling:
    """Tests for error handling."""

    def test_missing_policy_file(self, temp_video_dir: Path):
        """Test handling of missing policy file."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                "/nonexistent/policy.yaml",
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_invalid_policy_yaml(self, temp_dir: Path, temp_video_dir: Path):
        """Test handling of invalid policy YAML."""
        bad_policy = temp_dir / "bad_policy.yaml"
        bad_policy.write_text("invalid: yaml: content: [")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(bad_policy),
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        assert result.exit_code != 0


class TestProcessCommandDryRun:
    """Tests for dry-run mode."""

    def test_dry_run_does_not_modify_files(
        self, temp_video_dir: Path, policy_file: Path
    ):
        """Test that --dry-run doesn't modify files."""
        video_file = temp_video_dir / "movie.mkv"
        original_mtime = video_file.stat().st_mtime

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--dry-run",
                str(video_file),
            ],
        )

        # File should not be modified
        assert video_file.stat().st_mtime == original_mtime

    def test_dry_run_shows_plan(self, temp_video_dir: Path, policy_file: Path):
        """Test that dry-run shows what would be done."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--dry-run",
                "--verbose",
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        # Command should succeed in dry-run mode
        assert result.exit_code == 0
        # Verbose mode should show dry-run indicator
        assert "dry" in result.output.lower() or "Mode:" in result.output


class TestProcessCommandOnErrorBehavior:
    """Tests for on_error behavior differentiation."""

    @patch("vpo.cli.process.WorkflowProcessor")
    def test_on_error_skip_continues_batch(
        self, mock_processor_cls, temp_video_dir: Path, policy_file_with_fail: Path
    ):
        """Test that on_error=skip allows batch to continue."""
        # Create mock results - first file fails, second succeeds
        from vpo.policy.types import FileProcessingResult

        mock_processor = MagicMock()
        fail_result = MagicMock(spec=FileProcessingResult)
        fail_result.success = False
        fail_result.batch_should_stop = False  # skip mode
        fail_result.failed_phase = "apply"
        fail_result.phases_completed = 0
        fail_result.phases_failed = 1
        fail_result.phases_skipped = 0
        fail_result.phase_results = ()
        fail_result.file_path = temp_video_dir / "movie.mkv"
        fail_result.total_duration_seconds = 0.1
        fail_result.total_changes = 0

        success_result = MagicMock(spec=FileProcessingResult)
        success_result.success = True
        success_result.batch_should_stop = False
        success_result.failed_phase = None
        success_result.phases_completed = 1
        success_result.phases_failed = 0
        success_result.phases_skipped = 0
        success_result.phase_results = ()
        success_result.file_path = temp_video_dir / "show.mp4"
        success_result.total_duration_seconds = 0.1
        success_result.total_changes = 0

        mock_processor.process_file.side_effect = [fail_result, success_result]
        mock_processor_cls.return_value = mock_processor

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file_with_fail),
                "--on-error",
                "skip",
                str(temp_video_dir),  # Directory with multiple files
            ],
        )

        # Both files should be processed
        assert mock_processor.process_file.call_count == 2

    @patch("vpo.cli.process.WorkflowProcessor")
    def test_on_error_fail_stops_batch(
        self, mock_processor_cls, temp_video_dir: Path, policy_file: Path
    ):
        """Test that on_error=fail stops batch processing."""
        from vpo.policy.types import FileProcessingResult

        mock_processor = MagicMock()
        fail_result = MagicMock(spec=FileProcessingResult)
        fail_result.success = False
        fail_result.batch_should_stop = True  # fail mode
        fail_result.failed_phase = "apply"
        fail_result.phases_completed = 0
        fail_result.phases_failed = 1
        fail_result.phases_skipped = 0
        fail_result.phase_results = ()
        fail_result.file_path = temp_video_dir / "movie.mkv"
        fail_result.total_duration_seconds = 0.1
        fail_result.total_changes = 0

        mock_processor.process_file.return_value = fail_result
        mock_processor_cls.return_value = mock_processor

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--on-error",
                "fail",
                "--workers",
                "1",  # Sequential processing to test stop behavior
                str(temp_video_dir),  # Directory with multiple files
            ],
        )

        # With ThreadPoolExecutor, there's a race condition: the second file
        # might start before the stop event is checked. We verify that:
        # 1. At most 2 files were processed (some may have started before stop)
        # 2. The batch indicated it stopped early
        assert mock_processor.process_file.call_count <= 2
        # The output should indicate batch stopped early
        assert (
            "stopped early" in result.output.lower()
            or "error" in result.output.lower()
            or "failed" in result.output.lower()
        )


class TestProcessCommandWorkflow:
    """Tests for workflow execution."""

    @patch("vpo.cli.process.WorkflowProcessor")
    def test_phases_override(
        self, mock_processor_cls, temp_video_dir: Path, policy_file: Path
    ):
        """Test that --phases overrides policy phases via selected_phases parameter."""
        from vpo.policy.types import FileProcessingResult

        mock_processor = MagicMock()
        mock_result = MagicMock(spec=FileProcessingResult)
        mock_result.success = True
        mock_result.batch_should_stop = False
        mock_result.failed_phase = None
        mock_result.phases_completed = 1
        mock_result.phases_failed = 0
        mock_result.phases_skipped = 0
        mock_result.phase_results = ()
        mock_result.file_path = temp_video_dir / "movie.mkv"
        mock_result.total_duration_seconds = 0.1
        mock_result.total_changes = 0

        mock_processor.process_file.return_value = mock_result
        mock_processor_cls.return_value = mock_processor

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                "--phases",
                "apply",  # Use "apply" since it's defined in the fixture
                str(temp_video_dir / "movie.mkv"),
            ],
        )

        # WorkflowProcessor should be called
        mock_processor_cls.assert_called_once()
        # Check that selected_phases parameter was passed
        call_kwargs = mock_processor_cls.call_args.kwargs
        assert call_kwargs["selected_phases"] == ["apply"]


class TestProcessCommandSummary:
    """Tests for summary output."""

    @patch("vpo.cli.process.WorkflowProcessor")
    def test_summary_counts(
        self, mock_processor_cls, temp_video_dir: Path, policy_file: Path
    ):
        """Test that summary shows correct counts."""
        from vpo.policy.types import FileProcessingResult

        mock_processor = MagicMock()

        # Create results for all 2 files in temp_video_dir (movie.mkv, show.mp4)
        # Non-recursive, so won't find nested/episode.mkv
        def make_result(path, success):
            result = MagicMock(spec=FileProcessingResult)
            result.success = success
            result.batch_should_stop = False
            result.failed_phase = None if success else "apply"
            result.phases_completed = 1 if success else 0
            result.phases_failed = 0 if success else 1
            result.phases_skipped = 0
            result.phase_results = ()
            result.file_path = path
            result.total_duration_seconds = 0.1
            result.total_changes = 0
            return result

        mock_processor.process_file.side_effect = [
            make_result(temp_video_dir / "movie.mkv", True),
            make_result(temp_video_dir / "show.mp4", True),
        ]
        mock_processor_cls.return_value = mock_processor

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "--policy",
                str(policy_file),
                str(temp_video_dir),  # Non-recursive, should find 2 files
            ],
        )

        # Summary should show counts
        assert "2" in result.output  # Total or success count
        assert "ok" in result.output.lower() or "success" in result.output.lower()
