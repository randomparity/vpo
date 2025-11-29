"""CLI command for processing media files through the unified workflow.

This command replaces the separate apply and transcode commands with a
unified workflow that runs phases in order: analyze → apply → transcode.
"""

import json
import logging
import sqlite3
import sys
from pathlib import Path

import click

from video_policy_orchestrator.cli.exit_codes import ExitCode
from video_policy_orchestrator.cli.output import error_exit
from video_policy_orchestrator.cli.profile_loader import load_profile_or_exit
from video_policy_orchestrator.db.connection import get_connection
from video_policy_orchestrator.policy.loader import PolicyValidationError, load_policy
from video_policy_orchestrator.policy.models import ProcessingPhase

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


def _format_result_human(result, file_path: Path) -> str:
    """Format processing result for human-readable output."""
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

    lines.append(f"Duration: {result.duration_seconds:.1f}s")
    return "\n".join(lines)


def _format_result_json(result, file_path: Path) -> dict:
    """Format processing result for JSON output."""
    return {
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

    try:
        with get_connection() as conn:
            from video_policy_orchestrator.policy.models import WorkflowConfig
            from video_policy_orchestrator.workflow import WorkflowProcessor

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
                from dataclasses import replace

                policy = replace(policy, workflow=effective_config)

            # Create processor
            processor = WorkflowProcessor(
                conn=conn,
                policy=policy,
                dry_run=dry_run,
                verbose=verbose,
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
                    if verbose:
                        click.echo(_format_result_human(result, file_path))
                        click.echo("")
                    else:
                        status = "✓" if result.success else "✗"
                        click.echo(f"{status} {file_path.name}")

    except sqlite3.Error as e:
        error_exit(f"Database error: {e}", ExitCode.GENERAL_ERROR, json_output)

    # Output summary
    if json_output:
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
