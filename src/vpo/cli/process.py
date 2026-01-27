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
from vpo.cli.log_formatter import format_phase_details
from vpo.cli.output import error_exit
from vpo.cli.profile_loader import load_profile_or_exit
from vpo.config.loader import get_config
from vpo.db.connection import get_connection
from vpo.db.queries import get_file_by_path
from vpo.jobs import (
    CLIJobLifecycle,
    NullJobLifecycle,
    StderrProgressReporter,
    WorkflowRunner,
    WorkflowRunnerConfig,
)
from vpo.logging import worker_context
from vpo.policy.loader import PolicyValidationError, load_policy
from vpo.policy.types import (
    FileProcessingResult,
    OnErrorMode,
    PhaseOutcome,
    PolicySchema,
)

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
# File Discovery
# =============================================================================


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

    # Add phase details (always show in verbose mode)
    if verbose:
        lines.append("")
        lines.append("Phase details:")
        for pr in result.phase_results:
            # Status indicator with outcome awareness
            if pr.outcome == PhaseOutcome.SKIPPED:
                status = "SKIP"
            elif pr.success:
                status = "OK"
            else:
                status = "FAIL"

            # Phase summary line
            change_word = "change" if pr.changes_made == 1 else "changes"
            lines.append(
                f"  [{status}] {pr.phase_name}: "
                f"{pr.changes_made} {change_word}, {pr.duration_seconds:.2f}s"
            )

            # Operations list
            if pr.operations_executed:
                ops_str = ", ".join(pr.operations_executed)
                lines.append(f"         Operations: {ops_str}")

            # Enhanced detail lines (container change, tracks removed, etc.)
            detail_lines = format_phase_details(pr)
            for detail in detail_lines:
                lines.append(f"         {detail}")

            # Skip reason for skipped phases
            if pr.skip_reason:
                lines.append(f"         Skip reason: {pr.skip_reason.message}")

            # Error message for failed phases
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
        "phase_results": [_format_phase_result_json(pr) for pr in result.phase_results],
    }


def _format_phase_result_json(pr) -> dict:
    """Format a PhaseResult for JSON output including enhanced detail fields.

    Args:
        pr: PhaseResult to format.

    Returns:
        Dictionary for JSON serialization.
    """
    result = {
        "phase": pr.phase_name,
        "success": pr.success,
        "outcome": pr.outcome.value if pr.outcome else None,
        "operations_executed": list(pr.operations_executed),
        "changes_made": pr.changes_made,
        "duration_seconds": round(pr.duration_seconds, 2),
        "message": pr.message,
        "error": pr.error,
    }

    # Add container change details
    if pr.container_change:
        result["container_change"] = {
            "source_format": pr.container_change.source_format,
            "target_format": pr.container_change.target_format,
            "warnings": list(pr.container_change.warnings),
        }

    # Add track dispositions (removed tracks)
    if pr.track_dispositions:
        removed_tracks = [
            {
                "track_index": td.track_index,
                "track_type": td.track_type,
                "codec": td.codec,
                "language": td.language,
                "channels": td.channels,
                "reason": td.reason,
            }
            for td in pr.track_dispositions
            if td.action == "REMOVE"
        ]
        if removed_tracks:
            result["tracks_removed"] = removed_tracks

    # Add track order change
    if pr.track_order_change:
        before, after = pr.track_order_change
        result["track_order_change"] = {
            "before": list(before),
            "after": list(after),
        }

    # Add audio synthesis info
    if pr.audio_synthesis_created:
        result["audio_synthesis_created"] = list(pr.audio_synthesis_created)

    # Add transcode results
    if pr.size_before is not None and pr.size_after is not None:
        result["transcode"] = {
            "size_before": pr.size_before,
            "size_after": pr.size_after,
            "encoder_type": pr.encoder_type,
            "encoding_fps": pr.encoding_fps,
        }
    elif pr.transcode_skip_reason:
        result["transcode_skip_reason"] = pr.transcode_skip_reason

    # Add skip reason for skipped phases
    if pr.skip_reason:
        result["skip_reason"] = {
            "type": pr.skip_reason.reason_type.value,
            "message": pr.skip_reason.message,
        }

    return result


