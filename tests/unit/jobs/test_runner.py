"""Tests for unified workflow runner."""

from pathlib import Path
from unittest.mock import MagicMock

from vpo.jobs.runner import (
    NullJobLifecycle,
    WorkflowRunnerConfig,
    WorkflowRunResult,
    _create_error_result,
)
from vpo.policy.types import FileProcessingResult


class TestWorkflowRunnerConfig:
    """Tests for WorkflowRunnerConfig dataclass."""

    def test_defaults(self):
        """Config has sensible defaults."""
        config = WorkflowRunnerConfig()

        assert config.dry_run is False
        assert config.verbose is False
        assert config.selected_phases is None
        assert config.policy_name == ""

    def test_custom_values(self):
        """Config accepts custom values."""
        config = WorkflowRunnerConfig(
            dry_run=True,
            verbose=True,
            selected_phases=["analyze", "apply"],
            policy_name="test.yaml",
        )

        assert config.dry_run is True
        assert config.verbose is True
        assert config.selected_phases == ["analyze", "apply"]
        assert config.policy_name == "test.yaml"


class TestNullJobLifecycle:
    """Tests for NullJobLifecycle (no-op implementation)."""

    def test_on_job_start_returns_none(self):
        """on_job_start returns None (no job created)."""
        lifecycle = NullJobLifecycle()
        result = lifecycle.on_job_start(Path("/test/file.mkv"), "policy.yaml")

        assert result is None

    def test_on_job_complete_is_noop(self):
        """on_job_complete completes without error."""
        lifecycle = NullJobLifecycle()
        mock_result = MagicMock(spec=FileProcessingResult)

        # Should not raise
        lifecycle.on_job_complete("job-123", mock_result)

    def test_on_job_fail_is_noop(self):
        """on_job_fail completes without error."""
        lifecycle = NullJobLifecycle()

        # Should not raise
        lifecycle.on_job_fail("job-123", "test error")


class TestWorkflowRunResult:
    """Tests for WorkflowRunResult dataclass."""

    def test_success_from_result_true(self):
        """success is True when result.success is True."""
        mock_result = MagicMock(spec=FileProcessingResult)
        mock_result.success = True

        run_result = WorkflowRunResult(result=mock_result, job_id="job-123")

        assert run_result.success is True

    def test_success_from_result_false(self):
        """success is False when result.success is False."""
        mock_result = MagicMock(spec=FileProcessingResult)
        mock_result.success = False

        run_result = WorkflowRunResult(result=mock_result, job_id="job-123")

        assert run_result.success is False

    def test_job_id_optional(self):
        """job_id is optional."""
        mock_result = MagicMock(spec=FileProcessingResult)
        mock_result.success = True

        run_result = WorkflowRunResult(result=mock_result)

        assert run_result.job_id is None


class TestCreateErrorResult:
    """Tests for _create_error_result helper."""

    def test_creates_failure_result(self):
        """Creates a FileProcessingResult representing failure."""
        path = Path("/test/file.mkv")
        error = "Test error message"

        result = _create_error_result(path, error)

        assert result.file_path == path
        assert result.success is False
        assert result.error_message == error
        assert result.phases_completed == 0
        assert result.phases_failed == 0
        assert result.total_changes == 0

    def test_empty_phase_results(self):
        """Error result has empty phase_results tuple."""
        result = _create_error_result(Path("/test.mkv"), "error")

        assert result.phase_results == ()
