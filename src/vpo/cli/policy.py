"""CLI commands for policy management."""

import json
from pathlib import Path

import click

from vpo.cli.exit_codes import ExitCode
from vpo.policy.loader import load_policy
from vpo.policy.pydantic_models import PolicyValidationError


@click.group("policy")
def policy_group() -> None:
    """Manage and validate policy files."""
    pass


@policy_group.command("validate")
@click.argument("policy_file", type=click.Path(exists=False, path_type=Path))
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output validation result in JSON format.",
)
def validate_policy_cmd(policy_file: Path, json_output: bool) -> None:
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
        vpo policy validate my-policy.yaml --json
    """
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

    # Try to load and validate the policy
    try:
        load_policy(policy_path)
        result["valid"] = True
        result["message"] = "Policy is valid"
    except PolicyValidationError as e:
        error_msg = str(e.message) if hasattr(e, "message") else str(e)
        result["errors"].append(
            {
                "field": getattr(e, "field", None),
                "message": error_msg,
                "code": "validation_error",
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
