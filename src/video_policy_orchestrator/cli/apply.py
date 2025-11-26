"""CLI command for applying policies to media files."""

import json
import logging
import sqlite3
import sys
from pathlib import Path

import click

from video_policy_orchestrator.db.connection import get_connection
from video_policy_orchestrator.db.models import (
    OperationStatus,
    TrackInfo,
    get_file_by_path,
    get_tracks_for_file,
)
from video_policy_orchestrator.db.operations import (
    create_operation,
    update_operation_status,
)
from video_policy_orchestrator.executor.backup import FileLockError, file_lock
from video_policy_orchestrator.executor.interface import check_tool_availability
from video_policy_orchestrator.policy.loader import PolicyValidationError, load_policy
from video_policy_orchestrator.policy.models import (
    ActionType,
    ContainerChange,
    TrackDisposition,
)

logger = logging.getLogger(__name__)

# Cached policy engine instance (module-level singleton)
_policy_engine_instance = None


def _get_policy_engine():
    """Get the PolicyEnginePlugin instance.

    Returns a cached instance of the built-in policy engine plugin for
    evaluation and execution. The instance is created once and reused
    across invocations for better performance.

    Returns:
        PolicyEnginePlugin instance.
    """
    global _policy_engine_instance
    if _policy_engine_instance is None:
        from video_policy_orchestrator.plugins.policy_engine import PolicyEnginePlugin

        _policy_engine_instance = PolicyEnginePlugin()
    return _policy_engine_instance


# Exit codes per contracts/cli-apply.md
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_POLICY_VALIDATION_ERROR = 2
EXIT_TARGET_NOT_FOUND = 3
EXIT_TOOL_NOT_AVAILABLE = 4
EXIT_OPERATION_FAILED = 5


def _tracks_from_records(
    track_records: list,
) -> list[TrackInfo]:
    """Convert TrackRecord list to TrackInfo list for policy evaluation.

    Args:
        track_records: List of TrackRecord objects from database.

    Returns:
        List of TrackInfo domain objects suitable for policy evaluation.
    """
    return [
        TrackInfo(
            index=r.track_index,
            track_type=r.track_type,
            codec=r.codec,
            language=r.language,
            title=r.title,
            is_default=r.is_default,
            is_forced=r.is_forced,
            channels=r.channels,
            channel_layout=r.channel_layout,
            width=r.width,
            height=r.height,
            frame_rate=r.frame_rate,
        )
        for r in track_records
    ]


def _format_track_dispositions(
    dispositions: tuple[TrackDisposition, ...],
) -> str:
    """Format track dispositions for display.

    Args:
        dispositions: Tuple of track dispositions.

    Returns:
        Formatted string showing each track with action and reason.
    """
    if not dispositions:
        return ""

    lines = []
    for disp in dispositions:
        # Build track description
        parts = [f"Track {disp.track_index}: {disp.track_type}"]

        if disp.codec:
            parts.append(f"({disp.codec})")

        if disp.language:
            parts.append(f"[{disp.language}]")

        if disp.title:
            parts.append(f'"{disp.title}"')

        if disp.channels:
            channel_desc = _channels_to_layout(disp.channels)
            parts.append(channel_desc)

        if disp.resolution:
            parts.append(disp.resolution)

        track_desc = " ".join(parts)

        # Format action with reason
        if disp.action == "KEEP":
            action_str = f"  KEEP   {track_desc}"
        else:
            action_str = f"  REMOVE {track_desc} - {disp.reason}"

        lines.append(action_str)

    return "\n".join(lines)


def _channels_to_layout(channels: int) -> str:
    """Convert channel count to layout description."""
    layouts = {
        1: "mono",
        2: "stereo",
        6: "5.1",
        8: "7.1",
    }
    return layouts.get(channels, f"{channels}ch")


def _format_container_change(change: ContainerChange | None) -> str:
    """Format container change for display.

    Args:
        change: Container change object or None.

    Returns:
        Formatted string describing the container conversion.
    """
    if change is None:
        return ""

    lines = [
        f"Container: {change.source_format.upper()} → {change.target_format.upper()}"
    ]

    if change.warnings:
        lines.append("  Warnings:")
        for warning in change.warnings:
            lines.append(f"    - {warning}")

    if change.incompatible_tracks:
        track_list = ", ".join(str(t) for t in change.incompatible_tracks)
        lines.append(f"  Incompatible tracks: {track_list}")

    return "\n".join(lines)


