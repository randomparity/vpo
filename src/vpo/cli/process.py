"""CLI command for processing media files through the unified workflow.

This command processes files through user-defined phases in order.
"""

import json
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click

from vpo.cli.exit_codes import ExitCode
from vpo.cli.output import error_exit
from vpo.cli.profile_loader import load_profile_or_exit
from vpo.config.loader import get_config
from vpo.db.connection import get_connection
from vpo.db.queries import get_file_by_path
from vpo.jobs.tracking import (
    complete_process_job,
    create_process_job,
    fail_process_job,
)
from vpo.logging import worker_context
from vpo.policy.loader import PolicyValidationError, load_policy
from vpo.policy.types import (
    FileProcessingResult,
    OnErrorMode,
    PolicySchema,
)
from vpo.workflow import WorkflowProcessor

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
            completed, total, active = self.completed, self.total, self.active
        # I/O outside lock to avoid blocking workers if stderr is slow
        self._update_display(completed, total, active)

    def complete_file(self) -> None:
        """Mark a file as completed processing."""
        with self._lock:
            self.active -= 1
            self.completed += 1
            completed, total, active = self.completed, self.total, self.active
        # I/O outside lock to avoid blocking workers if stderr is slow
        self._update_display(completed, total, active)

    def _update_display(self, completed: int, total: int, active: int) -> None:
        """Update progress display on stderr.

        Args:
            completed: Number of completed files.
            total: Total number of files.
            active: Number of currently active workers.
        """
        if self.enabled:
            msg = f"\rProcessing: {completed}/{total} [{active} active]"
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
            if path.suffix.casefold() in video_extensions:
                files.append(path)
        elif path.is_dir():
            if recursive:
                for ext in video_extensions:
                    files.extend(path.rglob(f"*{ext}"))
            else:
                for ext in video_extensions:
                    files.extend(path.glob(f"*{ext}"))

    return sorted(set(files))


# =============================================================================
# Result Formatting
# =============================================================================


def _format_result_human(result, file_path: Path, verbose: bool = False) -> str:
    """Format processing result for human-readable output.

    Args:
        result: FileProcessingResult from workflow processor.
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
    if result.stats_id:
        lines.append(f"Stats ID: {result.stats_id}")
    return "\n".join(lines)


def _format_result_json(result, file_path: Path) -> dict:
    """Format processing result for JSON output.

    Args:
        result: FileProcessingResult from workflow processor.
        file_path: Path to the processed file.

    Returns:
        Dictionary for JSON serialization.
    """
    return {
        "file": str(file_path),
        "success": result.success,
        "stats_id": result.stats_id,
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


def _process_single_file(
    file_path: Path,
    db_path: Path,
    policy: PolicySchema,
    dry_run: bool,
    verbose: bool,
    policy_name: str,
    selected_phases: list[str] | None,
    progress: ProgressTracker,
    stop_event: threading.Event,
    worker_id: str,
    file_id: str,
    batch_id: str | None,
) -> tuple[Path, FileProcessingResult | None, bool]:
    """Process a single file (worker function).

    Each worker creates its own database connection for thread safety.

    Args:
        file_path: Path to the video file.
        db_path: Path to the database file.
        policy: Policy schema.
        dry_run: Whether to preview changes without modifying.
        verbose: Whether to emit verbose logging.
        policy_name: Name of the policy for audit.
        selected_phases: Optional phases to execute.
        progress: Progress tracker for display.
        stop_event: Event signaling batch should stop.
        worker_id: Worker identifier for logging (e.g., "01").
        file_id: File identifier for logging (e.g., "F001").
        batch_id: UUID grouping CLI batch operations (None if dry-run).

    Returns:
        Tuple of (file_path, result, success).
    """
    if stop_event.is_set():
        return file_path, None, False

    progress.start_file()
    job = None
    try:
        # Set worker context for logging - all logs within this context
        # will include [W{worker_id}:{file_id}] tag
        with worker_context(worker_id, file_id, file_path):
            # Log file mapping line so full path can be found by file_id
            logger.info("=== FILE %s: %s", file_id, file_path)

            # Each worker gets its own connection for thread safety
            with get_connection(db_path) as conn:
                # Create job record (skip for dry-run)
                db_file_id: int | None = None
                job_id: str | None = None
                if not dry_run:
                    # Get file_id from database if file exists there
                    file_record = get_file_by_path(conn, str(file_path))
                    if file_record:
                        db_file_id = file_record.id

                    job = create_process_job(
                        conn,
                        db_file_id,
                        str(file_path),
                        policy_name,
                        origin="cli",
                        batch_id=batch_id,
                    )
                    job_id = job.id
                    conn.commit()

                processor = WorkflowProcessor(
                    conn=conn,
                    policy=policy,
                    dry_run=dry_run,
                    verbose=verbose,
                    policy_name=policy_name,
                    selected_phases=selected_phases,
                    job_id=job_id,
                )
                result = processor.process_file(file_path)

                # Complete job record (skip for dry-run)
                if not dry_run and job:
                    complete_process_job(
                        conn,
                        job.id,
                        success=result.success,
                        phases_completed=result.phases_completed,
                        total_changes=result.total_changes,
                        error_message=result.error_message,
                        stats_id=result.stats_id,
                    )

                return file_path, result, result.success
    except Exception as e:
        logger.exception("Error processing %s: %s", file_path, e)

        # Fail job record if it was created
        if job:
            try:
                with get_connection(db_path) as conn:
                    fail_process_job(conn, job.id, str(e))
            except Exception as job_err:
                logger.warning("Failed to update job record: %s", job_err)

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

    # Auto-enable verbose for dry-run (seeing changes is the whole point)
    if dry_run and not json_output:
        verbose = True

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
    stopped_early = False
    batch_start_time = time.time()

    # Validate phase names before processing
    selected_phases = None
    if phases_str:
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
    from vpo.db.connection import get_default_db_path

    db_path = get_default_db_path()
    progress = ProgressTracker(
        total=len(file_paths),
        enabled=not json_output and not verbose,  # Disable if JSON or verbose
    )
    stop_event = threading.Event()

    # Generate batch_id for CLI batch operations (skip for dry-run)
    batch_id = str(uuid.uuid4()) if not dry_run else None

    try:
        # Parallel processing with ThreadPoolExecutor
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
                    _process_single_file,
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
                    batch_id,
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
                                formatted = _format_result_human(
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
                                # Cancel pending futures and shutdown executor
                                for f in futures:
                                    f.cancel()
                                executor.shutdown(wait=True, cancel_futures=True)
                                break
                    except Exception as e:
                        logger.exception("Unexpected error for %s: %s", file_path, e)
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
                    click.echo(
                        "\nInterrupted - waiting for active workers to complete..."
                    )
                # Cancel pending futures (not yet running)
                for f in futures:
                    f.cancel()
                # Wait for running tasks to complete gracefully
                # cancel_futures=True cancels pending immediately, but running
                # tasks continue until their current operation completes.
                # The stop_event signals workers to exit quickly.
                executor.shutdown(wait=True, cancel_futures=True)

        # Finish progress display
        progress.finish()

    except sqlite3.Error as e:
        error_exit(f"Database error: {e}", ExitCode.GENERAL_ERROR, json_output)

    # Calculate batch duration
    batch_duration = time.time() - batch_start_time

    # Output summary
    if json_output:
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
