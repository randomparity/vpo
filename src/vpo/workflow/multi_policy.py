"""Multi-policy orchestration for single-file processing.

Extracts per-file multi-policy logic (sequential execution, on_error handling,
result accumulation) so both CLI and daemon can reuse it.
"""

import logging
import sqlite3
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from vpo.jobs.runner import (
    JobLifecycle,
    WorkflowRunner,
    WorkflowRunnerConfig,
)
from vpo.policy.types import FileProcessingResult, OnErrorMode, PolicySchema
from vpo.workflow.processor import NOT_IN_DB_MESSAGE

logger = logging.getLogger(__name__)

LifecycleFactory = Callable[[str], JobLifecycle]
"""Factory that takes a policy name and returns a JobLifecycle."""


@dataclass(frozen=True)
class PolicyEntry:
    """A policy paired with its runner configuration."""

    policy: PolicySchema
    config: WorkflowRunnerConfig


@dataclass(frozen=True)
class MultiPolicyResult:
    """Result of running one or more policies against a single file."""

    policy_results: tuple[tuple[str, FileProcessingResult], ...]
    overall_success: bool


_ON_ERROR_SEVERITY: dict[OnErrorMode, int] = {
    OnErrorMode.CONTINUE: 0,
    OnErrorMode.SKIP: 1,
    OnErrorMode.FAIL: 2,
}


def strictest_error_mode(policies: Iterable[PolicySchema]) -> OnErrorMode:
    """Select the strictest on_error mode across multiple policies.

    Priority (strictest to most lenient):
    1. FAIL  -- abort entire batch on first error
    2. SKIP  -- skip remaining files on error
    3. CONTINUE -- process all files regardless of errors
    """
    return max(
        (p.config.on_error for p in policies),
        key=lambda m: _ON_ERROR_SEVERITY[m],
    )


def run_policies_for_file(
    conn: sqlite3.Connection,
    file_path: Path,
    entries: Sequence[PolicyEntry],
    lifecycle_factory: LifecycleFactory,
    *,
    stop_event: threading.Event | None = None,
    file_id: int | None = None,
) -> MultiPolicyResult:
    """Run one or more policies sequentially against a single file.

    When multiple policies are provided, they run in order. If a policy
    fails, the failing policy's on_error setting determines whether to
    continue to the next policy (continue), or skip remaining policies
    for this file (skip/fail).

    Args:
        conn: Database connection (caller owns lifetime).
        file_path: Path to the video file.
        entries: Ordered list of PolicyEntry (policy + config).
        lifecycle_factory: Creates a JobLifecycle for each policy name.
        stop_event: Optional event signaling batch should stop.
        file_id: Database ID of the file (if known).

    Returns:
        MultiPolicyResult with accumulated (policy_name, result) pairs.
    """
    policy_results: list[tuple[str, FileProcessingResult]] = []
    overall_success = True

    for entry in entries:
        if stop_event is not None and stop_event.is_set():
            break

        policy_name = entry.config.policy_name

        if len(entries) > 1:
            logger.info("--- Policy %s", policy_name)

        lifecycle = lifecycle_factory(policy_name)

        try:
            runner = WorkflowRunner.for_cli(conn, entry.policy, entry.config, lifecycle)
            run_result = runner.run_single(file_path, file_id=file_id)

            policy_results.append((policy_name, run_result.result))

            if not run_result.success:
                overall_success = False
                if len(entries) > 1:
                    on_error = entry.policy.config.on_error
                    if on_error != OnErrorMode.CONTINUE:
                        logger.warning(
                            "Policy '%s' failed for %s, skipping "
                            "remaining policies (on_error=%s)",
                            policy_name,
                            file_path.name,
                            on_error.value,
                        )
                        break
                    logger.warning(
                        "Policy '%s' failed for %s, continuing "
                        "to next policy (on_error=continue)",
                        policy_name,
                        file_path.name,
                    )

            # Early exit for not-in-db (no point running more policies)
            if (
                run_result.result
                and run_result.result.error_message == NOT_IN_DB_MESSAGE
            ):
                break

        finally:
            # Clean up connection state before next policy
            if conn.in_transaction:
                logger.warning(
                    "Connection left in transaction after policy '%s', rolling back",
                    policy_name,
                )
                conn.rollback()
            # Ensure job log is closed if lifecycle supports it
            close_fn = getattr(lifecycle, "close_job_log", None)
            if close_fn is not None:
                close_fn()

    # Guard: if stop_event fired before any policy ran,
    # create a placeholder so callers never see an empty list.
    if not policy_results:
        last_name = entries[-1].config.policy_name if entries else "unknown"
        placeholder = FileProcessingResult(
            file_path=file_path,
            success=False,
            phase_results=(),
            total_duration_seconds=0.0,
            total_changes=0,
            phases_completed=0,
            phases_failed=0,
            phases_skipped=0,
            error_message="Batch stopped before processing",
        )
        policy_results = [(last_name, placeholder)]
        overall_success = False

    return MultiPolicyResult(
        policy_results=tuple(policy_results),
        overall_success=overall_success,
    )