# =============================================================================
# Parallel Processing Worker
# =============================================================================


# Lock for synchronizing verbose output across worker threads
_output_lock = threading.Lock()


def _process_single_file(
    file_path: Path,
    file_index: int,
    db_path: Path,
    policy: PolicySchema,
    runner_config: WorkflowRunnerConfig,
    progress: StderrProgressReporter,
    stop_event: threading.Event,
    worker_id: str,
    file_id: str,
    batch_id: str | None,
    save_logs: bool = False,
) -> tuple[Path, FileProcessingResult | None, bool]:
    """Process a single file using WorkflowRunner.

    Each worker creates its own database connection for thread safety.

    Args:
        file_path: Path to the video file.
        file_index: Zero-based index for progress tracking.
        db_path: Path to the database file.
        policy: Policy schema.
        runner_config: WorkflowRunner configuration.
        progress: Progress reporter for display.
        stop_event: Event signaling batch should stop.
        worker_id: Worker identifier for logging (e.g., "01").
        file_id: File identifier for logging (e.g., "F001").
        batch_id: UUID grouping CLI batch operations (None if dry-run).
        save_logs: If True, save detailed logs to ~/.vpo/logs/.

    Returns:
        Tuple of (file_path, result, success).
    """
    if stop_event.is_set():
        return file_path, None, False

    progress.on_item_start(file_index)
    try:
        # Set worker context for logging - all logs within this context
        # will include [W{worker_id}:{file_id}] tag
        with worker_context(worker_id, file_id, file_path):
            # Log file mapping line so full path can be found by file_id
            logger.info("=== FILE %s: %s", file_id, file_path)

            # Each worker gets its own connection for thread safety
            with get_connection(db_path) as conn:
                # Get database file_id if file exists in DB
                db_file_id: int | None = None
                if not runner_config.dry_run:
                    file_record = get_file_by_path(conn, str(file_path))
                    if file_record:
                        db_file_id = file_record.id

                # Create lifecycle for job management (or no-op for dry-run)
                if runner_config.dry_run:
                    lifecycle: CLIJobLifecycle | NullJobLifecycle = NullJobLifecycle()
                else:
                    lifecycle = CLIJobLifecycle(
                        conn,
                        batch_id=batch_id,
                        policy_name=runner_config.policy_name,
                        save_logs=save_logs,
                    )

                try:
                    # Create and run workflow
                    # job_log is created in on_job_start() if save_logs=True;
                    # run_single() gets it from lifecycle dynamically
                    runner = WorkflowRunner.for_cli(
                        conn, policy, runner_config, lifecycle
                    )
                    run_result = runner.run_single(file_path, file_id=db_file_id)

                    progress.on_item_complete(file_index, success=run_result.success)
                    return file_path, run_result.result, run_result.success
                finally:
                    # Ensure job log is closed
                    if isinstance(lifecycle, CLIJobLifecycle):
                        lifecycle.close_job_log()

    except Exception as e:
        logger.exception("Worker error processing %s: %s", file_path, e)
        progress.on_item_complete(file_index, success=False)

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
@click.option(
    "--save-logs/--no-save-logs",
    default=True,
    help="Save detailed job logs to ~/.vpo/logs/ (default: enabled).",
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
    save_logs: bool,
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
    progress = StderrProgressReporter(
        enabled=not json_output and not verbose,  # Disable if JSON or verbose
    )
    progress.on_start(len(file_paths))
    stop_event = threading.Event()

    # Generate batch_id for CLI batch operations (skip for dry-run)
    batch_id = str(uuid.uuid4()) if not dry_run else None

    # Create shared runner configuration
    runner_config = WorkflowRunnerConfig(
        dry_run=dry_run,
        verbose=verbose,
        selected_phases=selected_phases,
        policy_name=str(policy_path),
    )

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

                # file_index is 0-based for progress tracking
                future = executor.submit(
                    _process_single_file,
                    file_path,
                    file_idx - 1,  # 0-based index for progress
                    db_path,
                    policy,
                    runner_config,
                    progress,
                    stop_event,
                    worker_id,
                    file_id,
                    batch_id,
                    save_logs,
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
        progress.on_complete()

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
