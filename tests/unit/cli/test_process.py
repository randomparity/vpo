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
from vpo.policy.types import FileProcessingResult, GlobalConfig, OnErrorMode


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
    """Tests for _process_single_file with multiple policies."""

    def _make_run_result(self, success: bool = True, result=None):
        """Create a mock RunResult."""
        mock = MagicMock()
        mock.success = success
        mock.result = result or _make_result(success=success)
        return mock

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.WorkflowRunner")
    @patch("vpo.cli.process.worker_context")
    def test_sequential_execution_order(
        self, mock_ctx, mock_runner_cls, mock_conn, make_policy
    ):
        """Policies execute in order on the file."""
        policy_a = make_policy()
        policy_b = make_policy()
        path_a = Path("/tmp/a.yaml")
        path_b = Path("/tmp/b.yaml")

        call_order = []

        def make_runner(conn, policy, config, lifecycle):
            mock_runner = MagicMock()
            call_order.append(config.policy_name)
            mock_runner.run_single.return_value = self._make_run_result()
            return mock_runner

        mock_runner_cls.for_cli.side_effect = make_runner
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        from vpo.jobs import WorkflowRunnerConfig

        configs = [
            WorkflowRunnerConfig(dry_run=True, policy_name="policy_a"),
            WorkflowRunnerConfig(dry_run=True, policy_name="policy_b"),
        ]

        progress = MagicMock()
        stop_event = threading.Event()

        _, results, success = _process_single_file(
            Path("/tmp/test.mkv"),
            0,
            Path("/tmp/db.sqlite"),
            [(path_a, policy_a), (path_b, policy_b)],
            configs,
            progress,
            stop_event,
            "01",
            "F001",
            None,
        )

        assert success is True
        assert len(results) == 2
        assert results[0][0] == "policy_a"
        assert results[1][0] == "policy_b"
        assert call_order == ["policy_a", "policy_b"]

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.WorkflowRunner")
    @patch("vpo.cli.process.worker_context")
    def test_on_error_skip_stops_remaining_policies(
        self, mock_ctx, mock_runner_cls, mock_conn, make_policy
    ):
        """on_error=skip stops remaining policies for this file."""
        policy_a = make_policy(config=GlobalConfig(on_error=OnErrorMode.SKIP))
        policy_b = make_policy()

        mock_runner = MagicMock()
        mock_runner.run_single.return_value = self._make_run_result(
            success=False,
            result=_make_result(success=False, error_message="fail"),
        )
        mock_runner_cls.for_cli.return_value = mock_runner
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        from vpo.jobs import WorkflowRunnerConfig

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

        assert success is False
        # Only the first policy ran (skip stops remaining)
        assert len(results) == 1
        assert results[0][0] == "policy_a"

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.WorkflowRunner")
    @patch("vpo.cli.process.worker_context")
    def test_on_error_continue_runs_next_policy(
        self, mock_ctx, mock_runner_cls, mock_conn, make_policy
    ):
        """on_error=continue proceeds to next policy after failure."""
        policy_a = make_policy(config=GlobalConfig(on_error=OnErrorMode.CONTINUE))
        policy_b = make_policy()

        call_count = [0]

        def make_runner(conn, policy, config, lifecycle):
            mock_r = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_r.run_single.return_value = self._make_run_result(
                    success=False,
                    result=_make_result(success=False, error_message="fail"),
                )
            else:
                mock_r.run_single.return_value = self._make_run_result()
            return mock_r

        mock_runner_cls.for_cli.side_effect = make_runner
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        from vpo.jobs import WorkflowRunnerConfig

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

        assert success is False  # overall fails because policy_a failed
        assert len(results) == 2  # both ran
        assert not results[0][1].success
        assert results[1][1].success

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.WorkflowRunner")
    @patch("vpo.cli.process.worker_context")
    def test_on_error_fail_skips_remaining_policies(
        self, mock_ctx, mock_runner_cls, mock_conn, make_policy
    ):
        """on_error=fail skips remaining policies for this file.

        Batch-level stop_event is set by the outer result collection loop,
        not by _process_single_file. This preserves backward compatibility
        with single-policy behavior.
        """
        policy_a = make_policy(config=GlobalConfig(on_error=OnErrorMode.FAIL))
        policy_b = make_policy()

        mock_runner = MagicMock()
        mock_runner.run_single.return_value = self._make_run_result(
            success=False,
            result=_make_result(success=False, error_message="fatal"),
        )
        mock_runner_cls.for_cli.return_value = mock_runner
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        from vpo.jobs import WorkflowRunnerConfig

        configs = [
            WorkflowRunnerConfig(dry_run=True, policy_name="policy_a"),
            WorkflowRunnerConfig(dry_run=True, policy_name="policy_b"),
        ]

        stop_event = threading.Event()
        _, results, success = _process_single_file(
            Path("/tmp/test.mkv"),
            0,
            Path("/tmp/db.sqlite"),
            [(Path("/tmp/a.yaml"), policy_a), (Path("/tmp/b.yaml"), policy_b)],
            configs,
            MagicMock(),
            stop_event,
            "01",
            "F001",
            None,
        )

        assert success is False
        assert not stop_event.is_set()  # batch stop handled by outer loop
        assert len(results) == 1  # only first policy ran

    @patch("vpo.cli.process.get_connection")
    @patch("vpo.cli.process.WorkflowRunner")
    @patch("vpo.cli.process.worker_context")
    def test_single_policy_works_unchanged(
        self, mock_ctx, mock_runner_cls, mock_conn, make_policy
    ):
        """Single policy in a list works the same as before."""
        policy = make_policy()
        mock_runner = MagicMock()
        mock_runner.run_single.return_value = self._make_run_result()
        mock_runner_cls.for_cli.return_value = mock_runner
        mock_conn.return_value.__enter__ = MagicMock()
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        from vpo.jobs import WorkflowRunnerConfig

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
