"""CLI commands for policy management.

This module provides commands for managing policy files:
- policy list: List available policies
- policy show: Display policy contents
- policy validate: Validate policy syntax

The `policy run` command has been promoted to `vpo process` for better
discoverability as a top-level command.
"""

import json
import logging
from pathlib import Path

import click

from vpo.cli.exit_codes import ExitCode
from vpo.cli.output import format_option
from vpo.config.loader import get_config
from vpo.policy.loader import PolicyValidationError, load_policy

logger = logging.getLogger(__name__)


def _get_policy_directories() -> list[Path]:
    """Get list of directories to search for policies.

    Returns:
        List of policy directories (default + configured).
    """
    config = get_config()
    data_dir = config.data_dir

    # Default policy directory
    default_dir = data_dir / "policies"

    # Return unique directories
    dirs = [default_dir]

    return [d for d in dirs if d.exists()]


def _discover_policies() -> list[tuple[Path, str, bool]]:
    """Discover all policy files in configured directories.

    Returns:
        List of (path, name, is_valid) tuples.
    """
    policies = []

    for policy_dir in _get_policy_directories():
        for path in policy_dir.glob("*.yaml"):
            name = path.stem
            # Check if valid
            try:
                load_policy(path)
                is_valid = True
            except (PolicyValidationError, FileNotFoundError, Exception):
                is_valid = False

            policies.append((path, name, is_valid))

        # Also check .yml files
        for path in policy_dir.glob("*.yml"):
            name = path.stem
            try:
                load_policy(path)
                is_valid = True
            except (PolicyValidationError, FileNotFoundError, Exception):
                is_valid = False

            policies.append((path, name, is_valid))

    # Sort by name
    return sorted(policies, key=lambda x: x[1].lower())


@click.group("policy")
def policy_group() -> None:
    """Manage policy files.

    Commands for listing, viewing, and validating policy files.
    To apply a policy to files, use 'vpo process'.

    Examples:

        # List available policies
        vpo policy list

        # View policy contents
        vpo policy show normalize

        # Validate a policy
        vpo policy validate my-policy.yaml

        # Apply a policy to files (promoted to top-level)
        vpo process --policy my-policy.yaml /path/to/files
    """
    pass


# =============================================================================
# List Command
# =============================================================================


@policy_group.command("list")
@format_option
def list_policies_cmd(output_format: str) -> None:
    """List available policy files.

    Scans ~/.vpo/policies/ for YAML policy files and shows their
    validation status.

    Examples:

        # List all policies
        vpo policy list

        # Output as JSON
        vpo policy list --format json
    """
    json_output = output_format == "json"
    policies = _discover_policies()

    if json_output:
        output = {
            "directories": [str(d) for d in _get_policy_directories()],
            "policies": [
                {
                    "name": name,
                    "path": str(path),
                    "valid": is_valid,
                }
                for path, name, is_valid in policies
            ],
        }
        click.echo(json.dumps(output, indent=2))
        return

    if not policies:
        dirs = _get_policy_directories()
        if dirs:
            click.echo(f"No policies found in {dirs[0]}")
        else:
            click.echo("No policy directories configured.")
        click.echo()
        click.echo("To create a policy, add a YAML file to ~/.vpo/policies/")
        return

    # Header
    click.echo(f"{'NAME':<25} {'PATH':<50} {'VALID':<8}")
    click.echo("-" * 85)

    # Policies
    for path, name, is_valid in policies:
        path_str = str(path)
        if len(path_str) > 50:
            path_str = "..." + path_str[-47:]

        if is_valid:
            valid_str = click.style("Yes", fg="green")
        else:
            valid_str = click.style("No", fg="red")

        click.echo(f"{name:<25} {path_str:<50} {valid_str}")

    click.echo()
    click.echo(f"Found {len(policies)} policy file(s)")


# =============================================================================
# Show Command
# =============================================================================


