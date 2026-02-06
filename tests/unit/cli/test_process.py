"""Tests for process command worker utilities.

Renamed as part of CLI reorganization. The `policy run` command
was promoted to top-level `process` command.
"""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.cli.process import (
    _format_multi_policy_result_human,
    _process_single_file,
    get_max_workers,
    resolve_worker_count,
)
from vpo.jobs import WorkflowRunnerConfig
from vpo.policy.types import FileProcessingResult
from vpo.workflow.multi_policy import MultiPolicyResult


class TestGetMaxWorkers:
    """Tests for get_max_workers function."""

    def test_returns_half_cpu_cores(self) -> None:
        """Should return half of CPU cores."""
        with patch("os.cpu_count", return_value=8):
            assert get_max_workers() == 4

    def test_minimum_is_one(self) -> None:
        """Minimum return value is 1."""
        with patch("os.cpu_count", return_value=1):
            assert get_max_workers() == 1

    def test_handles_cpu_count_none(self) -> None:
        """Should handle cpu_count returning None."""
        with patch("os.cpu_count", return_value=None):
            # Defaults to 2 CPUs, returns 1
            assert get_max_workers() == 1

    def test_odd_cpu_count_floors(self) -> None:
        """Odd CPU count should floor divide."""
        with patch("os.cpu_count", return_value=7):
            assert get_max_workers() == 3


