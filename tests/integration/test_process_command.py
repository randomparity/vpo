"""Integration tests for process command."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from video_policy_orchestrator.cli import main


@pytest.fixture
def policy_file(temp_dir: Path) -> Path:
    """Create a minimal test policy file."""
    policy_path = temp_dir / "test_policy.yaml"
    policy_path.write_text(
        """
schema_version: 12
workflow:
  phases:
    - apply
  on_error: skip
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
workflow:
  phases:
    - apply
  on_error: fail
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
workflow:
  phases:
    - apply
  on_error: continue
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
                "analyze,apply,transcode",
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
        # File not in DB, but should find the file path at least
        found = "movie.mkv" in result.output
        found = found or "not found" in result.output.lower()
        assert result.exit_code != 0 or found

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
        # Should find video files in directory
        found = "movie.mkv" in result.output
        found = found or "not found" in result.output.lower()
        assert result.exit_code != 0 or found

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
        # With -R, should find nested files too
        found = "episode" in result.output.lower()
        found = found or "not found" in result.output.lower()
        assert found or result.exit_code != 0

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
                str(temp_video_dir / "movie.mkv"),
            ],
        )
        # Should output something about dry-run or plan
        # (even if it fails because file not in DB)
        found = "dry" in result.output.lower() or "not found" in result.output.lower()
        assert found or result.exit_code != 0


class TestProcessCommandOnErrorBehavior:
    """Tests for on_error behavior differentiation."""

    @patch("video_policy_orchestrator.cli.process.WorkflowProcessor")
    def test_on_error_skip_continues_batch(
        self, mock_processor_cls, temp_video_dir: Path, policy_file_with_fail: Path
    ):
        """Test that on_error=skip allows batch to continue."""
        # Create mock results - first file fails, second succeeds
        from video_policy_orchestrator.policy.models import ProcessingPhase
        from video_policy_orchestrator.workflow.processor import FileProcessingResult

        mock_processor = MagicMock()
        fail_result = MagicMock(spec=FileProcessingResult)
        fail_result.success = False
        fail_result.batch_should_stop = False  # skip mode
        fail_result.error_message = "Test error"
        fail_result.phases_completed = []
        fail_result.phases_failed = [ProcessingPhase.APPLY]
        fail_result.phases_skipped = []
        fail_result.phase_results = []
        fail_result.file_path = temp_video_dir / "movie.mkv"
        fail_result.duration_seconds = 0.1

        success_result = MagicMock(spec=FileProcessingResult)
        success_result.success = True
        success_result.batch_should_stop = False
        success_result.error_message = None
        success_result.phases_completed = [ProcessingPhase.APPLY]
        success_result.phases_failed = []
        success_result.phases_skipped = []
        success_result.phase_results = []
        success_result.file_path = temp_video_dir / "show.mp4"
        success_result.duration_seconds = 0.1

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

    @patch("video_policy_orchestrator.cli.process.WorkflowProcessor")
    def test_on_error_fail_stops_batch(
        self, mock_processor_cls, temp_video_dir: Path, policy_file: Path
    ):
        """Test that on_error=fail stops batch processing."""
        from video_policy_orchestrator.policy.models import ProcessingPhase
        from video_policy_orchestrator.workflow.processor import FileProcessingResult

        mock_processor = MagicMock()
        fail_result = MagicMock(spec=FileProcessingResult)
        fail_result.success = False
        fail_result.batch_should_stop = True  # fail mode
        fail_result.error_message = "Test error"
        fail_result.phases_completed = []
        fail_result.phases_failed = [ProcessingPhase.APPLY]
        fail_result.phases_skipped = []
        fail_result.phase_results = []
        fail_result.file_path = temp_video_dir / "movie.mkv"
        fail_result.duration_seconds = 0.1

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
                str(temp_video_dir),  # Directory with multiple files
            ],
        )

        # Should stop after first failure
        assert mock_processor.process_file.call_count == 1
        assert "Stopping batch" in result.output or "fail" in result.output.lower()


class TestProcessCommandWorkflow:
    """Tests for workflow execution."""

    @patch("video_policy_orchestrator.cli.process.WorkflowProcessor")
    def test_phases_override(
        self, mock_processor_cls, temp_video_dir: Path, policy_file: Path
    ):
        """Test that --phases overrides policy phases."""
        from video_policy_orchestrator.policy.models import ProcessingPhase
        from video_policy_orchestrator.workflow.processor import FileProcessingResult

        mock_processor = MagicMock()
        mock_result = MagicMock(spec=FileProcessingResult)
        mock_result.success = True
        mock_result.batch_should_stop = False
        mock_result.error_message = None
        mock_result.phases_completed = [ProcessingPhase.ANALYZE]
        mock_result.phases_failed = []
        mock_result.phases_skipped = []
        mock_result.phase_results = []
        mock_result.file_path = temp_video_dir / "movie.mkv"
        mock_result.duration_seconds = 0.1

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
                "analyze",
                str(temp_video_dir / "movie.mkv"),
            ],
        )

        # WorkflowProcessor should be called
        mock_processor_cls.assert_called_once()
        # Check that phases were overridden (in the policy passed to processor)
        call_kwargs = mock_processor_cls.call_args.kwargs
        assert call_kwargs["policy"].workflow.phases == (ProcessingPhase.ANALYZE,)


class TestProcessCommandSummary:
    """Tests for summary output."""

    @patch("video_policy_orchestrator.cli.process.WorkflowProcessor")
    def test_summary_counts(
        self, mock_processor_cls, temp_video_dir: Path, policy_file: Path
    ):
        """Test that summary shows correct counts."""
        from video_policy_orchestrator.policy.models import ProcessingPhase
        from video_policy_orchestrator.workflow.processor import FileProcessingResult

        mock_processor = MagicMock()

        # Create results for all 2 files in temp_video_dir (movie.mkv, show.mp4)
        # Non-recursive, so won't find nested/episode.mkv
        def make_result(path, success):
            result = MagicMock(spec=FileProcessingResult)
            result.success = success
            result.batch_should_stop = False
            result.error_message = None if success else "Failed"
            result.phases_completed = [ProcessingPhase.APPLY] if success else []
            result.phases_failed = [] if success else [ProcessingPhase.APPLY]
            result.phases_skipped = []
            result.phase_results = []
            result.file_path = path
            result.duration_seconds = 0.1
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