@policy_group.command("show")
@click.argument("policy_name_or_path")
@format_option
@click.option(
    "--raw",
    is_flag=True,
    help="Output raw YAML without parsing.",
)
def show_policy_cmd(policy_name_or_path: str, output_format: str, raw: bool) -> None:
    """Display contents of a policy file.

    POLICY_NAME_OR_PATH can be either:
    - A policy name (without .yaml extension) to search in ~/.vpo/policies/
    - A path to a policy file

    Examples:

        # Show policy by name
        vpo policy show normalize

        # Show policy by path
        vpo policy show /path/to/policy.yaml

        # Output as parsed JSON
        vpo policy show normalize --format json

        # Output raw YAML
        vpo policy show normalize --raw
    """
    json_output = output_format == "json"
    if json_output and raw:
        raise click.ClickException("Cannot use both --format json and --raw")

    # Find policy file
    policy_path = _resolve_policy_path(policy_name_or_path)

    if policy_path is None:
        raise click.ClickException(
            f"Policy '{policy_name_or_path}' not found. "
            "Specify a valid policy name or path."
        )

    if raw:
        # Output raw YAML
        try:
            content = policy_path.read_text()
            click.echo(content)
        except OSError as e:
            raise click.ClickException(f"Failed to read policy: {e}")
        return

    # Load and parse policy
    try:
        policy = load_policy(policy_path)
    except PolicyValidationError as e:
        raise click.ClickException(f"Policy validation failed: {e}")
    except FileNotFoundError:
        raise click.ClickException(f"Policy file not found: {policy_path}")

    if json_output:
        # Output parsed structure as JSON
        output = _policy_to_dict(policy, policy_path)
        click.echo(json.dumps(output, indent=2))
        return

    # Human-readable output
    _output_policy_human(policy, policy_path)


def _resolve_policy_path(name_or_path: str) -> Path | None:
    """Resolve a policy name or path to a file path.

    Args:
        name_or_path: Policy name or path.

    Returns:
        Path to policy file, or None if not found.
    """
    # Check if it's a path
    path = Path(name_or_path)
    if path.exists():
        return path.resolve()

    # Try with .yaml extension
    yaml_path = Path(f"{name_or_path}.yaml")
    if yaml_path.exists():
        return yaml_path.resolve()

    # Search policy directories
    for policy_dir in _get_policy_directories():
        for ext in (".yaml", ".yml"):
            candidate = policy_dir / f"{name_or_path}{ext}"
            if candidate.exists():
                return candidate

    return None


def _policy_to_dict(policy, policy_path: Path) -> dict:
    """Convert a policy to a JSON-serializable dict.

    Args:
        policy: Loaded PolicySchema.
        policy_path: Path to the policy file.

    Returns:
        Dictionary representation.
    """
    result = {
        "path": str(policy_path),
        "name": policy.name or policy_path.stem,
        "schema_version": policy.schema_version,
        "phases": [],
    }

    # Add config
    if policy.config:
        on_error = policy.config.on_error.value if policy.config.on_error else None
        result["config"] = {"on_error": on_error}

    # Add phases
    for phase in policy.phases:
        phase_dict = {
            "name": phase.name,
        }

        # Add phase type info
        if phase.container:
            phase_dict["type"] = "container"
            target = phase.container.target.value if phase.container.target else None
            phase_dict["target"] = target
        elif phase.transcode:
            phase_dict["type"] = "transcode"
            phase_dict["video_codec"] = phase.transcode.to
            if phase.audio_transcode:
                phase_dict["audio_transcode"] = True
        elif phase.rules:
            phase_dict["type"] = "rules"
            phase_dict["rules_count"] = len(phase.rules.items)
        elif phase.audio_synthesis:
            phase_dict["type"] = "audio_synthesis"
        elif phase.metadata:
            phase_dict["type"] = "metadata"
        elif phase.tracks:
            phase_dict["type"] = "tracks"
        else:
            phase_dict["type"] = "other"

        # Add skip conditions
        if phase.skip_when:
            phase_dict["skip_when"] = True
        if phase.depends_on:
            phase_dict["depends_on"] = list(phase.depends_on)
        if phase.run_if:
            phase_dict["run_if"] = True

        result["phases"].append(phase_dict)

    return result


def _output_policy_human(policy, policy_path: Path) -> None:
    """Output policy in human-readable format.

    Args:
        policy: Loaded PolicySchema.
        policy_path: Path to the policy file.
    """
    click.echo(f"\nPolicy: {policy.name or policy_path.stem}")
    click.echo("=" * 60)
    click.echo(f"  Path:    {policy_path}")
    click.echo(f"  Schema:  v{policy.schema_version}")

    if policy.config:
        click.echo("\n  Config:")
        if policy.config.on_error:
            click.echo(f"    on_error: {policy.config.on_error.value}")

    click.echo(f"\n  Phases ({len(policy.phases)}):")

    for i, phase in enumerate(policy.phases, 1):
        # Determine phase type
        if phase.container:
            phase_type = "container"
            if phase.container.target:
                details = f"target: {phase.container.target.value}"
            else:
                details = ""
        elif phase.transcode:
            phase_type = "transcode"
            details_parts = [f"video: {phase.transcode.to}"]
            if phase.audio_transcode:
                details_parts.append("audio: yes")
            details = ", ".join(details_parts)
        elif phase.rules:
            phase_type = "rules"
            details = (
                f"{len(phase.rules.items)} rule(s), match: {phase.rules.match.value}"
            )
        elif phase.audio_synthesis:
            phase_type = "audio_synthesis"
            details = f"{len(phase.audio_synthesis)} track(s)"
        elif phase.metadata:
            phase_type = "metadata"
            details = ""
        elif phase.tracks:
            phase_type = "tracks"
            details = ""
        else:
            phase_type = "other"
            details = ""

        click.echo(f"    {i}. {phase.name} [{phase_type}]")
        if details:
            click.echo(f"       {details}")

        # Show conditionals
        if phase.skip_when:
            click.echo("       skip_when: configured")
        if phase.depends_on:
            click.echo(f"       depends_on: {', '.join(phase.depends_on)}")
        if phase.run_if:
            click.echo("       run_if: configured")

    click.echo()


