"""Tests for unified workflow runner."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from vpo.jobs.runner import (
    ErrorClassification,
    NullJobLifecycle,
    WorkflowRunner,
    WorkflowRunnerConfig,
    WorkflowRunResult,
    _create_error_result,
    classify_workflow_error,
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


class TestErrorClassification:
    """Tests for error classification."""

    def test_file_not_found_is_permanent(self):
        """FileNotFoundError is classified as permanent."""
        result = classify_workflow_error(FileNotFoundError("file.mkv"))
        assert result == ErrorClassification.PERMANENT

    def test_is_a_directory_is_permanent(self):
        """IsADirectoryError is classified as permanent."""
        result = classify_workflow_error(IsADirectoryError("/path"))
        assert result == ErrorClassification.PERMANENT

    def test_db_locked_is_transient(self):
        """Database locked error is classified as transient."""
        result = classify_workflow_error(sqlite3.OperationalError("database is locked"))
        assert result == ErrorClassification.TRANSIENT

    def test_db_busy_is_transient(self):
        """Database busy error is classified as transient."""
        result = classify_workflow_error(sqlite3.OperationalError("database is busy"))
        assert result == ErrorClassification.TRANSIENT

    def test_disk_full_is_transient(self):
        """Disk full error is classified as transient."""
        result = classify_workflow_error(OSError("no space left on device"))
        assert result == ErrorClassification.TRANSIENT

    def test_permission_error_is_transient(self):
        """Permission error is classified as transient."""
        result = classify_workflow_error(PermissionError("access denied"))
        assert result == ErrorClassification.TRANSIENT

    def test_value_error_is_fatal(self):
        """ValueError is classified as fatal."""
        result = classify_workflow_error(ValueError("bad config"))
        assert result == ErrorClassification.FATAL

    def test_type_error_is_fatal(self):
        """TypeError is classified as fatal."""
        result = classify_workflow_error(TypeError("wrong type"))
        assert result == ErrorClassification.FATAL

    def test_unknown_error_is_permanent(self):
        """Unknown errors default to permanent."""
        result = classify_workflow_error(Exception("unknown"))
        assert result == ErrorClassification.PERMANENT


class TestWorkflowRunnerFactoryMethods:
    """Tests for WorkflowRunner factory methods."""

    def test_for_cli_sets_lifecycle(self):
        """for_cli sets the provided lifecycle."""
        conn = MagicMock()
        policy = MagicMock()
        config = WorkflowRunnerConfig(dry_run=True, policy_name="test")
        lifecycle = MagicMock()

        runner = WorkflowRunner.for_cli(conn, policy, config, lifecycle)

        assert runner.lifecycle is lifecycle
        assert runner.pre_existing_job_id is None

    def test_for_daemon_uses_null_lifecycle(self):
        """for_daemon uses NullJobLifecycle."""
        conn = MagicMock()
        policy = MagicMock()
        config = WorkflowRunnerConfig(dry_run=False, policy_name="test")

        runner = WorkflowRunner.for_daemon(conn, policy, config, job_id="job-123")

        assert isinstance(runner.lifecycle, NullJobLifecycle)
        assert runner.pre_existing_job_id == "job-123"

    def test_for_daemon_sets_job_log(self):
        """for_daemon sets the job log writer."""
        conn = MagicMock()
        policy = MagicMock()
        config = WorkflowRunnerConfig(dry_run=False, policy_name="test")
        job_log = MagicMock()

        runner = WorkflowRunner.for_daemon(
            conn, policy, config, job_id="job-123", job_log=job_log
        )

        assert runner.job_log is job_log

    def test_for_daemon_sets_ffmpeg_callback(self):
        """for_daemon sets the FFmpeg progress callback."""
        conn = MagicMock()
        policy = MagicMock()
        config = WorkflowRunnerConfig(dry_run=False, policy_name="test")
        callback = MagicMock()

        runner = WorkflowRunner.for_daemon(
            conn, policy, config, job_id="job-123", ffmpeg_progress_callback=callback
        )

        assert runner.ffmpeg_progress_callback is callback


class TestWorkflowRunnerRunSingle:
    """Tests for WorkflowRunner.run_single."""

    def test_run_single_file_not_found(self, tmp_path):
        """Missing file returns error result with permanent classification."""
        conn = MagicMock()
        policy = MagicMock()
        config = WorkflowRunnerConfig(dry_run=True, policy_name="test")

        runner = WorkflowRunner.for_cli(conn, policy, config, NullJobLifecycle())
        result = runner.run_single(tmp_path / "nonexistent.mkv")

        assert not result.success
        assert "not found" in result.result.error_message.lower()
        assert result.error_classification == ErrorClassification.PERMANENT

    def test_lifecycle_called_on_completion(self, tmp_path):
        """Lifecycle methods are called correctly on success."""
        conn = MagicMock()
        policy = MagicMock()
        policy.phase_names = ["test"]
        config = WorkflowRunnerConfig(dry_run=True, policy_name="test")
        lifecycle = MagicMock()
        lifecycle.on_job_start.return_value = "job-123"

        # Create a real file
        test_file = tmp_path / "test.mkv"
        test_file.touch()

        # Mock the processor
        with patch("vpo.jobs.runner.WorkflowProcessor") as mock_proc_cls:
            mock_processor = MagicMock()
            mock_result = MagicMock(success=True, phase_results=[])
            mock_processor.process_file.return_value = mock_result
            mock_proc_cls.return_value = mock_processor

            runner = WorkflowRunner.for_cli(conn, policy, config, lifecycle)
            result = runner.run_single(test_file)

        lifecycle.on_job_start.assert_called_once()
        lifecycle.on_job_complete.assert_called_once()
        lifecycle.on_job_fail.assert_not_called()
        assert result.success

    def test_lifecycle_called_on_failure(self, tmp_path):
        """Lifecycle.on_job_fail called when exception occurs."""
        conn = MagicMock()
        policy = MagicMock()
        policy.phase_names = ["test"]
        config = WorkflowRunnerConfig(dry_run=False, policy_name="test")
        lifecycle = MagicMock()
        lifecycle.on_job_start.return_value = "job-123"

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("vpo.jobs.runner.WorkflowProcessor") as mock_proc_cls:
            mock_processor = MagicMock()
            mock_processor.process_file.side_effect = RuntimeError("Boom")
            mock_proc_cls.return_value = mock_processor

            runner = WorkflowRunner.for_cli(conn, policy, config, lifecycle)
            result = runner.run_single(test_file)

        lifecycle.on_job_fail.assert_called_once_with("job-123", "Boom")
        assert not result.success
        assert result.error_classification is not None

    def test_error_classification_set_on_exception(self, tmp_path):
        """Error classification is set when exception occurs."""
        conn = MagicMock()
        policy = MagicMock()
        policy.phase_names = ["test"]
        config = WorkflowRunnerConfig(dry_run=False, policy_name="test")

        test_file = tmp_path / "test.mkv"
        test_file.touch()

        with patch("vpo.jobs.runner.WorkflowProcessor") as mock_proc_cls:
            mock_processor = MagicMock()
            mock_processor.process_file.side_effect = sqlite3.OperationalError(
                "database is locked"
            )
            mock_proc_cls.return_value = mock_processor

            runner = WorkflowRunner.for_cli(conn, policy, config, NullJobLifecycle())
            result = runner.run_single(test_file)

        assert not result.success
        assert result.error_classification == ErrorClassification.TRANSIENT