def _format_dry_run_output(
    policy_path: Path,
    policy_version: int,
    target_path: Path,
    plan,
) -> str:
    """Format dry-run output in human-readable format."""
    lines = [
        f"Policy: {policy_path} (v{policy_version})",
        f"Target: {target_path}",
        "",
    ]

    if plan.is_empty:
        lines.append("No changes required - file already matches policy.")
    else:
        lines.append("Proposed changes:")

        # Show traditional actions first
        for action in plan.actions:
            lines.append(f"  {action.description}")

        # Show track dispositions if present
        if plan.track_dispositions:
            lines.append("")
            lines.append("Track dispositions:")
            lines.append(_format_track_dispositions(plan.track_dispositions))

        # Show container change if present
        if plan.container_change:
            lines.append("")
            lines.append(_format_container_change(plan.container_change))

        lines.append("")

        # Show summary with track counts
        summary_parts = []
        if plan.tracks_removed > 0:
            summary_parts.append(
                f"{plan.tracks_removed} track{'s' if plan.tracks_removed > 1 else ''} "
                "to be removed"
            )
        if len(plan.actions) > 0:
            summary_parts.append(
                f"{len(plan.actions)} metadata "
                f"change{'s' if len(plan.actions) > 1 else ''}"
            )
        if plan.container_change:
            summary_parts.append("container conversion")

        if summary_parts:
            lines.append(f"Summary: {', '.join(summary_parts)}")
        else:
            lines.append(f"Summary: {plan.summary}")

        lines.append("")
        lines.append("To apply these changes, run without --dry-run")

    return "\n".join(lines)


def _format_dry_run_json(
    policy_path: Path,
    policy_version: int,
    target_path: Path,
    container: str,
    plan,
) -> str:
    """Format dry-run output in JSON format."""
    actions_json = []
    for action in plan.actions:
        action_dict = {
            "action_type": action.action_type.value.upper(),
            "track_index": action.track_index,
            "current_value": action.current_value,
            "desired_value": action.desired_value,
        }
        actions_json.append(action_dict)

    # Build track dispositions list
    track_dispositions_json = []
    for disp in plan.track_dispositions:
        disp_dict = {
            "track_index": disp.track_index,
            "track_type": disp.track_type,
            "action": disp.action,
            "reason": disp.reason,
        }
        if disp.codec:
            disp_dict["codec"] = disp.codec
        if disp.language:
            disp_dict["language"] = disp.language
        if disp.title:
            disp_dict["title"] = disp.title
        if disp.channels:
            disp_dict["channels"] = disp.channels
        if disp.resolution:
            disp_dict["resolution"] = disp.resolution
        track_dispositions_json.append(disp_dict)

    output = {
        "status": "dry_run",
        "policy": {
            "path": str(policy_path),
            "version": policy_version,
        },
        "target": {
            "path": str(target_path),
            "container": container,
        },
        "plan": {
            "requires_remux": plan.requires_remux,
            "actions": actions_json,
            "track_dispositions": track_dispositions_json,
            "tracks_kept": plan.tracks_kept,
            "tracks_removed": plan.tracks_removed,
        },
    }

    # Add container change if present
    if plan.container_change:
        output["plan"]["container_change"] = {
            "source_format": plan.container_change.source_format,
            "target_format": plan.container_change.target_format,
            "warnings": list(plan.container_change.warnings),
            "incompatible_tracks": list(plan.container_change.incompatible_tracks),
        }

    return json.dumps(output, indent=2)


