"""CLI command for processing media files through the unified workflow.

This command replaces the separate apply and transcode commands with a
unified workflow that runs phases in order: analyze → apply → transcode.

For V11 policies, the workflow runs user-defined phases in order.
"""

import json
import logging
import sqlite3
import sys
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
from video_policy_orchestrator.db.connection import get_connection
from video_policy_orchestrator.policy.loader import PolicyValidationError, load_policy
from video_policy_orchestrator.policy.models import (
    ProcessingPhase,
    V11PolicySchema,
    WorkflowConfig,
)
from video_policy_orchestrator.workflow import V11WorkflowProcessor, WorkflowProcessor

logger = logging.getLogger(__name__)


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
    lines = [f"File: {file_path}"]

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
    lines = [f"File: {file_path}"]

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

    if verbose and not json_output:
        click.echo(f"Policy: {policy_path} (v{policy.schema_version})")
        click.echo(f"Files: {len(file_paths)}")
        click.echo(f"Mode: {'dry-run' if dry_run else 'live'}")
        click.echo("")

    # Process files
    results = []
    success_count = 0
    fail_count = 0
    is_v11 = isinstance(policy, V11PolicySchema)

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

    try:
        with get_connection() as conn:
            if is_v11:
                # V11 policy with user-defined phases
                processor = V11WorkflowProcessor(
                    conn=conn,
                    policy=policy,
                    dry_run=dry_run,
                    verbose=verbose,
                    policy_name=str(policy_path),
                    selected_phases=selected_phases,
                )

                for file_path in file_paths:
                    if verbose and not json_output:
                        click.echo(f"Processing: {file_path}")

                    result = processor.process_file(file_path)
                    results.append(result)

                    if result.success:
                        success_count += 1
                    else:
                        fail_count += 1

                    if not json_output:
                        if dry_run or verbose:
                            formatted = _format_v11_result_human(
                                result, file_path, verbose
                            )
                            click.echo(formatted)
                            click.echo("")
                        else:
                            status = "OK" if result.success else "FAILED"
                            click.echo(f"[{status}] {file_path.name}")

                    # Check if batch should stop
                    if not result.success and policy.config.on_error.value == "fail":
                        if not json_output:
                            click.echo(
                                f"Stopping batch due to error (on_error='fail'): "
                                f"{result.error_message}"
                            )
                        break
            else:
                # V1-V10 policy - use existing workflow processor
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

                for file_path in file_paths:
                    if verbose and not json_output:
                        click.echo(f"Processing: {file_path}")

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
                        if not json_output:
                            click.echo(
                                f"Stopping batch due to error (on_error='fail'): "
                                f"{result.error_message}"
                            )
                        break

    except sqlite3.Error as e:
        error_exit(f"Database error: {e}", ExitCode.GENERAL_ERROR, json_output)

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
                "summary": {
                    "total": len(results),
                    "success": success_count,
                    "failed": fail_count,
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
                "summary": {
                    "total": len(results),
                    "success": success_count,
                    "failed": fail_count,
                },
                "results": [_format_result_json(r, r.file_path) for r in results],
            }
        click.echo(json.dumps(output, indent=2))
    else:
        click.echo("")
        n = len(results)
        click.echo(f"Processed {n} file(s): {success_count} ok, {fail_count} failed")

    # Exit code
    if fail_count > 0:
        sys.exit(ExitCode.OPERATION_FAILED)
    sys.exit(ExitCode.SUCCESS)