class TestResolveWorkerCount:
    """Tests for resolve_worker_count function."""

    def test_uses_requested_when_provided(self) -> None:
        """Should use requested value when provided."""
        with patch("os.cpu_count", return_value=16):
            result = resolve_worker_count(requested=4, config_default=2)
            assert result == 4

    def test_uses_config_default_when_not_requested(self) -> None:
        """Should use config default when requested is None."""
        with patch("os.cpu_count", return_value=16):
            result = resolve_worker_count(requested=None, config_default=3)
            assert result == 3

    def test_caps_at_max_workers(self) -> None:
        """Should cap at half CPU cores."""
        with patch("os.cpu_count", return_value=4):  # max = 2
            result = resolve_worker_count(requested=10, config_default=2)
            assert result == 2

    def test_logs_warning_when_capped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Should log warning when capping worker count."""
        with patch("os.cpu_count", return_value=4):  # max = 2
            result = resolve_worker_count(requested=10, config_default=2)
            assert result == 2
            assert "exceeds cap of 2" in caplog.text

    def test_minimum_is_one(self) -> None:
        """Result is at least 1."""
        with patch("os.cpu_count", return_value=16):
            result = resolve_worker_count(requested=0, config_default=2)
            assert result == 1

    def test_negative_becomes_one(self) -> None:
        """Negative values become 1."""
        with patch("os.cpu_count", return_value=16):
            result = resolve_worker_count(requested=-5, config_default=2)
            assert result == 1


# Note: Progress tracking is now handled by StderrProgressReporter in vpo.jobs.progress
# Tests for progress reporters are in tests/unit/jobs/test_progress.py


# =============================================================================
# Multiple Policy Support Tests
# =============================================================================


def _make_result(
    file_path: Path | None = None, success: bool = True, error_message: str = ""
) -> FileProcessingResult:
    """Create a minimal FileProcessingResult for testing."""
    return FileProcessingResult(
        file_path=file_path or Path("/tmp/test.mkv"),
        success=success,
        phase_results=(),
        total_duration_seconds=1.0,
        total_changes=0,
        phases_completed=1 if success else 0,
        phases_failed=0 if success else 1,
        phases_skipped=0,
        error_message=error_message,
    )


class TestProcessSingleFileMultiPolicy:
    """Tests for _process_single_file delegation to run_policies_for_file.

    Detailed multi-policy orchestration tests (on_error modes, stop_event,
    transaction cleanup) live in tests/unit/workflow/test_multi_policy.py.
    These tests verify that the CLI wrapper correctly delegates and
    translates the result.
    """

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.run_policies_for_file")
    @patch("vpo.cli.process.worker_context")
    def test_delegates_to_run_policies_for_file(
        self, mock_ctx, mock_run, mock_conn, make_policy
    ):
        """_process_single_file delegates to run_policies_for_file."""
        result_a = _make_result()
        result_b = _make_result()
        mock_run.return_value = MultiPolicyResult(
            policy_results=(("policy_a", result_a), ("policy_b", result_b)),
            overall_success=True,
        )
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        policy_a = make_policy()
        policy_b = make_policy()
        configs = [
            WorkflowRunnerConfig(dry_run=True, policy_name="policy_a"),
            WorkflowRunnerConfig(dry_run=True, policy_name="policy_b"),
        ]

        _, results, success = _process_single_file(
            Path("/tmp/test.mkv"),
            0,
            Path("/tmp/db.sqlite"),
            [(Path("/tmp/a.yaml"), policy_a), (Path("/tmp/b.yaml"), policy_b)],
            configs,
            MagicMock(),
            threading.Event(),
            "01",
            "F001",
            None,
        )

        assert success is True
        assert len(results) == 2
        assert results[0][0] == "policy_a"
        assert results[1][0] == "policy_b"
        mock_run.assert_called_once()

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.run_policies_for_file")
    @patch("vpo.cli.process.worker_context")
    def test_failure_result_propagated(
        self, mock_ctx, mock_run, mock_conn, make_policy
    ):
        """Failure result from run_policies_for_file is propagated."""
        fail_result = _make_result(success=False, error_message="fail")
        mock_run.return_value = MultiPolicyResult(
            policy_results=(("policy_a", fail_result),),
            overall_success=False,
        )
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        policy = make_policy()
        configs = [WorkflowRunnerConfig(dry_run=True, policy_name="policy_a")]

        _, results, success = _process_single_file(
            Path("/tmp/test.mkv"),
            0,
            Path("/tmp/db.sqlite"),
            [(Path("/tmp/a.yaml"), policy)],
            configs,
            MagicMock(),
            threading.Event(),
            "01",
            "F001",
            None,
        )

        assert success is False
        assert len(results) == 1
        assert not results[0][1].success

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.run_policies_for_file")
    @patch("vpo.cli.process.worker_context")
    def test_single_policy_works(self, mock_ctx, mock_run, mock_conn, make_policy):
        """Single policy in a list works fine."""
        ok_result = _make_result()
        mock_run.return_value = MultiPolicyResult(
            policy_results=(("test", ok_result),),
            overall_success=True,
        )
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        policy = make_policy()
        configs = [WorkflowRunnerConfig(dry_run=True, policy_name="test")]

        _, results, success = _process_single_file(
            Path("/tmp/test.mkv"),
            0,
            Path("/tmp/db.sqlite"),
            [(Path("/tmp/test.yaml"), policy)],
            configs,
            MagicMock(),
            threading.Event(),
            "01",
            "F001",
            None,
        )

        assert success is True
        assert len(results) == 1
        assert results[0][0] == "test"

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.run_policies_for_file")
    @patch("vpo.cli.process.worker_context")
    def test_stop_event_returns_none_results(
        self, mock_ctx, mock_run, mock_conn, make_policy
    ):
        """When stop_event is set before entry, returns None results."""
        policy = make_policy()
        configs = [WorkflowRunnerConfig(dry_run=True, policy_name="test")]

        stop = threading.Event()
        stop.set()

        path, results, success = _process_single_file(
            Path("/tmp/test.mkv"),
            0,
            Path("/tmp/db.sqlite"),
            [(Path("/tmp/test.yaml"), policy)],
            configs,
            MagicMock(),
            stop,
            "01",
            "F001",
            None,
        )

        assert path == Path("/tmp/test.mkv")
        assert results is None
        assert success is False
        mock_run.assert_not_called()

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.run_policies_for_file")
    @patch("vpo.cli.process.worker_context")
    def test_exception_returns_error_result(
        self, mock_ctx, mock_run, mock_conn, make_policy
    ):
        """Unhandled exception in processing returns error result tuple."""
        mock_run.side_effect = RuntimeError("disk full")
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        policy = make_policy()
        configs = [WorkflowRunnerConfig(dry_run=True, policy_name="test")]

        path, results, success = _process_single_file(
            Path("/tmp/test.mkv"),
            0,
            Path("/tmp/db.sqlite"),
            [(Path("/tmp/test.yaml"), policy)],
            configs,
            MagicMock(),
            threading.Event(),
            "01",
            "F001",
            None,
        )

        assert path == Path("/tmp/test.mkv")
        assert success is False
        assert results is not None
        assert len(results) == 1
        _, result = results[0]
        assert result.success is False
        assert "disk full" in result.error_message


class TestFormatMultiPolicyResult:
    """Tests for _format_multi_policy_result_human."""

    def test_single_policy_delegates(self):
        """Single policy delegates to _format_result_human."""
        result = _make_result()
        output = _format_multi_policy_result_human(
            [("test_policy", result)],
            Path("/tmp/test.mkv"),
            verbose=False,
        )
        assert "Status: Success" in output

    def test_multiple_policies_shows_per_policy(self):
        """Multiple policies show per-policy sections."""
        result_a = _make_result()
        result_b = _make_result(success=False, error_message="bad codec")
        output = _format_multi_policy_result_human(
            [("normalize", result_a), ("transcode", result_b)],
            Path("/tmp/test.mkv"),
            verbose=False,
        )
        assert "Policy: normalize" in output
        assert "Policy: transcode" in output
        assert "File: /tmp/test.mkv" in output


class TestProcessCommandMultiPolicyCLI:
    """Tests for multi-policy CLI option handling."""

    def test_phases_with_multiple_policies_rejected(self, temp_dir: Path):
        """--phases with multiple --policy flags is rejected."""
        from click.testing import CliRunner

        from vpo.cli import main

        # Create two minimal policy files
        for name in ("a.yaml", "b.yaml"):
            (temp_dir / name).write_text(
                "schema_version: 12\nphases:\n  - name: default\n"
            )
        # Create a dummy video file
        video = temp_dir / "test.mkv"
        video.touch()

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "process",
                "-p",
                str(temp_dir / "a.yaml"),
                "-p",
                str(temp_dir / "b.yaml"),
                "--phases",
                "default",
                str(video),
            ],
        )
        assert result.exit_code != 0
        assert "--phases cannot be used with multiple policies" in result.output