@click.command("apply")
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
    "--dry-run",
    "-n",
    is_flag=True,
    default=False,
    help="Preview changes without modifying file",
)
@click.option(
    "--keep-backup",
    is_flag=True,
    default=None,
    help="Keep backup file after successful operation",
)
@click.option(
    "--no-keep-backup",
    is_flag=True,
    default=None,
    help="Delete backup file after successful operation",
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
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show detailed operation log",
)
@click.argument(
    "target",
    type=click.Path(exists=False, path_type=Path),
)
def apply_command(
    policy_path: Path | None,
    profile: str | None,
    dry_run: bool,
    keep_backup: bool | None,
    no_keep_backup: bool | None,
    json_output: bool,
    verbose: bool,
    target: Path,
) -> None:
    """Apply a policy to a media file.

    TARGET is the path to the media file to process.

    You must specify either --policy or --profile (with default_policy).

    Examples:

        vpo apply --policy policy.yaml file.mkv

        vpo apply --profile movies file.mkv
    """
    # Load profile if specified
    loaded_profile = None
    if profile:
        from video_policy_orchestrator.config.profiles import (
            ProfileError,
            list_profiles,
            load_profile,
        )

        try:
            loaded_profile = load_profile(profile)
            if verbose and not json_output:
                click.echo(f"Using profile: {loaded_profile.name}")
        except ProfileError as e:
            available = list_profiles()
            _error_exit(str(e), EXIT_GENERAL_ERROR, json_output)
            if available:
                click.echo("\nAvailable profiles:", err=True)
                for name in sorted(available):
                    click.echo(f"  - {name}", err=True)

    # Determine policy path from CLI or profile
    if policy_path is None:
        if loaded_profile and loaded_profile.default_policy:
            policy_path = loaded_profile.default_policy
        else:
            _error_exit(
                "No policy specified. Use --policy or --profile with default_policy.",
                EXIT_POLICY_VALIDATION_ERROR,
                json_output,
            )

    # Resolve paths
    policy_path = policy_path.expanduser().resolve()
    target = target.expanduser().resolve()

    # Load and validate policy
    try:
        policy = load_policy(policy_path)
    except FileNotFoundError:
        _error_exit(
            f"Policy file not found: {policy_path}",
            EXIT_POLICY_VALIDATION_ERROR,
            json_output,
        )
    except PolicyValidationError as e:
        _error_exit(str(e), EXIT_POLICY_VALIDATION_ERROR, json_output)

    # Check target exists
    if not target.exists():
        _error_exit(
            f"Target file not found: {target}",
            EXIT_TARGET_NOT_FOUND,
            json_output,
        )

    # Get file info from database
    try:
        with get_connection() as conn:
            file_record = get_file_by_path(conn, str(target))
            if file_record is None:
                _error_exit(
                    f"File not found in database. Run 'vpo scan' first: {target}",
                    EXIT_TARGET_NOT_FOUND,
                    json_output,
                )

            # Get tracks from database
            track_records = get_tracks_for_file(conn, file_record.id)
            tracks = _tracks_from_records(track_records)
    except sqlite3.Error as e:
        _error_exit(
            f"Database error: {e}",
            EXIT_GENERAL_ERROR,
            json_output,
        )

    if not tracks:
        _error_exit(
            f"No tracks found for file: {target}",
            EXIT_GENERAL_ERROR,
            json_output,
        )

    # Determine container format
    container = file_record.container_format or target.suffix.lstrip(".")

    # Check tool availability for non-dry-run
    if not dry_run:
        tools = check_tool_availability()
        if container.lower() in ("mkv", "matroska"):
            # MKV files need mkvpropedit for metadata, mkvmerge for reordering
            if not tools.get("mkvpropedit"):
                _error_exit(
                    "Required tool not available: mkvpropedit. Install mkvtoolnix.",
                    EXIT_TOOL_NOT_AVAILABLE,
                    json_output,
                )
        elif not tools.get("ffmpeg"):
            _error_exit(
                "Required tool not available: ffmpeg. Install ffmpeg.",
                EXIT_TOOL_NOT_AVAILABLE,
                json_output,
            )

    # Get policy engine plugin
    policy_engine = _get_policy_engine()

    # Evaluate policy using the plugin
    if verbose:
        click.echo(f"Evaluating policy against {len(tracks)} tracks...")

    plan = policy_engine.evaluate(
        file_id=str(file_record.id),
        file_path=target,
        container=container,
        tracks=tracks,
        policy=policy,
    )

    if verbose:
        click.echo(f"Plan: {plan.summary}")

    # Output results
    if dry_run:
        if json_output:
            click.echo(
                _format_dry_run_json(
                    policy_path, policy.schema_version, target, container, plan
                )
            )
        else:
            click.echo(
                _format_dry_run_output(policy_path, policy.schema_version, target, plan)
            )
        sys.exit(EXIT_SUCCESS)

    # Non-dry-run mode: apply changes
    if plan.is_empty:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "completed",
                        "message": "No changes required",
                        "actions_applied": 0,
                    }
                )
            )
        else:
            click.echo(f"Policy: {policy_path} (v{policy.schema_version})")
            click.echo(f"Target: {target}")
            click.echo("")
            click.echo("No changes required - file already matches policy.")
        sys.exit(EXIT_SUCCESS)

    # Check if plan requires remux (track reordering) and mkvmerge is available
    if plan.requires_remux:
        has_reorder = any(a.action_type == ActionType.REORDER for a in plan.actions)
        if has_reorder:
            tools = check_tool_availability()
            if not tools.get("mkvmerge"):
                _error_exit(
                    "Track reordering requires mkvmerge. Install mkvtoolnix.",
                    EXIT_TOOL_NOT_AVAILABLE,
                    json_output,
                )

    # Determine backup behavior
    should_keep_backup = keep_backup if keep_backup is not None else True
    if no_keep_backup:
        should_keep_backup = False

    # Acquire file lock to prevent concurrent modifications
    try:
        with file_lock(target):
            # Create operation record
            operation = create_operation(conn, plan, file_record.id, str(policy_path))

            # Update status to IN_PROGRESS
            update_operation_status(conn, operation.id, OperationStatus.IN_PROGRESS)

            # Execute the plan using the policy engine plugin
            import time

            if verbose:
                click.echo("Using executor: PolicyEnginePlugin")
                click.echo(f"Executing {len(plan.actions)} actions...")

            start_time = time.time()
            result = policy_engine.execute(plan, keep_backup=should_keep_backup)
            duration = time.time() - start_time

            if verbose:
                click.echo(f"Execution completed in {duration:.2f}s")

            if result.success:
                # Update operation status to COMPLETED
                if result.backup_path:
                    backup_path_str = str(result.backup_path)
                else:
                    backup_path_str = None
                update_operation_status(
                    conn,
                    operation.id,
                    OperationStatus.COMPLETED,
                    backup_path=backup_path_str,
                )

                # Output success
                if json_output:
                    output = {
                        "status": "completed",
                        "operation_id": operation.id,
                        "policy": {
                            "path": str(policy_path),
                            "version": policy.schema_version,
                        },
                        "target": {
                            "path": str(target),
                            "container": container,
                        },
                        "actions_applied": len(plan.actions),
                        "duration_seconds": round(duration, 1),
                        "backup_kept": should_keep_backup,
                    }
                    if result.backup_path:
                        output["backup_path"] = str(result.backup_path)
                    click.echo(json.dumps(output, indent=2))
                else:
                    click.echo(f"Policy: {policy_path} (v{policy.schema_version})")
                    click.echo(f"Target: {target}")
                    click.echo("")
                    msg = f"Applied {len(plan.actions)} changes in {duration:.1f}s"
                    click.echo(msg)
                    if result.backup_path:
                        click.echo(f"Backup: {result.backup_path} (kept)")

                sys.exit(EXIT_SUCCESS)
            else:
                # Update operation status to FAILED (backup restored by executor)
                update_operation_status(
                    conn,
                    operation.id,
                    OperationStatus.ROLLED_BACK,
                    error_message=result.message,
                )

                _error_exit(result.message, EXIT_OPERATION_FAILED, json_output)

    except FileLockError:
        _error_exit(
            f"File is being modified by another operation: {target}",
            EXIT_GENERAL_ERROR,
            json_output,
        )


def _error_exit(message: str, code: int, json_output: bool) -> None:
    """Exit with an error message."""
    if json_output:
        click.echo(
            json.dumps(
                {
                    "status": "failed",
                    "error": {
                        "code": _code_to_name(code),
                        "message": message,
                    },
                }
            ),
            err=True,
        )
    else:
        click.echo(f"Error: {message}", err=True)
    sys.exit(code)


def _code_to_name(code: int) -> str:
    """Convert exit code to error name."""
    names = {
        EXIT_GENERAL_ERROR: "GENERAL_ERROR",
        EXIT_POLICY_VALIDATION_ERROR: "POLICY_VALIDATION_ERROR",
        EXIT_TARGET_NOT_FOUND: "TARGET_NOT_FOUND",
        EXIT_TOOL_NOT_AVAILABLE: "TOOL_NOT_AVAILABLE",
        EXIT_OPERATION_FAILED: "OPERATION_FAILED",
    }
    return names.get(code, "UNKNOWN_ERROR")