# =============================================================================
# Validate Command
# =============================================================================


@policy_group.command("validate")
@click.argument("policy_file", type=click.Path(exists=False, path_type=Path))
@format_option
def validate_policy_cmd(policy_file: Path, output_format: str) -> None:
    """Validate a policy YAML file.

    Checks that the policy file has valid YAML syntax, uses the correct
    schema version, and contains all required fields.

    Exit codes:
        0: Policy is valid
        10: Policy validation failed

    Examples:

        # Validate a policy file
        vpo policy validate my-policy.yaml

        # Validate with JSON output (for CI/tooling)
        vpo policy validate my-policy.yaml --format json
    """
    json_output = output_format == "json"
    result = _validate_policy(policy_file)

    if json_output:
        _output_json(result)
    else:
        _output_human(result)

    if not result["valid"]:
        raise SystemExit(ExitCode.POLICY_VALIDATION_ERROR)


def _validate_policy(policy_path: Path) -> dict:
    """Validate a policy file and return the result as a dict.

    Args:
        policy_path: Path to the policy file.

    Returns:
        Dict with keys: valid, file, message, errors
    """
    result = {
        "valid": False,
        "file": str(policy_path),
        "errors": [],
    }

    # Check file exists
    if not policy_path.exists():
        result["errors"].append(
            {
                "field": None,
                "message": f"File not found: {policy_path}",
                "code": "file_not_found",
            }
        )
        result["message"] = f"File not found: {policy_path}"
        return result

    # Check if it's a directory
    if policy_path.is_dir():
        result["errors"].append(
            {
                "field": None,
                "message": f"Path is a directory, not a file: {policy_path}",
                "code": "is_directory",
            }
        )
        result["message"] = f"Path is a directory, not a file: {policy_path}"
        return result

    # Try to load and validate the policy
    try:
        load_policy(policy_path)
        result["valid"] = True
        result["message"] = "Policy is valid"
    except PolicyValidationError as e:
        error_msg = str(e.message) if hasattr(e, "message") else str(e)
        # Detect YAML syntax errors from the message
        code = "validation_error"
        if "Invalid YAML syntax" in error_msg:
            code = "yaml_syntax_error"
        result["errors"].append(
            {
                "field": getattr(e, "field", None),
                "message": error_msg,
                "code": code,
            }
        )
        result["message"] = error_msg
    except FileNotFoundError as e:
        result["errors"].append(
            {
                "field": None,
                "message": str(e),
                "code": "file_not_found",
            }
        )
        result["message"] = str(e)
    except PermissionError as e:
        result["errors"].append(
            {
                "field": None,
                "message": f"Permission denied: {e}",
                "code": "permission_denied",
            }
        )
        result["message"] = f"Permission denied: {e}"
    except IsADirectoryError as e:
        result["errors"].append(
            {
                "field": None,
                "message": f"Path is a directory: {e}",
                "code": "is_directory",
            }
        )
        result["message"] = f"Path is a directory: {e}"
    except Exception as e:
        result["errors"].append(
            {
                "field": None,
                "message": str(e),
                "code": "unknown_error",
            }
        )
        result["message"] = str(e)

    return result


def _output_json(result: dict) -> None:
    """Output validation result in JSON format."""
    click.echo(json.dumps(result, indent=2))


def _output_human(result: dict) -> None:
    """Output validation result in human-readable format."""
    if result["valid"]:
        click.echo(click.style("Valid", fg="green") + f": {result['file']}")
    else:
        click.echo(click.style("Invalid", fg="red") + f": {result['file']}")
        if result.get("message"):
            click.echo(f"  {result['message']}")
