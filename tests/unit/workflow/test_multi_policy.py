"""Tests for multi-policy orchestration (workflow.multi_policy)."""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vpo.jobs.runner import WorkflowRunnerConfig
from vpo.policy.types import FileProcessingResult, GlobalConfig, OnErrorMode
from vpo.workflow.multi_policy import (
    MultiPolicyResult,
    PolicyEntry,
    run_policies_for_file,
    strictest_error_mode,
)
from vpo.workflow.processor import NOT_IN_DB_MESSAGE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    file_path: Path | None = None,
    success: bool = True,
    error_message: str = "",
) -> FileProcessingResult:
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


def _make_run_result(success: bool = True, result=None):
    mock = MagicMock()
    mock.success = success
    mock.result = result or _make_result(success=success)
    return mock


def _entry(make_policy, *, on_error=OnErrorMode.SKIP, policy_name="policy"):
    policy = make_policy(config=GlobalConfig(on_error=on_error))
    config = WorkflowRunnerConfig(dry_run=True, policy_name=policy_name)
    return PolicyEntry(policy=policy, config=config)


# ---------------------------------------------------------------------------
# strictest_error_mode
# ---------------------------------------------------------------------------


class TestStrictestErrorMode:
    def test_single_continue(self, make_policy):
        p = make_policy(config=GlobalConfig(on_error=OnErrorMode.CONTINUE))
        assert strictest_error_mode([p]) == OnErrorMode.CONTINUE

    def test_single_fail(self, make_policy):
        p = make_policy(config=GlobalConfig(on_error=OnErrorMode.FAIL))
        assert strictest_error_mode([p]) == OnErrorMode.FAIL

    def test_mixed_selects_strictest(self, make_policy):
        p1 = make_policy(config=GlobalConfig(on_error=OnErrorMode.CONTINUE))
        p2 = make_policy(config=GlobalConfig(on_error=OnErrorMode.SKIP))
        p3 = make_policy(config=GlobalConfig(on_error=OnErrorMode.FAIL))
        assert strictest_error_mode([p1, p2, p3]) == OnErrorMode.FAIL

    def test_all_same_returns_that_mode(self, make_policy):
        p1 = make_policy(config=GlobalConfig(on_error=OnErrorMode.SKIP))
        p2 = make_policy(config=GlobalConfig(on_error=OnErrorMode.SKIP))
        assert strictest_error_mode([p1, p2]) == OnErrorMode.SKIP

    def test_skip_vs_continue(self, make_policy):
        p1 = make_policy(config=GlobalConfig(on_error=OnErrorMode.CONTINUE))
        p2 = make_policy(config=GlobalConfig(on_error=OnErrorMode.SKIP))
        assert strictest_error_mode([p1, p2]) == OnErrorMode.SKIP

    def test_empty_policies_raises(self):
        """Empty policies iterable raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            strictest_error_mode([])


# ---------------------------------------------------------------------------
# run_policies_for_file
# ---------------------------------------------------------------------------


class TestRunPoliciesForFile:
    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_sequential_execution_order(self, mock_runner_cls, make_policy):
        """Policies execute in order."""
        entry_a = _entry(make_policy, policy_name="policy_a")
        entry_b = _entry(make_policy, policy_name="policy_b")

        call_order = []

        def make_runner(conn, policy, config, lifecycle):
            call_order.append(config.policy_name)
            mock_r = MagicMock()
            mock_r.run_single.return_value = _make_run_result()
            return mock_r

        mock_runner_cls.for_cli.side_effect = make_runner

        conn = MagicMock()
        conn.in_transaction = False
        factory = MagicMock(side_effect=lambda pn: MagicMock())

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry_a, entry_b],
            lifecycle_factory=factory,
        )

        assert result.overall_success is True
        assert len(result.policy_results) == 2
        assert result.policy_results[0][0] == "policy_a"
        assert result.policy_results[1][0] == "policy_b"
        assert call_order == ["policy_a", "policy_b"]

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_single_policy_works(self, mock_runner_cls, make_policy):
        """Single policy in the list works fine."""
        entry = _entry(make_policy, policy_name="only")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result()
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry],
            lifecycle_factory=lambda pn: MagicMock(),
        )

        assert result.overall_success is True
        assert len(result.policy_results) == 1
        assert result.policy_results[0][0] == "only"

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_on_error_skip_stops_remaining(self, mock_runner_cls, make_policy):
        """on_error=skip stops remaining policies for this file."""
        entry_a = _entry(make_policy, on_error=OnErrorMode.SKIP, policy_name="a")
        entry_b = _entry(make_policy, policy_name="b")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result(
            success=False,
            result=_make_result(success=False, error_message="fail"),
        )
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry_a, entry_b],
            lifecycle_factory=lambda pn: MagicMock(),
        )

        assert result.overall_success is False
        assert len(result.policy_results) == 1
        assert result.policy_results[0][0] == "a"

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_on_error_continue_runs_next(self, mock_runner_cls, make_policy):
        """on_error=continue proceeds to next policy after failure."""
        entry_a = _entry(make_policy, on_error=OnErrorMode.CONTINUE, policy_name="a")
        entry_b = _entry(make_policy, policy_name="b")

        call_count = [0]

        def make_runner(conn, policy, config, lifecycle):
            call_count[0] += 1
            mock_r = MagicMock()
            if call_count[0] == 1:
                mock_r.run_single.return_value = _make_run_result(
                    success=False,
                    result=_make_result(success=False, error_message="fail"),
                )
            else:
                mock_r.run_single.return_value = _make_run_result()
            return mock_r

        mock_runner_cls.for_cli.side_effect = make_runner

        conn = MagicMock()
        conn.in_transaction = False

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry_a, entry_b],
            lifecycle_factory=lambda pn: MagicMock(),
        )

        assert result.overall_success is False  # overall fails
        assert len(result.policy_results) == 2  # both ran
        assert not result.policy_results[0][1].success
        assert result.policy_results[1][1].success

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_on_error_fail_stops_remaining(self, mock_runner_cls, make_policy):
        """on_error=fail skips remaining policies (same as skip at per-file level)."""
        entry_a = _entry(make_policy, on_error=OnErrorMode.FAIL, policy_name="a")
        entry_b = _entry(make_policy, policy_name="b")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result(
            success=False,
            result=_make_result(success=False, error_message="fatal"),
        )
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry_a, entry_b],
            lifecycle_factory=lambda pn: MagicMock(),
        )

        assert result.overall_success is False
        assert len(result.policy_results) == 1

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_not_in_db_breaks_loop(self, mock_runner_cls, make_policy):
        """NOT_IN_DB_MESSAGE error breaks the policy loop."""
        entry_a = _entry(make_policy, policy_name="a")
        entry_b = _entry(make_policy, policy_name="b")

        not_in_db_result = _make_result(success=False, error_message=NOT_IN_DB_MESSAGE)
        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result(
            success=False, result=not_in_db_result
        )
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry_a, entry_b],
            lifecycle_factory=lambda pn: MagicMock(),
        )

        # Only one policy ran due to not-in-db early exit
        assert len(result.policy_results) == 1
        assert result.policy_results[0][1].error_message == NOT_IN_DB_MESSAGE

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_stop_event_prevents_execution(self, mock_runner_cls, make_policy):
        """If stop_event is set before start, no policies run."""
        entry = _entry(make_policy, policy_name="a")

        conn = MagicMock()
        conn.in_transaction = False
        stop = threading.Event()
        stop.set()

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry],
            lifecycle_factory=lambda pn: MagicMock(),
            stop_event=stop,
        )

        assert result.overall_success is False
        assert len(result.policy_results) == 1
        assert (
            result.policy_results[0][1].error_message
            == "Batch stopped before processing"
        )
        mock_runner_cls.for_cli.assert_not_called()

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_stop_event_mid_loop(self, mock_runner_cls, make_policy):
        """stop_event set after first policy prevents second from running."""
        entry_a = _entry(make_policy, policy_name="a")
        entry_b = _entry(make_policy, policy_name="b")

        stop = threading.Event()

        def make_runner(conn, policy, config, lifecycle):
            mock_r = MagicMock()
            mock_r.run_single.return_value = _make_run_result()
            # Set stop after first policy runs
            stop.set()
            return mock_r

        mock_runner_cls.for_cli.side_effect = make_runner

        conn = MagicMock()
        conn.in_transaction = False

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry_a, entry_b],
            lifecycle_factory=lambda pn: MagicMock(),
            stop_event=stop,
        )

        # Only first policy ran
        assert len(result.policy_results) == 1
        assert result.policy_results[0][0] == "a"

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_transaction_cleanup_on_error(self, mock_runner_cls, make_policy):
        """Connection in_transaction triggers rollback in finally block."""
        entry = _entry(make_policy, policy_name="a")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result()
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = True

        run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry],
            lifecycle_factory=lambda pn: MagicMock(),
        )

        conn.rollback.assert_called_once()

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_lifecycle_close_job_log_called(self, mock_runner_cls, make_policy):
        """Lifecycle close_job_log is called in finally block."""
        entry = _entry(make_policy, policy_name="a")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result()
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        lifecycle = MagicMock()

        run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry],
            lifecycle_factory=lambda pn: lifecycle,
        )

        lifecycle.close_job_log.assert_called_once()

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_lifecycle_factory_called_per_policy(self, mock_runner_cls, make_policy):
        """Lifecycle factory is called once per policy with the policy name."""
        entry_a = _entry(make_policy, policy_name="a")
        entry_b = _entry(make_policy, policy_name="b")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result()
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        factory = MagicMock(return_value=MagicMock())

        run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry_a, entry_b],
            lifecycle_factory=factory,
        )

        assert factory.call_count == 2
        factory.assert_any_call("a")
        factory.assert_any_call("b")

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_file_id_passed_to_runner(self, mock_runner_cls, make_policy):
        """file_id kwarg is passed through to runner.run_single."""
        entry = _entry(make_policy, policy_name="a")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result()
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry],
            lifecycle_factory=lambda pn: MagicMock(),
            file_id=42,
        )

        mock_r.run_single.assert_called_once_with(Path("/tmp/test.mkv"), file_id=42)

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_result_is_frozen_dataclass(self, mock_runner_cls, make_policy):
        """MultiPolicyResult is a frozen dataclass."""
        entry = _entry(make_policy, policy_name="a")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result()
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry],
            lifecycle_factory=lambda pn: MagicMock(),
        )

        assert isinstance(result, MultiPolicyResult)
        assert isinstance(result.policy_results, tuple)

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_empty_entries_returns_placeholder(self, mock_runner_cls):
        """Empty entries list returns a placeholder result."""
        conn = MagicMock()
        conn.in_transaction = False

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[],
            lifecycle_factory=lambda pn: MagicMock(),
        )

        assert result.overall_success is False
        assert len(result.policy_results) == 1
        assert result.policy_results[0][0] == "unknown"
        assert (
            result.policy_results[0][1].error_message
            == "Batch stopped before processing"
        )
        mock_runner_cls.for_cli.assert_not_called()

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_runner_exception_triggers_finally_cleanup(
        self, mock_runner_cls, make_policy
    ):
        """When runner.run_single raises, finally block still runs."""
        entry = _entry(make_policy, policy_name="a")

        mock_r = MagicMock()
        mock_r.run_single.side_effect = RuntimeError("ffmpeg crashed")
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = True

        lifecycle = MagicMock()

        with pytest.raises(RuntimeError, match="ffmpeg crashed"):
            run_policies_for_file(
                conn=conn,
                file_path=Path("/tmp/test.mkv"),
                entries=[entry],
                lifecycle_factory=lambda pn: lifecycle,
            )

        # Finally block should have run despite exception
        conn.rollback.assert_called_once()
        lifecycle.close_job_log.assert_called_once()

    @patch("vpo.workflow.multi_policy.WorkflowRunner")
    def test_lifecycle_without_close_job_log_no_error(
        self, mock_runner_cls, make_policy
    ):
        """Lifecycle without close_job_log attribute does not error."""
        entry = _entry(make_policy, policy_name="a")

        mock_r = MagicMock()
        mock_r.run_single.return_value = _make_run_result()
        mock_runner_cls.for_cli.return_value = mock_r

        conn = MagicMock()
        conn.in_transaction = False

        # Use a simple object without close_job_log
        lifecycle = object()

        result = run_policies_for_file(
            conn=conn,
            file_path=Path("/tmp/test.mkv"),
            entries=[entry],
            lifecycle_factory=lambda pn: lifecycle,
        )

        assert result.overall_success is True
