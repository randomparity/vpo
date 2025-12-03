"""CLI command for processing media files through the unified workflow.

This command replaces the separate apply and transcode commands with a
unified workflow that runs phases in order: analyze → apply → transcode.

For V11 policies, the workflow runs user-defined phases in order.
"""

import json
import logging
import os
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import click

from video_policy_orchestrator.cli.exit_codes import ExitCode
from video_policy_orchestrator.cli.output import error_exit
from video_policy_orchestrator.cli.plan_formatter import (
    OutputStyle,
    format_plan_human,
    format_plan_json,
)
from video_policy_orchestrator.cli.profile_loader import load_profile_or_exit
from video_policy_orchestrator.config.loader import get_config
from video_policy_orchestrator.db.connection import get_connection
from video_policy_orchestrator.logging import worker_context
from video_policy_orchestrator.policy.loader import PolicyValidationError, load_policy
from video_policy_orchestrator.policy.models import (
    FileProcessingResult,
    OnErrorMode,
    ProcessingPhase,
    V11PolicySchema,
    WorkflowConfig,
)
from video_policy_orchestrator.workflow import V11WorkflowProcessor, WorkflowProcessor

logger = logging.getLogger(__name__)


# =============================================================================
# Worker Count Utilities
# =============================================================================


def get_max_workers() -> int:
    """Calculate maximum worker count (half CPU cores, minimum 1).

    Returns:
        Maximum number of workers based on available CPU cores.
    """
    cpu_count = os.cpu_count() or 2  # Default to 2 if detection fails
    return max(1, cpu_count // 2)


def resolve_worker_count(requested: int | None, config_default: int) -> int:
    """Resolve effective worker count with capping.

    Args:
        requested: Worker count from CLI (None if not specified).
        config_default: Default worker count from configuration.

    Returns:
        Effective worker count (capped at max_workers).
    """
    max_workers = get_max_workers()
    effective = requested if requested is not None else config_default

    if effective > max_workers:
        logger.warning(
            f"Requested {effective} workers exceeds cap of {max_workers} "
            f"(half of {os.cpu_count()} cores). Using {max_workers}."
        )
        return max_workers

    return max(1, effective)


def _validate_workers(
    ctx: click.Context, param: click.Parameter, value: int | None
) -> int | None:
    """Validate --workers option value.

    Args:
        ctx: Click context.
        param: Click parameter.
        value: Worker count from CLI.

    Returns:
        Validated value (unchanged if valid).

    Raises:
        click.BadParameter: If value is less than 1.
    """
    if value is not None and value < 1:
        raise click.BadParameter("must be at least 1")
    return value


# =============================================================================
# Progress Tracking
# =============================================================================


class ProgressTracker:
    """Thread-safe progress tracking for parallel file processing.

    Displays aggregate progress on stderr using in-place updates.
    """

    def __init__(self, total: int, enabled: bool = True) -> None:
        """Initialize progress tracker.

        Args:
            total: Total number of files to process.
            enabled: If False, suppresses output (for JSON mode).
        """
        self.total = total
        self.completed = 0
        self.active = 0
        self.enabled = enabled
        self._lock = threading.Lock()

    def start_file(self) -> None:
        """Mark a file as starting processing."""
        with self._lock:
            self.active += 1
            self._update()

    def complete_file(self) -> None:
        """Mark a file as completed processing."""
        with self._lock:
            self.active -= 1
            self.completed += 1
            self._update()

    def _update(self) -> None:
        """Update progress display on stderr."""
        if self.enabled:
            msg = f"\rProcessing: {self.completed}/{self.total} [{self.active} active]"
            sys.stderr.write(msg)
            sys.stderr.flush()

    def finish(self) -> None:
        """Complete progress display with newline."""
        if self.enabled:
            sys.stderr.write("\n")
            sys.stderr.flush()


def _discover_files(paths: list[Path], recursive: bool) -> list[Path]:
    """Discover video files from the given paths.

    Args:
        paths: List of file or directory paths.
        recursive: If True, search directories recursively.

    Returns:
        List of video file paths.
    """
    video_extensions = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm"}
    files = []

    for path in paths:
        path = path.expanduser().resolve()
        if path.is_file():
            if path.suffix.lower() in video_extensions:
                files.append(path)
        elif path.is_dir():
            if recursive:
                for ext in video_extensions:
                    files.extend(path.rglob(f"*{ext}"))
            else:
                for ext in video_extensions:
                    files.extend(path.glob(f"*{ext}"))

    return sorted(set(files))


def _parse_phases(phases_str: str | None) -> tuple[ProcessingPhase, ...] | None:
    """Parse comma-separated phases string.

    Args:
        phases_str: Comma-separated phase names (e.g., "analyze,apply,transcode").

    Returns:
        Tuple of ProcessingPhase enums, or None if not specified.
    """
    if not phases_str:
        return None

    phases = []
    for name in phases_str.split(","):
        name = name.strip().lower()
        try:
            phases.append(ProcessingPhase(name))
        except ValueError:
            valid = ", ".join(p.value for p in ProcessingPhase)
            raise click.BadParameter(
                f"Invalid phase '{name}'. Valid phases: {valid}"
            ) from None

    return tuple(phases)


def _format_result_human(result, file_path: Path, verbose: bool = False) -> str:
    """Format processing result for human-readable output.

    Args:
        result: FileProcessingResult from workflow processor.
        file_path: Path to the processed file.
        verbose: If True, show full BEFORE/AFTER tables for plans.

    Returns:
        Formatted string for terminal output.
    """
    lines = []

    # Always show file path in verbose mode
    if verbose:
        lines.append(f"File: {file_path}")

    if result.success:
        completed = [p.value for p in result.phases_completed]
        lines.append("Status: Success")
        lines.append(f"Phases: {', '.join(completed)}")
    else:
        lines.append("Status: Failed")
        lines.append(f"Error: {result.error_message}")
        if result.phases_completed:
            completed = [p.value for p in result.phases_completed]
            lines.append(f"Completed: {', '.join(completed)}")
        if result.phases_failed:
            failed = [p.value for p in result.phases_failed]
            lines.append(f"Failed: {', '.join(failed)}")

    # Add plan details if available (dry-run mode)
    for pr in result.phase_results:
        if pr.plan is not None:
            lines.append("")
            style = OutputStyle.VERBOSE if verbose else OutputStyle.NORMAL
            lines.append(format_plan_human(pr.plan, style=style))

    lines.append(f"Duration: {result.duration_seconds:.1f}s")
    return "\n".join(lines)


def _format_result_json(result, file_path: Path) -> dict:
    """Format processing result for JSON output."""
    output = {
        "file": str(file_path),
        "success": result.success,
        "phases_completed": [p.value for p in result.phases_completed],
        "phases_failed": [p.value for p in result.phases_failed],
        "phases_skipped": [p.value for p in result.phases_skipped],
        "error_message": result.error_message,
        "duration_seconds": round(result.duration_seconds, 2),
        "phase_results": [
            {
                "phase": pr.phase.value,
                "success": pr.success,
                "message": pr.message,
                "changes_made": pr.changes_made,
                "duration_seconds": round(pr.duration_seconds, 2),
                "plan": format_plan_json(pr.plan) if pr.plan else None,
            }
            for pr in result.phase_results
        ],
    }

    # Also include plan at top level for convenience (first non-null plan)
    for pr in result.phase_results:
        if pr.plan is not None:
            output["plan"] = format_plan_json(pr.plan)
            break

    return output


# =============================================================================
# V11 Result Formatting (User-Defined Phases)
# =============================================================================


def _format_v11_result_human(result, file_path: Path, verbose: bool = False) -> str:
    """Format V11 processing result for human-readable output.

    Args:
        result: FileProcessingResult from V11 workflow processor.
        file_path: Path to the processed file.
        verbose: If True, show detailed output.

    Returns:
        Formatted string for terminal output.
    """
    lines = []

    # Always show file path in verbose mode
    if verbose:
        lines.append(f"File: {file_path}")

    if result.success:
        lines.append("Status: Success")
        lines.append(f"Phases completed: {result.phases_completed}")
        lines.append(f"Total changes: {result.total_changes}")
    else:
        lines.append("Status: Failed")
        lines.append(f"Error: {result.error_message}")
        if result.failed_phase:
            lines.append(f"Failed phase: {result.failed_phase}")
        lines.append(f"Phases completed: {result.phases_completed}")
        lines.append(f"Phases failed: {result.phases_failed}")
        lines.append(f"Phases skipped: {result.phases_skipped}")

    # Add phase details
    if verbose:
        lines.append("")
        lines.append("Phase details:")
        for pr in result.phase_results:
            status = "OK" if pr.success else "FAILED"
            lines.append(
                f"  [{status}] {pr.phase_name}: "
                f"{pr.changes_made} changes, {pr.duration_seconds:.2f}s"
            )
            if pr.operations_executed:
                ops_str = ", ".join(pr.operations_executed)
                lines.append(f"         Operations: {ops_str}")
            if pr.error:
                lines.append(f"         Error: {pr.error}")

    lines.append(f"Duration: {result.total_duration_seconds:.1f}s")
    return "\n".join(lines)


def _format_v11_result_json(result, file_path: Path) -> dict:
    """Format V11 processing result for JSON output.

    Args:
        result: FileProcessingResult from V11 workflow processor.
        file_path: Path to the processed file.

    Returns:
        Dictionary for JSON serialization.
    """
    return {
        "file": str(file_path),
        "success": result.success,
        "phases_completed": result.phases_completed,
        "phases_failed": result.phases_failed,
        "phases_skipped": result.phases_skipped,
        "total_changes": result.total_changes,
        "failed_phase": result.failed_phase,
        "error_message": result.error_message,
        "duration_seconds": round(result.total_duration_seconds, 2),
        "phase_results": [
            {
                "phase": pr.phase_name,
                "success": pr.success,
                "operations_executed": list(pr.operations_executed),
                "changes_made": pr.changes_made,
                "duration_seconds": round(pr.duration_seconds, 2),
                "message": pr.message,
                "error": pr.error,
            }
            for pr in result.phase_results
        ],
    }


# =============================================================================
# Parallel Processing Worker
# =============================================================================


# Lock for synchronizing verbose output across worker threads
_output_lock = threading.Lock()


def _process_single_file_v11(
    file_path: Path,
    db_path: Path,
    policy: V11PolicySchema,
    dry_run: bool,
    verbose: bool,
    policy_name: str,
    selected_phases: list[str] | None,
    progress: ProgressTracker,
    stop_event: threading.Event,
    worker_id: str,
    file_id: str,
) -> tuple[Path, FileProcessingResult | None, bool]:
    """Process a single file with V11 policy (worker function).

    Each worker creates its own database connection for thread safety.

    Args:
        file_path: Path to the video file.
        db_path: Path to the database file.
        policy: V11 policy schema.
        dry_run: Whether to preview changes without modifying.
        verbose: Whether to emit verbose logging.
        policy_name: Name of the policy for audit.
        selected_phases: Optional phases to execute.
        progress: Progress tracker for display.
        stop_event: Event signaling batch should stop.
        worker_id: Worker identifier for logging (e.g., "01").
        file_id: File identifier for logging (e.g., "F001").

    Returns:
        Tuple of (file_path, result, success).
    """
    if stop_event.is_set():
        return file_path, None, False

    progress.start_file()
    try:
        # Set worker context for logging - all logs within this context
        # will include [W{worker_id}:{file_id}] tag
        with worker_context(worker_id, file_id, file_path):
            # Log file mapping line so full path can be found by file_id
            logger.info("=== FILE %s: %s", file_id, file_path)

            # Each worker gets its own connection for thread safety
            with get_connection(db_path) as conn:
                processor = V11WorkflowProcessor(
                    conn=conn,
                    policy=policy,
                    dry_run=dry_run,
                    verbose=verbose,
                    policy_name=policy_name,
                    selected_phases=selected_phases,
                )
                result = processor.process_file(file_path)
                return file_path, result, result.success
    except Exception as e:
        logger.exception("Error processing %s: %s", file_path, e)
        # Create a minimal failure result
        result = FileProcessingResult(
            file_path=file_path,
            success=False,
            phase_results=(),
            total_duration_seconds=0.0,
            total_changes=0,
            phases_completed=0,
            phases_failed=0,
            phases_skipped=0,
            error_message=str(e),
        )
        return file_path, result, False
    finally:
        progress.complete_file()


@click.command("process")
@click.option(
    "--policy",
    "-p",
    "policy_path",
    required=False,
    type=click.Path(exists=False, path_type=Path),
    help="Path to YAML policy file (or use --profile for default)",
)
@click.option(
    "--profile",
    default=None,
    help="Use named configuration profile from ~/.vpo/profiles/.",
)
@click.option(
    "--recursive",
    "-R",
    is_flag=True,
    default=False,
    help="Process directories recursively",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Preview changes without modifying files",
)
@click.option(
    "--phases",
    "phases_str",
    default=None,
    help="Override phases to run (comma-separated: analyze,apply,transcode)",
)
@click.option(
    "--on-error",
    "on_error",
    type=click.Choice(["skip", "continue", "fail"]),
    default=None,
    help="Error handling mode (default: from policy)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show detailed output",
)
@click.option(
    "--json",
    "-j",
    "json_output",
    is_flag=True,
    default=False,
    help="Output in JSON format",
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=None,
    callback=_validate_workers,
    help=(
        "Number of parallel workers for batch processing "
        "(default: from config or 2, max: half CPU cores). "
        "Each worker needs ~2.5x file size disk space for transcoding."
    ),
)
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
def process_command(
    policy_path: Path | None,
    profile: str | None,
    recursive: bool,
    dry_run: bool,
    phases_str: str | None,
    on_error: str | None,
    verbose: bool,
    json_output: bool,
    workers: int | None,
    paths: tuple[Path, ...],
) -> None:
    """Process media files through the unified workflow.

    PATHS can be files or directories. Use -R for recursive directory processing.

    The workflow runs phases in order: analyze → apply → transcode.
    Each phase is optional and controlled by the policy's workflow section
    or the --phases option.

    Examples:

        vpo process --policy policy.yaml movie.mkv

        vpo process -p policy.yaml -R /media/movies/

        vpo process -p policy.yaml --phases analyze,apply movie.mkv

        vpo process -p policy.yaml --dry-run movie.mkv
    """
    # Load profile if specified
    loaded_profile = None
    if profile:
        loaded_profile = load_profile_or_exit(profile, json_output, verbose)

    # Determine policy path
    if policy_path is None:
        if loaded_profile and loaded_profile.default_policy:
            policy_path = loaded_profile.default_policy
        else:
            error_exit(
                "No policy specified. Use --policy or --profile with default_policy.",
                ExitCode.POLICY_VALIDATION_ERROR,
                json_output,
            )

    # Resolve and load policy
    policy_path = policy_path.expanduser().resolve()
    try:
        policy = load_policy(policy_path)
    except FileNotFoundError:
        error_exit(
            f"Policy file not found: {policy_path}",
            ExitCode.POLICY_VALIDATION_ERROR,
            json_output,
        )
    except PolicyValidationError as e:
        error_exit(str(e), ExitCode.POLICY_VALIDATION_ERROR, json_output)

    # Parse phase override
    phase_override = _parse_phases(phases_str)

    # Discover files
    file_paths = _discover_files(list(paths), recursive)
    if not file_paths:
        error_exit(
            "No video files found in the specified paths.",
            ExitCode.TARGET_NOT_FOUND,
            json_output,
        )

    # Resolve worker count from config and CLI
    config = get_config()
    effective_workers = resolve_worker_count(workers, config.processing.workers)

    if verbose and not json_output:
        click.echo(f"Policy: {policy_path} (v{policy.schema_version})")
        click.echo(f"Files: {len(file_paths)}")
        click.echo(f"Mode: {'dry-run' if dry_run else 'live'}")
        click.echo(f"Workers: {effective_workers}")
        click.echo("")

    # Process files
    results = []
    success_count = 0
    fail_count = 0
    is_v11 = isinstance(policy, V11PolicySchema)
    stopped_early = False
    batch_start_time = time.time()

    # Validate phase names for V11 policies before processing
    selected_phases = None
    if is_v11 and phases_str:
        selected_phases = [p.strip() for p in phases_str.split(",") if p.strip()]
        # Validate phase names against policy's phases list
        valid_names = set(policy.phase_names)
        invalid_names = [name for name in selected_phases if name not in valid_names]
        if invalid_names:
            error_msg = (
                f"Invalid phase name(s): {', '.join(invalid_names)}. "
                f"Valid phases: {', '.join(sorted(valid_names))}"
            )
            error_exit(error_msg, ExitCode.INVALID_ARGUMENTS, json_output)

    # Get database path for workers (each worker creates its own connection)
    from video_policy_orchestrator.db.connection import get_default_db_path

    db_path = get_default_db_path()
    progress = ProgressTracker(
        total=len(file_paths),
        enabled=not json_output and not verbose,  # Disable if JSON or verbose
    )
    stop_event = threading.Event()

    try:
        if is_v11:
            # V11 policy - parallel processing with ThreadPoolExecutor
            # Determine on_error mode from policy config
            policy_on_error = policy.config.on_error

            with ThreadPoolExecutor(max_workers=effective_workers) as executor:
                # Submit all files as futures
                futures = {}

                # Calculate file ID width based on batch size for consistent formatting
                # e.g., 50 files -> F01-F50, 5000 files -> F0001-F5000
                file_id_width = len(str(len(file_paths)))

                for file_idx, file_path in enumerate(file_paths, start=1):
                    if stop_event.is_set():
                        break

                    # Generate worker and file IDs for logging context.
                    # Worker ID is a logical slot (1 to effective_workers), not
                    # the actual thread ID. ThreadPoolExecutor assigns files to
                    # threads as they become available, so W01 may run on any thread.
                    worker_id = f"{((file_idx - 1) % effective_workers) + 1:02d}"
                    file_id = f"F{file_idx:0{file_id_width}d}"

                    future = executor.submit(
                        _process_single_file_v11,
                        file_path,
                        db_path,
                        policy,
                        dry_run,
                        verbose,
                        str(policy_path),
                        selected_phases,
                        progress,
                        stop_event,
                        worker_id,
                        file_id,
                    )
                    futures[future] = file_path

                # Process results as they complete
                try:
                    for future in as_completed(futures):
                        file_path = futures[future]
                        try:
                            _, result, success = future.result()
                            if result is not None:
                                results.append(result)
                                if success:
                                    success_count += 1
                                else:
                                    fail_count += 1

                                # Output result if verbose (use lock for thread safety)
                                if not json_output and verbose:
                                    formatted = _format_v11_result_human(
                                        result, file_path, verbose
                                    )
                                    with _output_lock:
                                        click.echo(formatted)
                                        click.echo("")
                                elif not json_output and not progress.enabled:
                                    # Not verbose, not progress mode - show status
                                    status = "OK" if success else "FAILED"
                                    with _output_lock:
                                        click.echo(f"[{status}] {file_path.name}")

                                # Handle on_error=fail mode
                                if not success and policy_on_error == OnErrorMode.FAIL:
                                    stop_event.set()
                                    stopped_early = True
                                    if not json_output:
                                        click.echo(
                                            "Stopping batch due to error "
                                            f"(on_error='fail'): {result.error_message}"
                                        )
                                    # Cancel pending futures
                                    for f in futures:
                                        f.cancel()
                                    break
                        except Exception as e:
                            logger.exception(
                                "Unexpected error for %s: %s", file_path, e
                            )
                            fail_count += 1
                            # Create minimal result for tracking
                            error_result = FileProcessingResult(
                                file_path=file_path,
                                success=False,
                                phase_results=(),
                                total_duration_seconds=0.0,
                                total_changes=0,
                                phases_completed=0,
                                phases_failed=0,
                                phases_skipped=0,
                                error_message=str(e),
                            )
                            results.append(error_result)

                except KeyboardInterrupt:
                    # User pressed CTRL-C, cancel remaining work
                    stop_event.set()
                    stopped_early = True
                    if not json_output:
                        click.echo("\nInterrupted - cancelling remaining files...")
                    # Cancel pending futures
                    for f in futures:
                        f.cancel()
                    # Shutdown executor without waiting for running tasks
                    executor.shutdown(wait=False, cancel_futures=True)

            # Finish progress display
            progress.finish()

        else:
            # Flat policy - sequential workflow processor with worker context
            with get_connection() as conn:
                # Create effective workflow config with overrides
                if phase_override or on_error:
                    base_config = policy.workflow or WorkflowConfig(
                        phases=(ProcessingPhase.APPLY,),
                    )
                    effective_phases = phase_override or base_config.phases
                    effective_on_error = on_error or base_config.on_error
                    effective_config = WorkflowConfig(
                        phases=effective_phases,
                        auto_process=base_config.auto_process,
                        on_error=effective_on_error,
                    )
                    # Create modified policy with new workflow
                    # Note: PolicySchema is frozen, so we need to create a new one
                    policy = replace(policy, workflow=effective_config)

                # Create processor
                processor = WorkflowProcessor(
                    conn=conn,
                    policy=policy,
                    dry_run=dry_run,
                    verbose=verbose,
                    policy_name=str(policy_path),
                )

                # Calculate file ID width for consistent formatting
                file_id_width = len(str(len(file_paths)))

                for file_idx, file_path in enumerate(file_paths, start=1):
                    if verbose and not json_output:
                        click.echo(f"Processing: {file_path}")

                    # Use worker context for log correlation (single worker "01")
                    file_id = f"F{file_idx:0{file_id_width}d}"
                    with worker_context("01", file_id, file_path):
                        logger.info("=== FILE %s: %s", file_id, file_path)
                        result = processor.process_file(file_path)

                    results.append(result)

                    if result.success:
                        success_count += 1
                    else:
                        fail_count += 1

                    if not json_output:
                        # In dry-run mode, always show plan details
                        # In non-dry-run mode, only show details if verbose
                        if dry_run or verbose:
                            formatted = _format_result_human(result, file_path, verbose)
                            click.echo(formatted)
                            click.echo("")
                        else:
                            status = "OK" if result.success else "FAILED"
                            click.echo(f"[{status}] {file_path.name}")

                    # Check if batch processing should stop (on_error='fail')
                    if result.batch_should_stop:
                        stopped_early = True
                        if not json_output:
                            click.echo(
                                f"Stopping batch due to error (on_error='fail'): "
                                f"{result.error_message}"
                            )
                        break

    except sqlite3.Error as e:
        error_exit(f"Database error: {e}", ExitCode.GENERAL_ERROR, json_output)

    # Calculate batch duration
    batch_duration = time.time() - batch_start_time

    # Output summary
    if json_output:
        if is_v11:
            policy_info = {
                "path": str(policy_path),
                "version": policy.schema_version,
                "phases": list(policy.phase_names),
            }
            # Add filtered phases if selective execution was used
            if selected_phases:
                policy_info["phases_filtered"] = selected_phases
            output = {
                "policy": policy_info,
                "dry_run": dry_run,
                "workers": effective_workers,
                "summary": {
                    "total": len(results),
                    "success": success_count,
                    "failed": fail_count,
                    "duration_seconds": round(batch_duration, 2),
                    "stopped_early": stopped_early,
                },
                "results": [_format_v11_result_json(r, r.file_path) for r in results],
            }
        else:
            output = {
                "policy": {
                    "path": str(policy_path),
                    "version": policy.schema_version,
                },
                "dry_run": dry_run,
                "workers": effective_workers,
                "summary": {
                    "total": len(results),
                    "success": success_count,
                    "failed": fail_count,
                    "duration_seconds": round(batch_duration, 2),
                    "stopped_early": stopped_early,
                },
                "results": [_format_result_json(r, r.file_path) for r in results],
            }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo("")
        n = len(results)
        duration_str = f" in {batch_duration:.1f}s" if batch_duration > 0 else ""
        msg = f"Processed {n} file(s): {success_count} ok, {fail_count} failed"
        click.echo(f"{msg}{duration_str}")
        if stopped_early:
            click.echo("(Batch stopped early due to error)")

    # Exit code
    if fail_count > 0:
        sys.exit(ExitCode.OPERATION_FAILED)
    sys.exit(ExitCode.SUCCESS)
